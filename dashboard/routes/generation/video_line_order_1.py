from __future__ import annotations

# --- w47-r1 item 2 (cr48 M1): a direct /submit and the line's claim take the same authority -------------------------
# Loaded after video_line_1.py (same namespace). A direct local video submit is decided inside ONE write transaction on
# the line store (BEGIN IMMEDIATE, the lock every claim and admission takes): when a take waits or is being started, or
# the engine runs one, the newcomer joins the line behind them; otherwise it is written down as the one starting take
# (owner and claim generation of this process, already crossed into its submit) and submits under that reserved id.
# No look outside the transaction decides. A take that waits takes its place in that same transaction; its row is
# marked as being prepared (owner and generation of the sender) until its request is validated as it will be started,
# and no claim passes a row being prepared (strict order). A refusal removes the row.
# w47-s1 invariant 3: when the transaction cannot be had (busy, any error before COMMIT) the submit is refused with
# _vq_busy_answer and nothing is sent; errors after COMMIT are answered by the committed decision.
# w47-s1 invariant 4: a preparation whose sender is gone or past the deadline is fenced (_vq_recover_preparing): the row
# stays, plain waiting with prepared = 0, and the claimant that starts it prepares it; the fenced sender's writes miss.
# w47-s1 invariant 2: the ledger row of a line take is inserted only through _vq_fenced_insert.

_VQ_BUSY_TEXT = "The take line is busy; try again"


def _vq_busy_answer() -> dict[str, Any]:
    """Invariant 3: no decision could be made; nothing was added or sent. Retryable (same client_request_id)."""
    return {"error": _VQ_BUSY_TEXT, "reason_text": _VQ_BUSY_TEXT, "reason_code": "provider_busy", "details": None,
            "retryable": True, "retry_after": 1}


def _vq_admit_or_start(request: SubmitRequest, owner: str, generation: str) -> tuple[str, dict[str, Any] | None]:
    """One write transaction: ('replay' | 'conflict' | 'preparing' | 'start', row). 'preparing': the take waits, its row
    holds its place and is this sender's to prepare; 'start': the take is this sender's starting take."""
    sha = _vq_request_sha256(request)
    connection_id = VIDEO_LINE_CONNECTION
    with _VQ_DB_LOCK:
        connection = _vq_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                held = _vq_dict(connection.execute("SELECT * FROM video_line WHERE client_request_id = ?",
                                                   (request.client_request_id,)).fetchone())
                if held is not None:
                    held = _vq_with_positions(connection, [held])[0]
                    connection.execute("COMMIT")
                    if (held["request_sha256"] != sha or held["target_id"] != request.target_id
                            or held["project_id"] != request.project_id):
                        return "conflict", None
                    return "replay", held
                (in_line,) = connection.execute("SELECT COUNT(*) FROM video_line WHERE connection_id = ?"
                                                " AND state IN ('waiting', 'starting')", (connection_id,)).fetchone()
                waits = bool(in_line) or bool(_comfy_store().active_rows(connection_id))
                if waits and in_line >= VIDEO_LINE_MAX:
                    raise _VideoLineFull()
                prompt = (request.args or {}).get("prompt") if isinstance(request.args, Mapping) else None
                now = time.time()
                connection.execute(
                    "INSERT INTO video_line (studio_job_id, client_request_id, connection_id, project_id, by, request_json,"
                    " request_sha256, label, target_id, requested_basename, state, created_at, owner, claimed_at,"
                    " claim_generation, submit_started) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("studio:" + uuid.uuid4().hex, request.client_request_id, connection_id, request.project_id,
                     _film_caller() if _film_caller() in ("artist", "hermes") else "artist",
                     json.dumps(request.model_dump(mode="json")), sha,
                     _job_label(prompt if isinstance(prompt, str) else request.requested_basename), request.target_id,
                     request.requested_basename, "waiting" if waits else "starting", now, owner, now, generation,
                     0 if waits else 1))
                row = _vq_dict(connection.execute("SELECT * FROM video_line WHERE client_request_id = ?",
                                                  (request.client_request_id,)).fetchone())
                row = _vq_with_positions(connection, [row])[0]
                connection.execute("COMMIT")  # invariant 3: nothing after this line can turn the decision into an error
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return ("preparing" if waits else "start"), row
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - the decision is committed; closing cannot undo it
                pass


def _vq_prepare_waiting(request: SubmitRequest, row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Validate a waiting take as it will be started and hand its row to the line (None), or end it and answer the
    refusal. Every write is guarded by the sender's owner and generation: once the preparation was fenced
    (invariant 4) they change nothing; the row is the line's and the answer is its receipt as it stands."""
    guard = (row["studio_job_id"], row["owner"], row["claim_generation"])
    started, refusal = _vq_validated(request)
    if refusal is not None:
        # Refused before anyone was answered: the row goes (a waiting row never holds an unsettled cancel: a cancel
        # ends it at once, and then this guarded statement misses). The sender may retry under the same id.
        if _vq_write("DELETE FROM video_line WHERE studio_job_id = ? AND state = 'waiting' AND owner IS ?"
                     " AND claim_generation IS ?", guard) != 1:
            return None  # fenced meanwhile: the take is the line's (its claimant validates it again); its receipt answers
        return refusal
    prompt = (request.args or {}).get("prompt") if isinstance(request.args, Mapping) else None
    _vq_write("UPDATE video_line SET request_json = ?, requested_basename = ?, label = ?, owner = NULL, claimed_at = NULL,"
              " claim_generation = NULL, prepared = 1 WHERE studio_job_id = ? AND state = 'waiting' AND owner IS ?"
              " AND claim_generation IS ?",
              (json.dumps(started.model_dump(mode="json")), started.requested_basename,
               _job_label(prompt if isinstance(prompt, str) else started.requested_basename), *guard))
    return None


def _vq_prepare_claimed(request: SubmitRequest, claimed: Mapping[str, Any]) -> tuple[SubmitRequest, dict[str, Any] | None]:
    """Invariant 4: a take whose preparer was fenced is prepared by the claimant that starts it; a refusal ends it
    failed with its reason (guarded by this claim)."""
    started, refusal = _vq_validated(request)
    if refusal is not None:
        code = refusal.get("reason_code") if isinstance(refusal.get("reason_code"), str) else "invalid_request"
        _vq_finish(claimed["studio_job_id"], "failed", code, _job_cause_text(refusal.get("error")), claimed)
        return request, refusal
    _vq_write("UPDATE video_line SET request_json = ?, requested_basename = ?, prepared = 1 WHERE studio_job_id = ?"
              " AND state = 'starting' AND owner IS ? AND claim_generation IS ?",
              (json.dumps(started.model_dump(mode="json")), started.requested_basename, claimed["studio_job_id"],
               claimed.get("owner"), claimed.get("claim_generation")))
    return started, None


def _vq_recover_preparing(alive: Any, clock: Any = None) -> None:
    """Invariant 4: a waiting row whose preparer is gone or past the deadline is fenced: owner and generation cleared
    (its late writes miss), prepared = 0 (the claimant prepares it). The take keeps its place and is never lost."""
    me, here, clock = _vq_owner_token(), _vq_claims_here(), clock or time.time
    for row in _vq_read("SELECT * FROM video_line WHERE state = 'waiting' AND owner IS NOT NULL ORDER BY seq", ()):
        if _vq_claim_live(row, me, here, alive, clock):
            continue
        _vq_write("UPDATE video_line SET owner = NULL, claimed_at = NULL, claim_generation = NULL, prepared = 0"
                  " WHERE seq = ? AND state = 'waiting' AND owner IS ? AND claim_generation IS ?",
                  (row["seq"], row.get("owner"), row.get("claim_generation")))


def _vq_fenced_insert(client_request_id: Any, insert: Any) -> Any:
    """Invariant 2: a line take's ledger row is written only while its claim still holds. One line-store write
    transaction checks the claim (owner, generation, starting, no cancel settled), runs ``insert`` (the ledger
    create) and marks submit_started = 2 (ledgered). Recovery decides a starting row in the same kind of
    transaction, so a fenced claim can never insert afterwards: _VQFenced, nothing written, nothing sent.
    Not a line take (no reservation): ``insert`` runs as before."""
    job_id, claim = _vq_reserved_for(client_request_id), _vq_reserved_claim(client_request_id)
    if job_id is None:
        return insert()
    if claim is None:  # a line id reserved without its claim cannot be checked: fail closed
        raise _VQFenced()
    with _VQ_DB_LOCK:
        try:
            connection = _vq_connect()
        except sqlite3.Error as exc:
            raise _VQFenced(busy=True) from exc
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error as exc:  # the line store is busy: no ledger row, nothing sent; the take is put back
                raise _VQFenced(busy=True) from exc
            try:
                held = _vq_dict(connection.execute(
                    "SELECT * FROM video_line WHERE studio_job_id = ? AND state = 'starting' AND submit_started = 1"
                    " AND owner IS ? AND claim_generation IS ?",
                    (job_id, claim.get("owner"), claim.get("claim_generation"))).fetchone())
                if held is None:
                    raise _VQFenced()
                if held.get("cancel_requested") in (1, 3):  # cancelled before its ledger row: never sent, settled now
                    connection.execute(_VQ_NEVER_SENT_SQL + " WHERE studio_job_id = ?", (time.time(), job_id))
                    connection.execute("COMMIT")
                    raise _VQFenced()
                row = insert()
                connection.execute("UPDATE video_line SET submit_started = 2 WHERE studio_job_id = ?", (job_id,))
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return row
        finally:
            connection.close()


class _VQFenced(Exception):
    """The take's claim was fenced (or its cancel settled) before its ledger row: it must send nothing. busy: the
    line store could not be written; nothing was written or sent and the claim is given back (provider_busy)."""

    def __init__(self, busy: bool = False) -> None:
        super().__init__("take line busy" if busy else "take claim fenced")
        self.busy = busy


async def _vq_admit_shielded(request: SubmitRequest, owner: str, generation: str) -> tuple[str, Any]:
    """w47-u1 item 2 (cr51 H12): the admission thread is shielded, so a request cancellation can never separate its
    COMMIT from its return: when the request is cancelled meanwhile, the thread is still waited for, and once it has
    returned the starter is woken (in memory) whenever the line holds the take, before the cancellation goes on."""
    task = asyncio.ensure_future(asyncio.to_thread(_vq_admit_or_start, request, owner, generation))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except BaseException:  # noqa: BLE001 - no decision was committed
                break
        try:
            kind, _row = task.result()
        except BaseException:  # noqa: BLE001
            kind = None
        if kind in ("preparing", "start", "replay"):
            _vq_claims_here().discard(generation)  # this request is gone: its starting row is the line's to recover
            _vq_wake()
        raise


async def _vq_direct_submit(request: SubmitRequest, _started: Any = None) -> dict[str, Any]:
    owner, generation = _vq_owner_token(), uuid.uuid4().hex
    here = _vq_claims_here()
    here.add(generation)  # before the row exists: recovery in this process never takes back this live take
    committed = False
    try:
        try:
            kind, row = await _vq_admit_shielded(request, owner, generation)
        except _VideoLineFull:
            return _v4_named("queue_full", _VQ_SUBMIT_PREFIX)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - invariant 3: no decision (busy, unreadable): refused, never sent directly
            return _vq_busy_answer()
        committed = kind in ("preparing", "start")
        if kind == "conflict":
            return _v4_named("request_id_conflict", None)
        if kind == "replay":
            # w47-u1 item 2: an exact replay that answers an outstanding take (waiting or starting) wakes the starter.
            if row is not None and row.get("state") in ("waiting", "starting"):
                _vq_wake()
            return _vq_receipt(row)
        if kind == "preparing":
            try:
                refusal = await asyncio.to_thread(_vq_prepare_waiting, request, row)
            except Exception:  # noqa: BLE001 - after COMMIT the committed decision answers: the take waits
                refusal = None  # (its preparation is fenced past the deadline and done by its claimant, invariant 4)
            if refusal is not None:
                return refusal
            _job_authors_note([row["studio_job_id"]], row["by"])  # the take is its sender's from the start (FRM-024)
            try:
                current = await asyncio.to_thread(_vq_get, row["studio_job_id"])
            except Exception:  # noqa: BLE001
                current = None
            return _vq_receipt(current or row)
        return await _vq_start_direct(request, row)
    except BaseException:
        if committed:  # an error or a cancellation after COMMIT: the take is the line's; wake (in memory, never busy)
            here.discard(generation)
            _vq_wake()
            committed = False
        raise
    finally:
        here.discard(generation)
        # w47-t1 item 4 (cr50 H10): a committed admission (waiting or starting) wakes the starter on every way out:
        # success, busy, any error, cancellation. A normal return wakes when the line still holds work (the refused
        # take was dropped: nothing to start); a starting row whose submit did not reach the ledger is no longer a
        # live claim of this process now, so the starter's recovery hands it to the line at its place and starts it.
        if committed:
            _vq_wake_if_work()


async def _vq_start_direct(request: SubmitRequest, row: Mapping[str, Any]) -> dict[str, Any]:
    """Submit a take written down as starting by this process under its reserved id; settle its line row after."""
    job_id = row["studio_job_id"]
    claim = {"owner": row["owner"], "claim_generation": row["claim_generation"]}
    reserved = _VQ_RESERVED.set((request.client_request_id, job_id, claim))
    result: Any = None
    try:
        result = await _v4_submit_route_before_line(request)
    except Exception:  # noqa: BLE001 - w47-t1 item 4: after COMMIT the committed decision answers: the take is the
        # line's; the starter (woken by the caller) decides it: ledgered -> started, else at its place, then started.
        return _vq_receipt({**row, "position": None})
    finally:
        _VQ_RESERVED.reset(reserved)
    try:
        return await _vq_after_direct(request, row, result)
    except Exception:  # noqa: BLE001 - invariant 3: after COMMIT the committed decision answers, never a second path
        details = result.get("details") if isinstance(result, dict) else None
        if isinstance(details, Mapping) and details.get("id") == job_id:
            return result  # it reached the ledger; recovery marks its line row started
        return _vq_receipt({**row, "position": None})  # still the line's take; recovery decides it


async def _vq_after_direct(request: SubmitRequest, row: Mapping[str, Any], result: Any) -> Any:
    """Settle a direct take's line row from its submit's outcome (the committed starting decision)."""
    job_id = row["studio_job_id"]
    claim = {"owner": row["owner"], "claim_generation": row["claim_generation"]}
    details = result.get("details") if isinstance(result, dict) else None
    if isinstance(result, dict) and result.get("fenced"):
        # Invariant 2: fenced before its ledger row (recovery put it back or settled its cancel): nothing was sent.
        current = await asyncio.to_thread(_vq_get, job_id)
        return _vq_receipt(current) if current is not None else _vq_busy_answer()
    if isinstance(details, Mapping) and details.get("id") == job_id:
        await asyncio.to_thread(_vq_finish, job_id, "started", None, None, claim)  # the ledger answers from now on
        await _vq_settle_cancel(job_id, row.get("project_id"))  # a cancel that came while it was being sent
    elif isinstance(result, dict) and result.get("reason_code") == "provider_busy" and details is None:
        # Work outside the line holds the engine: this take waits at its place instead, validated as it will start.
        started, refusal = await asyncio.to_thread(_vq_validated, request)
        if refusal is not None:
            await asyncio.to_thread(_vq_drop_direct, job_id, request.client_request_id, claim)
            return refusal
        await asyncio.to_thread(_vq_write, "UPDATE video_line SET request_json = ?, requested_basename = ?"
                                " WHERE studio_job_id = ? AND state = 'starting' AND owner IS ? AND claim_generation IS ?",
                                (json.dumps(started.model_dump(mode="json")), started.requested_basename, job_id,
                                 claim["owner"], claim["claim_generation"]))
        if await asyncio.to_thread(_vq_release, job_id, claim):
            _job_authors_note([job_id], row["by"])
            _vq_wake()
            current = await asyncio.to_thread(_vq_get, job_id)
            result = _vq_receipt(current) if current is not None else result
    else:
        # Refused (or broken) before a ledger row of its own: the line keeps nothing of it; the refusal answers.
        await asyncio.to_thread(_vq_drop_direct, job_id, request.client_request_id, claim)
    return result


def _vq_drop_direct(job_id: str, client_request_id: str, claim: Mapping[str, Any]) -> None:
    """A direct take refused before a ledger row of its own: the line keeps nothing of it. Only a row that never got
    its ledger row (submit_started < 2) and has no unsettled cancel is deleted (invariant 1); one with a cancel ends
    removed with it settled (proven never sent: its submit returned without a ledger row, invariant 2)."""
    try:
        if _read_client_row(client_request_id) is not None:
            _vq_finish(job_id, "started", None, None, claim)
            return
    except Exception:  # noqa: BLE001 - unreadable ledger: recovery decides later (the row is the dead claim's)
        return
    guard = (job_id, claim.get("owner"), claim.get("claim_generation"))
    where = " WHERE studio_job_id = ? AND state = 'starting' AND submit_started < 2 AND owner IS ? AND claim_generation IS ?"
    _vq_write(_VQ_NEVER_SENT_SQL + where + " AND " + _VQ_UNSETTLED, (time.time(), *guard), prune=True)
    _vq_write("DELETE FROM video_line" + where + " AND NOT " + _VQ_UNSETTLED, guard)
