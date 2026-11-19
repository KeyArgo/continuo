"""Free ComfyUI's graphics memory after Continuo's own work has gone idle (lane w47-q2).

ComfyUI keeps every model it loaded in graphics memory until it is told otherwise. Every place where Continuo POSTs a
prompt calls ``note_engine_use()``; the first call starts one watcher thread per process (daemon). Every
``CHECK_SECONDS`` it asks ComfyUI and unloads ONCE (``POST /free {unload_models, free_memory}``) when all hold:

a. Continuo used ComfyUI since the last unload (never anyone else's models alone);
b. the plugin setting ``unload_after_minutes`` (default 10, 0 = never, at most 1440) is above 0;
c. ComfyUI's queue is empty (``GET /queue``: nothing running, nothing waiting, whoever queued it);
d. the newest history entry (``GET /history?max_items=1``) ended (success, error or interrupt) at least that many
   minutes ago, whoever ran it (ms). Unreadable = no unload (fail closed).

Then the mark is cleared and the watcher ends until the next use. Any error (no answer, bad JSON) = nothing this
round. The address is Continuo's own (comfy_endpoint). No watcher in the test session (switch NO_PROBE_ENV set) or without
Hermes; tests drive ``round_once`` with fakes. Stdlib only, loaded by path; ONE process-wide holder for the state.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import types
from pathlib import Path
from typing import Any, Callable

_endpoint_spec = importlib.util.spec_from_file_location("film_suite_comfy_endpoint", Path(__file__).with_name("comfy_endpoint.py"))
_endpoint = importlib.util.module_from_spec(_endpoint_spec)
_endpoint_spec.loader.exec_module(_endpoint)

SETTING_KEY = "unload_after_minutes"
_FINISHED = ("execution_success", "execution_error", "execution_interrupted")
DEFAULT_MINUTES = 10
MAX_MINUTES = 1440
CHECK_SECONDS = 30.0
HTTP_TIMEOUT_SECONDS = 10.0
FREE_BODY = {"unload_models": True, "free_memory": True}

_STATE = sys.modules.setdefault("film_suite_engine_idle_state", types.ModuleType("film_suite_engine_idle_state"))
if not hasattr(_STATE, "lock"):
    _STATE.lock = threading.Lock()
    _STATE.used = False  # Continuo queued work on ComfyUI since the last unload
    _STATE.used_at = None  # monotonic time of the last use
    _STATE.generation = 0  # counts uses: a use during a round keeps the mark
    _STATE.running = False  # one watcher per process


def valid_minutes(value: Any) -> int | None:
    """A whole number of minutes from 0 to MAX_MINUTES, else None (never a bool, never text)."""
    if type(value) is int and 0 <= value <= MAX_MINUTES:
        return value
    return None


def minutes_setting() -> int | None:
    """The saved minutes (unset = DEFAULT_MINUTES); None when the saved value is unusable (then nothing unloads)."""
    saved = _endpoint.plugin_setting(SETTING_KEY)
    return DEFAULT_MINUTES if saved is None else valid_minutes(saved)


def used() -> bool:
    return bool(_STATE.used)


def watcher_running() -> bool:
    return bool(_STATE.running)


def reset() -> None:
    """Forget the mark and the watcher flag (tests)."""
    with _STATE.lock:
        _STATE.used, _STATE.used_at, _STATE.running = False, None, False


def watch_allowed() -> bool:
    """Never in the test session (switch comfy_endpoint.NO_PROBE_ENV set) and never without Hermes in the process."""
    if os.environ.get(_endpoint.NO_PROBE_ENV, ""):
        return False
    try:
        return importlib.util.find_spec("hermes_cli") is not None
    except (ImportError, ValueError):
        return False


def note_engine_use() -> None:
    """Continuo just sent a prompt to ComfyUI. Never raises into the caller."""
    try:
        with _STATE.lock:
            _STATE.used, _STATE.used_at = True, time.monotonic()
            _STATE.generation += 1
        if watch_allowed():
            ensure_watcher()
    except Exception:  # noqa: BLE001 - freeing memory is a help, never a failure of the job
        pass


def ensure_watcher(factory: Callable[..., Any] = threading.Thread) -> bool:
    """Start the watcher unless one runs in this process; True when this call started it."""
    with _STATE.lock:
        if _STATE.running:
            return False
        _STATE.running = True
    try:
        factory(target=_watch, name="continuo-engine-idle", daemon=True).start()
    except Exception:  # noqa: BLE001
        with _STATE.lock:
            _STATE.running = False
        return False
    return True


def _finished_ms(history: Any) -> int | None:
    """The finish timestamp (ms) of the newest history entry, or None when it cannot be read."""
    entry = list(history.values())[-1] if isinstance(history, dict) and history else None
    status = entry.get("status") if isinstance(entry, dict) else None
    messages = status.get("messages") if isinstance(status, dict) else None  # success, error or interrupt ends it
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if isinstance(message, (list, tuple)) and len(message) == 2 and message[0] in _FINISHED:
            stamp = message[1].get("timestamp") if isinstance(message[1], dict) else None
            return stamp if type(stamp) in (int, float) and stamp > 0 else None
    return None


def _queue_count(queue: Any) -> int | None:
    running, pending = (queue.get("queue_running"), queue.get("queue_pending")) if isinstance(queue, dict) else (None, None)
    if not isinstance(running, list) or not isinstance(pending, list):
        return None
    return len(running) + len(pending)


def round_once(*, get: Callable[[str], Any], post: Callable[[str, dict], Any], now_ms: float, minutes: Any) -> str:
    """One look. Answers unused | off | error | unreadable | busy | recent | unloaded; never raises."""
    with _STATE.lock:
        if not _STATE.used:
            return "unused"
        generation = _STATE.generation
    limit = valid_minutes(minutes)
    if not limit:
        return "off"
    try:
        count = _queue_count(get("/queue"))
        if count is None:
            return "unreadable"
        if count:
            return "busy"
        finished = _finished_ms(get("/history?max_items=1"))
        if finished is None or finished > now_ms:
            return "unreadable"
        if now_ms - finished < limit * 60_000:
            return "recent"
        post("/free", dict(FREE_BODY))
    except Exception:  # noqa: BLE001 - no answer or bad JSON: nothing this round
        return "error"
    with _STATE.lock:
        if _STATE.generation == generation:
            _STATE.used = False
    return "unloaded"


def watch_step(*, get: Callable[[str], Any], post: Callable[[str, dict], Any], now_ms: float, minutes: Any) -> bool:
    """One round of the watcher; False when the watcher ends (nothing of Continuo's left to free)."""
    round_once(get=get, post=post, now_ms=now_ms, minutes=minutes)
    with _STATE.lock:
        _STATE.running = bool(_STATE.used)
        return _STATE.running


def _read(response: Any) -> Any:
    body = response.read(4 << 20)  # bad JSON raises: nothing this round
    return json.loads(body) if body[:1] in (b"{", b"[") else None


def _http_get(path: str) -> Any:
    with _endpoint._opener.open(_endpoint.comfy_origin() + path, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
        return _read(response)


def _http_post(path: str, payload: dict) -> Any:
    import urllib.request
    request = urllib.request.Request(_endpoint.comfy_origin() + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with _endpoint._opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310 - no redirect
        return _read(response)


def _watch(sleep: Callable[[float], None] = time.sleep) -> None:
    """The watcher: one round every CHECK_SECONDS; an error waits for the next round, never a tight loop."""
    keep = True
    while keep:
        sleep(CHECK_SECONDS)
        try:
            keep = watch_step(get=_http_get, post=_http_post, now_ms=time.time() * 1000, minutes=minutes_setting())
        except Exception:  # noqa: BLE001 - never an exception out of the thread
            keep = True

