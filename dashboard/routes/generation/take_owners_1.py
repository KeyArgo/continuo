from __future__ import annotations


def _audio_route_fault(area: str, exc: BaseException) -> JSONResponse:
    """Lane w45-s6 item 2 (P3): what an Audio route answers for an error its own mapping does not know (voice, music,
    stems). A file the route could not read or write is 503 <area>_files_unavailable; anything else is a fault of this
    code: 500 <area>_internal_error. Neither claims the engine is down; no path is answered.
    Lane w45-s19 item 4: the page sentence is neutral (no exception class, no code name); the class goes only to the
    agent ``hint`` and to the log."""
    if isinstance(exc, OSError):
        return JSONResponse(status_code=503, content={"error": {"code": f"{area}_files_unavailable",
                                                                "message": f"A {area} file of this project could not be read or written"}})
    _AUDIO_FAULT_LOG.warning("%s route failed with %s", area, type(exc).__name__, exc_info=exc)
    return JSONResponse(status_code=500, content={"error": {"code": f"{area}_internal_error",
                                                            "message": f"Continuo could not finish this {area} request",
                                                            "hint": f"internal fault in the {area} route: {type(exc).__name__}; see the Hermes log"}})


_AUDIO_FAULT_LOG = __import__("logging").getLogger("film_suite.audio")


# --- Lane w45-s6 item 3 (release run finding P2): a take row left by a dead process never blocks a later take ---
# Music and voice takes run on a worker thread of this process; their ledger row is the one active row the ledger
# allows per connection (local-music / local-voice). generation/take_owner.py records who holds each row (an owner
# file written before the row) and closes, before a new take is admitted and when the takes are listed, every active
# row of the connection whose owner is gone: failed job_lost, shown as take_interrupted. A row a live process holds
# (this one or another Hermes sharing the home) is never closed.

def _take_owner_module() -> Any:
    module = sys.modules.get("film_suite_take_owner")
    if module is None:
        # Executed in plugin_api's namespace: __file__ is dashboard/plugin_api.py.
        spec = importlib.util.spec_from_file_location("film_suite_take_owner", Path(__file__).with_name("generation") / "take_owner.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["film_suite_take_owner"] = module
        spec.loader.exec_module(module)
    return module


def _take_owners(store: Any) -> Any:
    """The owner files of one ledger, beside it (<ledger folder>/take-owners)."""
    return _take_owner_module().TakeOwners(Path(store.path).parent / "take-owners")


def _take_admit(store: Any, connection_id: str, client_request_id: str) -> None:
    """Record this process as the take's owner, then close the connection's rows no live owner holds."""
    owners = _take_owners(store)
    owners.claim(client_request_id)
    _take_interrupted_note(_take_owner_module().settle(store, connection_id, owners))


def _take_settle(store: Any, connection_id: str) -> list[Any]:
    """Close the connection's rows no live owner holds (the takes lists call it before they read the ledger)."""
    try:
        closed = _take_owner_module().settle(store, connection_id, _take_owners(store))
    except Exception:  # noqa: BLE001 - a list still answers; the next admission settles again
        return []
    _take_interrupted_note(closed)
    return closed


def _take_release(store: Any, client_request_id: str) -> None:
    try:
        _take_owners(store).release(client_request_id)
    except Exception:  # noqa: BLE001 - an owner file left behind names a finished row: never closed again
        pass


# The sentence an interrupted take carries (the music takes list's own words since w16-mus) and its Jobs cause.
_TAKE_INTERRUPTED = "The take was stopped"
_TAKE_INTERRUPTED_CAUSE = "The Hermes process that made this take stopped before the take finished"


def _take_interrupted_note(closed: list[Any]) -> None:
    for row in closed:
        _job_cause_note(row.studio_job_id, _TAKE_INTERRUPTED_CAUSE)


# --- Lane w45-s8 item 3: one worker per take queue (music, voice), decided under the queue lock ---
# Asking the thread is_alive() lost a take: a worker that had already found its queue empty was still alive for a
# moment, a take queued then started no worker and stayed waiting for ever (no row, no prompt). Now the worker clears
# the flag itself, under the lock, in the same step in which it finds no waiting take. A take whose start raised ends
# only that take (``failed`` records it); the worker goes on with the next one.

def _take_worker(queue: list, lock: Any, flag: dict, run_one: Any, failed: Any) -> None:
    try:
        while True:
            with lock:
                item = next((entry for entry in queue if entry["state"] == "waiting"), None)
                if item is None:
                    flag["active"] = False
                    return
                item["state"] = "started"
            try:
                run_one(item)
            except Exception as exc:  # noqa: BLE001 - this take only; the next one still runs
                failed(item, exc)
            finally:
                with lock:
                    queue.remove(item)
    except BaseException:
        with lock:
            flag["active"] = False
        raise


def _take_wake(lock: Any, flag: dict, threads: list, worker: Any, name: str, stale: Any = None) -> None:
    """Start the queue's worker unless one is active. w47-t1 item 3 (cr50 H9): ``stale`` (the video line) names an
    active worker whose heartbeat is older than its deadline: a replacement starts under a new epoch, and the old one
    leaves at its next look (its claims are fenced by recovery; its late writes miss)."""
    with lock:
        if flag["active"] and not (stale is not None and stale()):
            return
        thread = threading.Thread(target=worker, name=name, daemon=True)
        if stale is None:
            threads[:] = [thread]
        else:
            flag["epoch"] = flag.get("epoch", 0) + 1
            flag["beat"] = time.time()
            thread.take_epoch = flag["epoch"]
            threads[:] = [thread] + [old for old in threads if old.is_alive()]
        flag["active"] = True
        try:
            thread.start()
        except BaseException:
            flag["active"] = False
            raise


def _take_start_failed(failed: dict, lock: Any, item: dict, exc: BaseException | None, keep: int = 64) -> None:
    """A take whose start failed before it had a ledger row: kept (by its request id) with its cause, so the takes
    list names it failed instead of the take vanishing while its caller waits."""
    item["error"] = item.get("error") or "The take could not be started"
    if exc is not None:  # w45-s19 item 4: the class goes to the log, never into the listed sentence
        _AUDIO_FAULT_LOG.warning("take %s could not be started: %s", item.get("client_request_id"), type(exc).__name__, exc_info=exc)
    with lock:
        failed[item["client_request_id"]] = {**item, "state": "failed", "error": item["error"]}
        for key in list(failed)[:-keep]:
            failed.pop(key, None)
