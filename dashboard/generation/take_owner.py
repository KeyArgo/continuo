"""Who holds a local take row of the Studio ledger (lane w45-s6 item 3, release-run finding P2).

Music and voice takes run on a worker thread of the Hermes process that queued them; their ledger row
(provider comfyui-local, connection local-music / local-voice) is the one active row the ledger allows per
connection. When that process dies (a kill, a Hermes restart) the row stayed submitting/queued/running forever and
every later take of that kind was refused provider_busy (music) or never started (voice).

The ledger has no owner column, so the owner is recorded beside it: one small file per row, named by the row's
client_request_id and written BEFORE the row exists (no window in which a row has no owner), holding the owner
token ``<pid>:<process start>``. A row is held when
  * its owner is this process: a worker of this process still has it (a process-wide set, so a reloaded plugin
    module sees the rows of the copy that is still running), or
  * its owner is another process that still runs (pid alive AND the same start time, so a reused pid is not it;
    where the start time cannot be read, a live pid counts: fail safe, the row stays), or
  * it has no owner file (a row of an earlier version) and it is younger than this machine's boot and than
    LEGACY_ROW_SECONDS.
Every other active row of the connection is closed failed / job_lost ("Generation job was lost"; Jobs and Dismiss
already read job_lost as interrupted) before a new take is admitted. Several Hermes processes sharing one home each
keep the rows they hold: a row is never closed while its owner runs.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import types
import uuid
from pathlib import Path
# Lane w47-q3: the one Windows file-sharing retry rule for replaced state files (studio_core/win_io.py, stdlib, by path).
import importlib.util as _win_io_import
_win_io_spec = _win_io_import.spec_from_file_location("film_suite_take_owner_win_io", Path(__file__).resolve().parents[1] / "studio_core" / "win_io.py")
_win_io = _win_io_import.module_from_spec(_win_io_spec)
_win_io_spec.loader.exec_module(_win_io)
from typing import Any, Callable, Iterable

LEGACY_ROW_SECONDS = 3600.0
REASON_CODE = "job_lost"
_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


def _holder() -> Any:
    """Process-wide state shared by every copy of this module (a plugin reload loads a new copy)."""
    holder = sys.modules.get("_film_suite_take_owner_state")
    if holder is None:
        holder = sys.modules.setdefault("_film_suite_take_owner_state", types.ModuleType("_film_suite_take_owner_state"))
    if not hasattr(holder, "live"):
        holder.live = set()
        holder.lock = threading.RLock()
    return holder


def process_started(pid: int) -> int | None:
    """The start time of process ``pid`` in the OS's own unit (Windows FILETIME, Linux clock ticks), None if unknown."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.restype = wintypes.HANDLE
            handle = kernel.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return None
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                    return None
                return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            finally:
                kernel.CloseHandle(handle)
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="ascii", errors="replace")
        return int(stat.rsplit(")", 1)[1].split()[19])
    except Exception:  # noqa: BLE001 - unknown is an answer
        return None


def pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def process_token(pid: int | None = None) -> str:
    pid = os.getpid() if pid is None else int(pid)
    return f"{pid}:{process_started(pid) or 0}"


def token_alive(token: Any, *, alive: Callable[[int], bool] = pid_alive, started: Callable[[int], int | None] = process_started) -> bool:
    """Does the process named by ``token`` still run? A malformed token names no process."""
    if type(token) is not str or not re.fullmatch(r"\d{1,10}:\d{1,24}", token):
        return False
    pid, start = (int(part) for part in token.split(":"))
    if not alive(pid):
        return False
    now = started(pid)
    return start == 0 or now is None or now == start


def boot_time() -> float | None:
    """When this machine started (epoch seconds), None if unknown."""
    try:
        if os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32")
            kernel.GetTickCount64.restype = ctypes.c_uint64
            return time.time() - kernel.GetTickCount64() / 1000.0
        return time.time() - float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
    except Exception:  # noqa: BLE001
        return None


class TakeOwners:
    """One owner file per take row, beside the ledger (``<ledger folder>/take-owners/<client_request_id>.json``)."""

    def __init__(self, folder: str | os.PathLike[str]) -> None:
        self.folder = Path(folder)

    def _path(self, client_request_id: str) -> Path | None:
        return self.folder / f"{client_request_id}.json" if isinstance(client_request_id, str) and _SAFE.fullmatch(client_request_id) else None

    def claim(self, client_request_id: str, token: str | None = None) -> None:
        """Record this process as the owner and mark the row live here; called before the row is made."""
        path = self._path(client_request_id)
        if path is None:
            raise ValueError("client_request_id cannot name an owner file")
        holder = _holder()
        with holder.lock:
            holder.live.add(client_request_id)
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps({"owner": token or process_token(), "at": time.time()}), encoding="utf-8")
        _win_io.replace(temporary, path)

    def release(self, client_request_id: str) -> None:
        holder = _holder()
        with holder.lock:
            holder.live.discard(client_request_id)
        path = self._path(client_request_id)
        if path is not None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    def owner(self, client_request_id: str) -> str | None:
        path = self._path(client_request_id)
        if path is None:
            return None
        try:
            body = json.loads(_win_io.read_text(path, encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return body.get("owner") if isinstance(body, dict) and isinstance(body.get("owner"), str) else None


def held(row: Any, owners: TakeOwners, *, me: str | None = None, now: float | None = None, boot: float | None = None,
         alive: Callable[[Any], bool] = token_alive) -> bool:
    """Is this active row held by a live owner? (the rule in the module docstring)"""
    me = me or process_token()
    token = owners.owner(row.client_request_id)
    if token is None:
        stamp = float(getattr(row, "updated_at", 0) or 0)
        now = time.time() if now is None else now
        if boot is not None and stamp < boot:
            return False
        return now - stamp < LEGACY_ROW_SECONDS
    if token == me:
        holder = _holder()
        with holder.lock:
            return row.client_request_id in holder.live
    return bool(alive(token))


def settle(store: Any, connection_id: str, owners: TakeOwners, *, me: str | None = None, now: float | None = None,
           boot: float | None = None, alive: Callable[[Any], bool] = token_alive) -> list[Any]:
    """Close every active row of ``connection_id`` that no live owner holds; answers the closed rows."""
    closed = []
    holder = _holder()
    with holder.lock:
        for row in store.active_rows(connection_id):
            if held(row, owners, me=me, now=now, boot=boot if boot is not None else boot_time(), alive=alive):
                continue
            try:
                closed.append(store.transition(row.studio_job_id, "failed", reason_code=REASON_CODE))
            except Exception:  # noqa: BLE001 - its owner finished it meanwhile
                continue
            owners.release(row.client_request_id)
    return closed


def live_ids() -> Iterable[str]:
    holder = _holder()
    with holder.lock:
        return frozenset(holder.live)
