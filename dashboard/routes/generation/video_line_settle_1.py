from __future__ import annotations

# --- w47-r1 (cr48 H1, M1, hung starter): the line's durable cancel settle and its truthful answer -------------------
# Loaded right after video_line_1.py (same namespace). A started take with a cancel intent that is not settled
# (cancel_requested 1 = pending, 3 = a settle under way) is cancelled on the ledger by whichever step, start or
# registration of Hermes comes next, whatever moment the process that should have done it died at.

# w47-r1 item 1 (cr48 H1): a started take with a cancel intent that is not settled (1 = pending, 3 = a settle under
# way) is cancelled on the ledger by recovery, whatever moment the process that should have done it died at. A settle
# under way in a live process is left to it; one whose process is gone is taken over. Idempotent: a settled row (2)
# is never touched again, and a settle that did not end the ledger job stays pending for the next step or start.

# --- w47-s1 invariants 2 and 4: recovery decides a claim that is not live in one line-store write transaction -------
def _vq_claim_live(row: Mapping[str, Any], me: str, here: set, alive: Any, clock: Any) -> bool:
    """Is this claim still its owner's to finish? Within the deadline: a claim of this process it still holds, or of
    another process that runs. Past the deadline: never (it is fenced, invariant 4)."""
    claimed_at = row.get("claimed_at")
    if isinstance(claimed_at, (int, float)) and clock() - float(claimed_at) > float(_VQ_STARTING_DEADLINE_SECONDS):
        return False
    owner = row.get("owner")
    if owner == me:
        return row["studio_job_id"] in here or row.get("claim_generation") in here
    return bool(alive(owner))


def _vq_decide_starting(row: Mapping[str, Any], ledger_has: Any, clock: Any) -> bool:
    """Invariant 2: ONE line-store write transaction decides a starting take whose claim is not live. Its ledger row
    is written only inside a line-store write transaction that still sees this claim and marks submit_started = 2
    with it (_vq_fenced_insert). So inside this transaction: mark 2 (or a ledger row seen before it, for rows of
    earlier releases) -> started (a cancel intent stays for _vq_settle_cancel); otherwise the claim is fenced
    (generation cleared) and no later insert can pass: the take is proven never sent, back at its place or removed
    with its cancel settled. The injected ledger look runs before the transaction; the ledger itself is read again inside it. An
    unreadable ledger decides nothing (the row stays)."""
    ledgered_before = bool(ledger_has(row["client_request_id"]))
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                current = _vq_dict(connection.execute("SELECT * FROM video_line WHERE seq = ?", (row["seq"],)).fetchone())
                if (current is None or current["state"] != "starting" or current.get("owner") != row.get("owner")
                        or current.get("claim_generation") != row.get("claim_generation")):
                    connection.execute("ROLLBACK")
                    return False
                # The ledger is read again under the line's lock: a starter that died between its ledger commit and
                # its line commit left a ledger row without the mark 2.
                if (current.get("submit_started") == 2 or ledgered_before
                        or _read_client_row(current["client_request_id"]) is not None):
                    connection.execute("UPDATE video_line SET state = 'started', ended_at = ? WHERE seq = ?",
                                       (clock(), row["seq"]))
                else:
                    connection.execute(_VQ_NEVER_SENT_SQL + " WHERE seq = ?", (time.time(), row["seq"]))
                _vq_prune(connection)
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return True
        finally:
            connection.close()


def _vq_recover(ledger_has: Any = None, alive: Any = None, now: Any = None, settle: bool = True) -> list[str]:
    """Starting takes whose claim is not live (owner gone, or past the deadline) are decided by _vq_decide_starting;
    waiting takes whose preparer is gone or past the deadline are fenced back to plain waiting; unsettled cancels of
    any state are reconciled against the ledger (w47-t1 item 2) and settled (settle=False: the request side's cheap
    pass, no engine call). Never touches a live claim within the deadline."""
    alive = alive or _take_owner_module().token_alive
    clock = now or time.time
    ledger_has = ledger_has or (lambda crid: _read_client_row(crid) is not None)
    me = _vq_owner_token()
    here = _vq_claims_here()
    moved: list[str] = []
    for row in _vq_read("SELECT * FROM video_line WHERE state = 'starting' ORDER BY seq", ()):
        if _vq_claim_live(row, me, here, alive, clock):
            continue
        try:
            decided = _vq_decide_starting(row, ledger_has, clock)
        except Exception:  # noqa: BLE001 - an unreadable ledger or a busy line decides nothing; the row stays
            continue
        if decided:
            moved.append(row["studio_job_id"])
    _vq_recover_preparing(alive, clock)
    _vq_reconcile_ended(alive, clock)
    if settle:
        _vq_settle_pending(alive)
    return moved


# --- w47-t1 item 2 (cr50 H8): an unsettled cancel is settled only against the ledger, in every state ------------------
# The schema upgrade only adds columns. A row whose cancel is unsettled (1, 3) but which left the line without a
# ledger answer (removed or failed by an earlier release) is decided here, in one line-store write transaction that
# reads the ledger by its client request id: a ledger row -> the take was sent: 'started' with the intent pending (the
# ledger job is then cancelled on the engine, or has ended); no ledger row and no live claim -> the claim is cleared
# (fenced) and the cancel settled as never sent.
def _vq_reconcile_ended(alive: Any, clock: Any) -> None:
    me, here = _vq_owner_token(), _vq_claims_here()
    for row in _vq_read("SELECT * FROM video_line WHERE state IN ('removed', 'failed', 'waiting') AND "
                        + _VQ_UNSETTLED + " ORDER BY seq", ()):
        if row.get("owner") is not None and _vq_claim_live(row, me, here, alive, clock):
            continue
        try:
            with _VQ_DB_LOCK:
                connection = _vq_connect()
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        current = _vq_dict(connection.execute("SELECT * FROM video_line WHERE seq = ?", (row["seq"],)).fetchone())
                        if (current is None or current["state"] != row["state"] or current.get("cancel_requested") not in (1, 3)
                                or current.get("claim_generation") != row.get("claim_generation")):
                            connection.execute("ROLLBACK")
                            continue
                        if _read_client_row(current["client_request_id"]) is not None:
                            connection.execute("UPDATE video_line SET state = 'started', cancel_requested = 1, settle_owner = NULL,"
                                               " settle_at = NULL, owner = NULL, claimed_at = NULL, claim_generation = NULL,"
                                               " ended_at = COALESCE(ended_at, ?) WHERE seq = ?", (clock(), row["seq"]))
                        elif current["state"] == "waiting":
                            connection.execute(_VQ_NEVER_SENT_SQL + " WHERE seq = ?", (time.time(), row["seq"]))
                        else:  # removed or failed with no ledger row: it keeps its state; fenced, the cancel settled
                            connection.execute("UPDATE video_line SET cancel_requested = 2, owner = NULL, claimed_at = NULL,"
                                               " claim_generation = NULL, submit_started = 0 WHERE seq = ?", (row["seq"],))
                        connection.execute("COMMIT")
                    except BaseException:
                        if connection.in_transaction:
                            connection.execute("ROLLBACK")
                        raise
                finally:
                    connection.close()
        except Exception:  # noqa: BLE001 - an unreadable ledger or a busy line decides nothing; it stays unsettled
            continue


def _vq_settling_here() -> set:
    """The takes this process is cancelling on the ledger right now (process-wide, like _vq_claims_here)."""
    holder = sys.modules.setdefault("_film_suite_video_line_state", type(sys)("_film_suite_video_line_state"))
    if not hasattr(holder, "settling"):
        holder.settling = set()
    return holder.settling


def _vq_unsettled() -> list[dict[str, Any]]:
    return _vq_read("SELECT * FROM video_line WHERE state = 'started' AND cancel_requested IN (1, 3) ORDER BY seq", ())


def _vq_unsettled_any() -> list[dict[str, Any]]:
    """w47-t1 item 2: every row whose cancel is not settled, whatever its state (recovery reconciles each)."""
    return _vq_read("SELECT * FROM video_line WHERE state <> 'starting' AND cancel_requested IN (1, 3) ORDER BY seq", ())


def _vq_run(coroutine: Any, timeout: float | None = None) -> Any:
    """Run a coroutine to its end from synchronous code (its own loop; its own thread when this one has a loop or a
    bound is asked). w47-u1 item 3: past ``timeout`` the caller goes on (TimeoutError); the thread stays until its call
    returns, and its writes carry a settle generation that a takeover has replaced (they miss)."""
    if timeout is None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["result"] = asyncio.run(coroutine)
        except BaseException as exc:  # noqa: BLE001 - handed back to the caller's thread
            box["error"] = exc
    thread = threading.Thread(target=run, name="fs-video-line-settle", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("the settle did not return within its lease")
    if "error" in box:
        raise box["error"]
    return box.get("result")


# w47-u1 item 3 (cr51 H13): settle ownership is a LEASE. State 3 records owner, generation and settle_at; any actor
# (the starter, a poll, the Jobs list, a start, another process) takes over a settle whose lease is older than
# _VQ_SETTLE_LEASE_SECONDS, or whose process is gone, by bumping the generation; the old settler's writes miss. The
# engine cancel is idempotent (cancelling a cancelled or finished prompt is harmless), so a duplicate cancel after a
# takeover is accepted.
_VQ_SETTLE_LEASE_SECONDS = 60.0


def _vq_lease_expired(row: Mapping[str, Any], clock: Any = None) -> bool:
    at = row.get("settle_at")
    return not isinstance(at, (int, float)) or (clock or time.time)() - float(at) > float(_VQ_SETTLE_LEASE_SECONDS)


def _vq_settle_pending(alive: Any = None, takeover_only: bool = False) -> None:
    """Settle every pending cancel of a started take (1), and take over every settle (3) whose lease ran out or whose
    process is gone. takeover_only (the request side's engine pass): only the takeovers."""
    alive = alive or _take_owner_module().token_alive
    me = _vq_owner_token()
    for row in _vq_unsettled():
        if row["cancel_requested"] == 3:
            owner = row.get("settle_owner")
            if not _vq_lease_expired(row) and (owner == me or alive(owner)):
                continue  # a live lease: its holder settles it
        elif takeover_only:
            continue
        try:
            _vq_run(_vq_settle_cancel(row["studio_job_id"], row.get("project_id"), stale=row),
                    timeout=float(_VQ_SETTLE_LEASE_SECONDS))
        except Exception:  # noqa: BLE001 - it stays pending (or its lease runs out); the next pass tries again
            pass


def _vq_settles_due(alive: Any = None) -> bool:
    """A settle (3) whose lease ran out or whose process is gone: the request side's engine pass takes it over."""
    try:
        alive = alive or _take_owner_module().token_alive
        me = _vq_owner_token()
        return any(row["cancel_requested"] == 3 and (_vq_lease_expired(row) or (row.get("settle_owner") != me
                   and not alive(row.get("settle_owner")))) for row in _vq_unsettled())
    except Exception:  # noqa: BLE001
        return False


def _vq_has_work() -> bool:
    """Takes wait or are being started, or a take still has a cancel to settle (w47-r1 item 1; w47-t1: any state)."""
    return bool(_vq_path().is_file() and (_vq_count() or _vq_unsettled_any()))


def _vq_wake_if_work() -> None:
    """w47-t1 item 4: wake when the line holds work; a store that cannot be read wakes anyway (the starter decides)."""
    try:
        work = _vq_has_work()
    except Exception:  # noqa: BLE001
        work = True
    if work:
        _vq_wake()


# w47-r1 item 1 (cr48 H1): a cancel whose take could not be stopped yet never answers as if it were done, nor as if it
# were lost: the intent is kept in the line store until it is settled.
# w47-t1 item 5: the three ways it settles, all true: cancelled on the engine, never sent, or ended by itself first.
# w47-u1 item 4: a take handed to ComfyUI without its engine ID is given up with a tombstone.
# w47-v1 (cr61 H15): cleaning up a late copy is best effort; the text says only that.
_VQ_CANCEL_PENDING_TEXT = ("This take is still being started; the cancel is kept: it will be cancelled on the engine once it"
                           " has started, or it is never sent, unless it ended by itself before the cancel reached it. If it"
                           " is given up while being sent and a copy reaches ComfyUI later, Hermes tries to stop it; a copy"
                           " that already finished cannot be undone.")


def _vq_pending_receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _vq_receipt(row)
    receipt.update(cancel_pending=True, reason_text=_VQ_CANCEL_PENDING_TEXT)
    return receipt


def _vq_cancel_truth(studio_job_id: str, result: Any) -> Any:
    """The ledger's cancel answer, unless the take is still running with its intent kept: then 'will be cancelled'."""
    current = _vq_get(studio_job_id)
    if current is None or current.get("cancel_requested") not in (1, 3) or _vq_ledger_ended(studio_job_id, result):
        return result
    answer = dict(result) if isinstance(result, Mapping) else {"details": None}
    answer.update(cancel_pending=True, reason_text=_VQ_CANCEL_PENDING_TEXT)
    return answer


async def _vq_settle_cancel(studio_job_id: str, project_id: str | None,
                            stale: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """A started take with a cancel intent is cancelled on the ledger by the holder of the settle lease (1 -> 3 -> 2);
    answers that caller's receipt, None when there was nothing to do or another caller holds a live lease. ``stale``
    is a row whose lease is taken over, only while it is unchanged (same generation and settle_at); the takeover bumps
    the generation, so the old holder's last write misses. The intent is settled (2) only once the ledger job has
    ended (and, for a take handed to ComfyUI without a prompt id, together with its tombstone)."""
    me, now, mine = _vq_owner_token(), time.time(), uuid.uuid4().hex
    if stale is not None and stale.get("cancel_requested") == 3:
        claimed = _vq_write("UPDATE video_line SET settle_owner = ?, settle_at = ?, settle_generation = ? WHERE studio_job_id = ?"
                            " AND state = 'started' AND cancel_requested = 3 AND settle_at IS ? AND settle_generation IS ?",
                            (me, now, mine, studio_job_id, stale.get("settle_at"), stale.get("settle_generation")))
    else:
        claimed = _vq_write("UPDATE video_line SET cancel_requested = 3, settle_owner = ?, settle_at = ?, settle_generation = ?"
                            " WHERE studio_job_id = ? AND state = 'started' AND cancel_requested = 1",
                            (me, now, mine, studio_job_id))
    if claimed != 1:
        return None
    here = _vq_settling_here()
    here.add(studio_job_id)
    settled = False
    try:
        # w47-t1 item 1: a ledger row not yet handed to ComfyUI (submitting) is ended by the compare-and-set a sender
        # also needs. w47-u1 item 1b: a row already sending (queued, no prompt id) is ended with its tombstone; a late
        # copy is looked for on the engine by its own sender and by the tombstone pass, which looks at once (best effort).
        try:
            record = _read_ledger_row(studio_job_id)
            if record.state == "submitting" and not record.provider_job_id:
                _v4_cas_unsent(record, record.project_id, "cancelled", "cancelled")
            elif record.state == "queued" and not record.provider_job_id:
                if _v4_give_up_sending(record, "cancelled", None, to="cancelled").is_terminal:
                    await _vq_tomb_pass(force=True)
        except Exception:  # noqa: BLE001 - no readable ledger row: the cancel route answers
            pass
        result = await _cancel_route_before_line(CancelRequest(id=studio_job_id, expected_project_id=project_id))
        settled = _vq_ledger_ended(studio_job_id, result)
        return result
    finally:
        try:
            _vq_write("UPDATE video_line SET cancel_requested = ?, settle_owner = NULL, settle_at = NULL, settle_generation = NULL"
                      " WHERE studio_job_id = ? AND cancel_requested = 3 AND settle_generation IS ?",
                      (2 if settled else 1, studio_job_id, mine))
        finally:
            here.discard(studio_job_id)


_VQ_ENDED = frozenset({"ready", "failed", "moderated", "cancelled"})


def _vq_ledger_ended(studio_job_id: str, result: Any) -> bool:
    """Has the take's ledger job ended (the cancel took, or it ended by itself)? The ledger's own row decides when it
    can be read; else the cancel's receipt. w47-u1 item 1c: a job that ended without a prompt id counts only together
    with its tombstone (written here when missing), so a late copy of it is still looked for on the engine."""
    try:
        record = _read_ledger_row(studio_job_id)
    except _comfy_job_store_module.JobNotFoundError:
        return True  # no ledger job under this id: nothing is left to stop
    except Exception:  # noqa: BLE001 - no readable ledger row: the receipt answers
        details = result.get("details") if isinstance(result, Mapping) else None
        return isinstance(details, Mapping) and details.get("status") in _VQ_ENDED
    if not record.is_terminal:
        return False
    # Every comfyui-local row that was handed to ComfyUI without a prompt id ends only through _v4_give_up_sending,
    # which writes the tombstone before the terminal move. A row an earlier release gave up by the lost-submit rule
    # (submission_unknown, no prompt id) gets its tombstone here, before its cancel is settled.
    if record.provider_job_id is None and record.reason_code == "submission_unknown":
        try:
            _vq_tomb_write(record.client_request_id, record.studio_job_id)
        except Exception:  # noqa: BLE001 - no tombstone, no settle: it stays pending
            return False
    return True
