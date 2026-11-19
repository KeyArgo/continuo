from __future__ import annotations

# --- w47-u1 (cold review IL/w47-r8-COLDREVIEW.md H11): the ENGINE is the truth, not the clock ---------------------------
# Loaded after video_line_worker_1.py (same namespace). A timer only decides when to LOOK; what happened is decided by
# what ComfyUI lists under the take's marker (extra_data.studio.client_request_id), and a late send is undone there.
# - The sender binds its prompt id by ONE conditional ledger move (JobStore.bind_unsent_v4: only a row still sending).
#   When that fails because the row was given up or cancelled meanwhile, the sender cancels its own prompt on ComfyUI at
#   once (_v4_bind_or_stop) and the row's cause says so.
# - A sending row (handed to ComfyUI, no prompt id) is never ended without a durable TOMBSTONE (marker, studio job id,
#   given-up time) written first (_v4_give_up_sending). Every recovery pass (the starter's step, /poll, the Jobs list,
#   Hermes' start through the starter) looks the live tombstones up in ComfyUI's queue and history by marker
#   (_vq_tomb_pass); a found prompt is cancelled on the engine and the row notes it. Tombstones expire after 24 hours.
# - A pending line cancel is settled against such a given-up row only together with its tombstone (_vq_ledger_ended).
# w47-v1 (cold review IL/w47-r9-COLDREVIEW.md): this is BEST-EFFORT cleanup of late copies, not a guarantee. A late copy
# may run before Hermes sees it; one that already finished cannot be undone; one outside 24 hours or the last 100
# history entries can be missed; a later take can reach ComfyUI before an earlier delayed one.
# - H14: only a definite "no such ledger row" (JobNotFoundError) counts as "nothing owns this prompt". Any other ledger
#   read error decides nothing: the tombstone stays live, no engine call, no note; the next pass looks again.
# - H15: while live tombstones exist, one low-rate watcher per process (_vq_tomb_watch) runs a pass every 15 s and
#   ends when none is live; an engine that does not answer is looked at again after the same interval.

_VQ_TOMB_KEEP_SECONDS = 24 * 3600.0  # how long a given-up take's late copy is looked for
_VQ_TOMB_LOOK_SECONDS = 15.0  # at most one engine look per process within this time (a timer decides when to look only)
_VQ_TOMB_STATE: dict[str, Any] = {"looked": 0.0}
_VQ_TOMB_WATCH_SECONDS = 15.0  # the watcher's interval while live tombstones exist
V4_LATE_COPY_STOPPED = "A late copy of this take reached ComfyUI and was stopped while it was still waiting or running."
V4_LATE_COPY_ENDED = ("A late copy of this take reached ComfyUI after it was given up and had already ended there; that cannot"
                      " be undone, and its output stays in ComfyUI. Hermes did not publish it.")
V4_LATE_COPY_PENDING = ("A late copy of this take reached ComfyUI; stopping it did not succeed yet. Hermes tries again while it"
                        " is running and ComfyUI answers, for up to 24 hours after the take was given up.")


def _vq_tomb_connect() -> sqlite3.Connection:
    connection = _vq_connect()
    connection.execute("CREATE TABLE IF NOT EXISTS take_tombstones (client_request_id TEXT PRIMARY KEY,"
                       " studio_job_id TEXT NOT NULL, given_up_at REAL NOT NULL, stopped_prompt_id TEXT, stopped_at REAL)")
    return connection


def _vq_tomb_exec(sql: str, params: tuple[Any, ...]) -> int:
    with _VQ_DB_LOCK:
        connection = _vq_tomb_connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                changed = connection.execute(sql, params).rowcount
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            return changed
        finally:
            connection.close()


def _vq_tomb_write(client_request_id: str, studio_job_id: str) -> None:
    """The durable tombstone of a take about to be given up (idempotent; raises when the store cannot be written).
    w47-v1 H15: the watcher of this process looks for it while it is live."""
    _vq_tomb_exec("INSERT OR IGNORE INTO take_tombstones (client_request_id, studio_job_id, given_up_at) VALUES (?, ?, ?)",
                  (client_request_id, studio_job_id, time.time()))
    _vq_tomb_watch_start()


def _vq_tomb_drop(client_request_id: str) -> None:
    """The take was bound to its own prompt after all: there is nothing to look for."""
    try:
        _vq_tomb_exec("DELETE FROM take_tombstones WHERE client_request_id = ?", (client_request_id,))
    except Exception:  # noqa: BLE001 - a tombstone of a bound take never cancels it (_vq_tomb_pass checks the ledger)
        pass


def _vq_tomb_stopped(client_request_id: str, prompt_id: str) -> None:
    try:
        _vq_tomb_exec("UPDATE take_tombstones SET stopped_prompt_id = ?, stopped_at = ? WHERE client_request_id = ?",
                      (prompt_id, time.time(), client_request_id))
    except Exception:  # noqa: BLE001 - looked up again; a second cancel of a stopped prompt is harmless
        pass


def _vq_tomb_get(client_request_id: str) -> dict[str, Any] | None:
    if not _vq_path().is_file():
        return None
    with _VQ_DB_LOCK:
        connection = _vq_tomb_connect()
        try:
            return _vq_dict(connection.execute("SELECT * FROM take_tombstones WHERE client_request_id = ?",
                                               (client_request_id,)).fetchone())
        finally:
            connection.close()


def _vq_tombs_live() -> list[dict[str, Any]]:
    """Tombstones still looked for (not stopped, younger than 24 hours); expired ones are dropped here."""
    if not _vq_path().is_file():
        return []
    with _VQ_DB_LOCK:
        connection = _vq_tomb_connect()
        try:
            connection.execute("DELETE FROM take_tombstones WHERE given_up_at < ?", (time.time() - _VQ_TOMB_KEEP_SECONDS,))
            return [dict(r) for r in connection.execute(
                "SELECT * FROM take_tombstones WHERE stopped_at IS NULL ORDER BY given_up_at").fetchall()]
        finally:
            connection.close()


def _vq_tomb_any() -> bool:
    try:
        return bool(_vq_tombs_live())
    except Exception:  # noqa: BLE001 - unreadable: the next pass looks again
        return False


def _vq_tomb_maybe() -> bool:
    """w47-v1 (cr61 H14/H15): may live tombstones exist? An unreadable store answers yes (Hermes' start then opens
    the ledger and starts the watcher, which looks again at its low rate); only a readable empty store answers no."""
    try:
        return bool(_vq_tombs_live())
    except Exception:  # noqa: BLE001
        return True


async def _vq_engine_stop(client: Any, prompt_id: str) -> bool:
    """Cancel one prompt on ComfyUI with the cancel route's own helper; an engine without the jobs endpoint gets the
    delete-from-queue + interrupt of that prompt only. Cancelling an ended or cancelled prompt is harmless."""
    try:
        outcome = await _comfy_provider_module.comfy_cancel_v4(client=client, provider_job_id=prompt_id)
        if _v4_outcome_kind(outcome) == "accepted":
            return True
    except Exception:  # noqa: BLE001 - the fallback below, then the next pass
        pass
    interrupt = getattr(client, "interrupt_prompt", None)
    if callable(interrupt):
        try:
            answer = await interrupt(prompt_id)
            return isinstance(answer, Mapping) and answer.get("cancelled") is True
        except Exception:  # noqa: BLE001
            return False
    return False


async def _v4_bind_or_stop(row: Any, project_id: str | None, prompt_id: str, client: Any) -> Any:
    """H11 a: bind the prompt id by one conditional move; when the row was given up or cancelled meanwhile, this
    prompt is a late copy: the sender cancels it on ComfyUI itself, now, and the row's cause says so. Answers the row."""
    bound, current = _comfy_store().bind_unsent_v4(studio_job_id=row.studio_job_id, expected_project_id=project_id,
                                                   provider_job_id=prompt_id)
    if bound:
        return current
    stopped = await _vq_engine_stop(client, prompt_id)
    crid = current.client_request_id
    if stopped:
        _vq_tomb_stopped(crid, prompt_id)
    else:
        try:  # not stopped: the tombstone (written by the give-up, or now) keeps it looked for
            _vq_tomb_write(crid, current.studio_job_id)
        except Exception:  # noqa: BLE001
            pass
    _job_cause_note(current.studio_job_id, V4_LATE_COPY_STOPPED if stopped else V4_LATE_COPY_PENDING)
    return current


async def _vq_tomb_pass(*, force: bool = False) -> list[str]:
    """Look every live tombstone up in ComfyUI's queue and the last 100 history entries by marker. A prompt found for a
    take whose ledger row ended without it, or that has definitely no ledger row, is cancelled on the engine (queued or
    running) or noted (already ended: that cannot be undone); one that is the take's own bound prompt retires its
    tombstone. A ledger that cannot be read decides nothing (w47-v1 H14). Answers the stopped prompt ids."""
    tombs = await asyncio.to_thread(_vq_tombs_live)
    if not tombs:
        return []
    _vq_tomb_watch_start()  # w47-v1 H15: whoever sees a live tombstone makes sure this process keeps looking
    now = time.monotonic()
    if not force and now - float(_VQ_TOMB_STATE.get("looked") or 0.0) < float(_VQ_TOMB_LOOK_SECONDS):
        return []
    _VQ_TOMB_STATE["looked"] = now
    client = _comfy_client_module.ComfyUIClient()
    try:
        queue = await client.queue()
        history = await client.recent_history(max_items=100)
    except Exception:  # noqa: BLE001 - the engine did not answer: nothing is decided, the next pass looks again
        return []
    provider = _comfy_provider_module
    live = set(provider._queue_prompt_ids(queue, "queue_running")) | set(provider._queue_prompt_ids(queue, "queue_pending"))
    stopped: list[str] = []
    for tomb in tombs:
        prompt_id = provider._correlate_prompt_id(queue, history, tomb["client_request_id"])
        if not prompt_id:
            continue
        try:
            record = await asyncio.to_thread(_read_ledger_row, tomb["studio_job_id"])
        except _comfy_job_store_module.JobNotFoundError:  # definitely no ledger row: nothing owns this prompt
            record = None
        except Exception:  # noqa: BLE001 - w47-v1 H14: unreadable is not missing; nothing is decided, looked at again
            continue
        if record is not None and record.provider_job_id == prompt_id:
            await asyncio.to_thread(_vq_tomb_drop, tomb["client_request_id"])  # the take's own prompt
            continue
        if record is not None and not record.is_terminal:
            continue  # not given up (yet): the lost-submit rule binds it by the same marker
        if prompt_id in live:
            if not await _vq_engine_stop(client, prompt_id):
                _job_cause_note(tomb["studio_job_id"], V4_LATE_COPY_PENDING)
                continue
            note = V4_LATE_COPY_STOPPED
            stopped.append(prompt_id)
        else:
            note = V4_LATE_COPY_ENDED
        await asyncio.to_thread(_vq_tomb_stopped, tomb["client_request_id"], prompt_id)
        _job_cause_note(tomb["studio_job_id"], note)
    return stopped


async def _vq_engine_pass() -> None:
    """The request side's engine pass (every /poll; the Jobs list through _vq_engine_pass_sync): late copies are
    looked up, and a cancel settle whose lease expired or whose process is gone is taken over (H13)."""
    try:
        await _vq_tomb_pass()
    except Exception:  # noqa: BLE001 - the next pass looks again
        pass
    try:
        if _vq_path().is_file():
            if await asyncio.to_thread(_vq_settles_due):
                await asyncio.to_thread(_vq_settle_pending, None, True)
    except Exception:  # noqa: BLE001
        pass


def _vq_engine_pass_sync(timeout: float = 10.0) -> None:
    """From synchronous code (the Jobs list): the same pass on its own thread, waited for at most ``timeout``."""
    try:
        if not (_vq_tomb_any() or _vq_settles_due()):
            return
        _vq_run(_vq_engine_pass(), timeout=timeout)
    except Exception:  # noqa: BLE001 - a hung pass is left on its thread; its writes are fenced
        pass


_poll_route_before_engine = _poll_route


async def _poll_route(request: PollRequest) -> dict[str, Any]:  # noqa: F811
    await _vq_engine_pass()
    return await _poll_route_before_engine(request)


_video_jobs_for_scope_before_engine = _video_jobs_for_scope


def _video_jobs_for_scope(project_id: str | None, limit: int) -> list[dict[str, Any]]:  # noqa: F811
    _vq_engine_pass_sync()
    return _video_jobs_for_scope_before_engine(project_id, limit)


# --- w47-v1 item 2 (cr61 H15): look while there is something to look for ---------------------------------------------
# The starter ends when no line work remains, even with live tombstones; a sender killed right after its POST with no
# later request would leave its copy unlooked-for. One watcher thread per process (process-wide state, like
# _vq_claims_here) runs a tombstone pass every _VQ_TOMB_WATCH_SECONDS while live tombstones exist and ends when none
# is live. It starts with each tombstone written and at Hermes' start. An engine that does not answer: it sleeps the
# same interval and looks again (never a tight loop). An unreadable tombstone store keeps it looking.
def _vq_tomb_watch_state() -> dict[str, Any]:
    holder = sys.modules.setdefault("_film_suite_video_line_state", type(sys)("_film_suite_video_line_state"))
    if not hasattr(holder, "tomb_watch"):
        holder.tomb_watch = {"lock": threading.Lock(), "thread": None, "halt": False}
    return holder.tomb_watch


def _vq_tomb_watcher() -> Any:
    """This process's running watcher thread, or None."""
    thread = _vq_tomb_watch_state()["thread"]
    return thread if thread is not None and thread.is_alive() else None


def _vq_tomb_watch_start() -> None:
    """Start the watcher unless one runs for this ledger (in memory; a failure leaves the request-side passes). A
    watcher of a replaced ledger (a plugin reload, a test) leaves at its next look and never touches the new one."""
    try:
        store = globals().get("_comfy_job_store")
        if store is None:
            return
        state = _vq_tomb_watch_state()
        with state["lock"]:
            if state["halt"] or (_vq_tomb_watcher() is not None and state.get("store") is store):
                return
            thread = threading.Thread(target=_vq_tomb_watch, args=(store,), name="fs-video-tombs", daemon=True)
            state["thread"], state["store"] = thread, store
            thread.start()
    except Exception:  # noqa: BLE001 - the starter, /poll, the Jobs list and a start still look
        pass


def _vq_tomb_watch(store: Any) -> None:
    state = _vq_tomb_watch_state()
    me = threading.current_thread()
    last = time.monotonic()  # the first look comes one interval after the start (the give-up's own caller looks now)

    def mine() -> bool:
        return not state["halt"] and globals().get("_comfy_job_store") is store
    try:
        while mine():
            try:
                live = bool(_vq_tombs_live())
            except Exception:  # noqa: BLE001 - unreadable: look again after the interval
                live = True
            if not live:
                with state["lock"]:
                    if state["thread"] is me:
                        state["thread"] = None
                if _vq_tomb_any():  # written while this watcher was leaving: a new one looks for it
                    _vq_tomb_watch_start()
                return
            due = max(last, float(_VQ_TOMB_STATE.get("looked") or 0.0)) + float(_VQ_TOMB_WATCH_SECONDS)
            while mine() and time.monotonic() < due:
                time.sleep(min(0.05, float(_VQ_TOMB_WATCH_SECONDS)))
            if not mine():
                return
            last = time.monotonic()
            try:
                asyncio.run(asyncio.wait_for(_vq_tomb_pass(), float(_VQ_STEP_SECONDS)))
            except Exception:  # noqa: BLE001 - the engine did not answer: the next interval looks again
                pass
    finally:
        with state["lock"]:
            if state["thread"] is me:
                state["thread"] = None


_vq_stop_before_engine = _vq_stop


def _vq_stop(timeout: float = 10.0) -> None:  # noqa: F811
    """Stop this process's starter and its tombstone watcher and wait for them (plugin unload; a test's end)."""
    state = _vq_tomb_watch_state()
    state["halt"] = True
    try:
        thread = state["thread"]
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
    finally:
        state["halt"] = False
    _vq_stop_before_engine(timeout)
