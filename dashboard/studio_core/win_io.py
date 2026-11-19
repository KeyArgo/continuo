"""The one Windows file-sharing retry rule for state files (lane w47-q3).

On Windows a file that another thread or process holds open cannot be replaced, and a file that is being replaced
cannot be opened: both raise PermissionError (WinError 5 ERROR_ACCESS_DENIED or 32 ERROR_SHARING_VIOLATION) for a few
milliseconds. Every atomic ``temp + replace`` writer and every reader of such a file therefore lost reads ("files
unavailable") and, worse, writes (a take that stays "running") under concurrency. The rule here:

* ``replace(src, dst)``: the platform replace; on Windows a PermissionError (or an OSError with winerror 5 or 32) is
  tried again after 1, 2, 4 ... ms (at most ``BUDGET_SECONDS`` of waiting in all), then the last error is raised.
* ``read_bytes(path, limit=None)`` / ``read_text(path, encoding)``: the same rule for opening and reading. A
  FileNotFoundError on the first try, a directory, and every other error are raised at once, never retried. (Measured:
  a reader that met a sharing refusal can next see FileNotFoundError for a moment, the old file delete-pending and the
  new one not yet renamed in; only then, inside the same bounded call, is it tried again.)
* Anywhere else (POSIX) both are the plain calls: a rename there never fails for a reader.

Stdlib only, touches nothing by itself; loaded by file path (like local_path.py, refusal_text.py) by every module that
replaces or reads such a file. Nothing else lives here: no locks, no file formats.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

_WINDOWS = os.name == "nt"
_SHARING_WINERRORS = frozenset({5, 32})  # ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION
# The waits between tries, in seconds: doubling from 1 ms, then 64 ms each (many short tries beat few long ones when
# readers keep a file open most of the time); 1.919 s in all over 36 tries (<= BUDGET_SECONDS).
DELAYS = (0.001, 0.002, 0.004, 0.008, 0.016, 0.032) + (0.064,) * 29
BUDGET_SECONDS = 2.0
_sleep: Callable[[float], None] = time.sleep


def is_sharing_error(exc: BaseException) -> bool:
    """A transient Windows sharing/delete-pending refusal (the only errors that are tried again)."""
    if isinstance(exc, FileNotFoundError):
        return False
    if isinstance(exc, PermissionError):
        return True
    return isinstance(exc, OSError) and getattr(exc, "winerror", None) in _SHARING_WINERRORS


def _retrying(action: Callable[[], Any], path: Any = None) -> Any:
    if not _WINDOWS:
        return action()
    refused = False
    for delay in DELAYS:
        try:
            return action()
        except OSError as exc:
            # A name that is missing on the first try is missing: raised at once. Right after a sharing refusal on the
            # same call it is the replace in flight (the old file delete-pending, the new one not yet renamed in).
            if not (is_sharing_error(exc) or refused and isinstance(exc, FileNotFoundError)):
                raise
            if path is not None and os.path.isdir(path):
                raise  # opening a folder is refused for good, not for a moment
            refused = True
        _sleep(delay)
    return action()


def replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    """``os.replace(src, dst)``, tried again while Windows answers a sharing refusal (see the module docstring)."""
    _retrying(lambda: os.replace(src, dst), dst)


def _path(path: str | os.PathLike[str]) -> Path:
    return path if isinstance(path, Path) else Path(path)  # the caller's own Path object as it is (its flavour kept)


def read_bytes(path: str | os.PathLike[str], limit: int | None = None) -> bytes:
    """The file's bytes (at most ``limit`` when given), tried again while Windows answers a sharing refusal."""
    if limit is None:
        return _retrying(lambda: _path(path).read_bytes(), path)

    def bounded() -> bytes:
        with open(path, "rb") as handle:
            return handle.read(limit)
    return _retrying(bounded, path)


def read_text(path: str | os.PathLike[str], encoding: str = "utf-8") -> str:
    """The file's text, tried again while Windows answers a sharing refusal; decoding errors raise as before."""
    return _retrying(lambda: _path(path).read_text(encoding=encoding), path)


__all__ = ["BUDGET_SECONDS", "DELAYS", "is_sharing_error", "read_bytes", "read_text", "replace"]
