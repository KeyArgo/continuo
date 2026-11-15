"""The one atomic POSIX rename below pinned parent descriptors (lane w41-mac-a, PR #2 by @ShawnCRMer).

Linux uses ``renameat2``; macOS has no ``renameat2`` and uses ``renameatx_np`` with ``RENAME_EXCL`` /
``RENAME_SWAP``, which give the same no-replace / exchange guarantees.  Callers always pass the Linux flag
values (0, ``RENAME_NOREPLACE``, ``RENAME_EXCHANGE``); the Darwin values are mapped here and never leak out.
Any other platform, or a filesystem without the requested operation, fails closed with ``ENOSYS``.

Stdlib only, no package imports: ``path_boundary.py`` and ``generation/bounded_download.py`` load it by file
path, so the flag mapping and the errno mapping exist once.
"""
from __future__ import annotations

import ctypes
import errno
import os
import sys

RENAME_NOREPLACE = 0x1
RENAME_EXCHANGE = 0x2
# <sys/stdio.h> on macOS: RENAME_SECLUDE 0x1, RENAME_SWAP 0x2, RENAME_EXCL 0x4.
DARWIN_RENAME_SWAP = 0x2
DARWIN_RENAME_EXCL = 0x4
DARWIN_FLAGS = {0: 0, RENAME_NOREPLACE: DARWIN_RENAME_EXCL, RENAME_EXCHANGE: DARWIN_RENAME_SWAP}
# errno values that mean "this filesystem or kernel cannot do the requested operation".  On Linux ENOTSUP and
# EOPNOTSUPP are one value; on macOS they differ (45 / 102) and APFS/HFS answer RENAME_SWAP with ENOTSUP.
UNAVAILABLE_ERRNOS = frozenset(
    {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, getattr(errno, "ENOTSUP", errno.EOPNOTSUPP)}
)


def is_darwin() -> bool:
    """Read at call time, so a test can fake the platform."""
    return sys.platform == "darwin"


def native_rename(flags: int) -> tuple[str, int]:
    """The libc function name and its flag value for one Linux-style ``flags`` value on this platform."""
    if flags not in DARWIN_FLAGS:
        raise ValueError("unsupported rename flags")
    if is_darwin():
        return "renameatx_np", DARWIN_FLAGS[flags]
    return "renameat2", int(flags)


def rename_between_fds(
    source_parent_fd: int,
    source_name: str,
    target_parent_fd: int,
    target_name: str,
    flags: int,
) -> None:
    """One atomic rename of ``source_name`` below one pinned parent to ``target_name`` below another (or the same).

    Raises ``FileExistsError`` when a no-replace target exists, ``OSError(ENOSYS)`` when the platform or the
    filesystem cannot perform the operation, and ``OSError(<errno>)`` for every other failure.
    """
    if os.name == "nt":
        raise RuntimeError("POSIX renameat2 requested on Windows")
    function_name, native_flags = native_rename(flags)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        function = getattr(libc, function_name)
    except (AttributeError, OSError) as exc:
        raise OSError(errno.ENOSYS, f"{function_name} is unavailable") from exc
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    result = function(
        int(source_parent_fd),
        ctypes.c_char_p(os.fsencode(source_name)),
        int(target_parent_fd),
        ctypes.c_char_p(os.fsencode(target_name)),
        int(native_flags),
    )
    if result == 0:
        return
    error = ctypes.get_errno() or errno.EIO
    if error == errno.EEXIST and flags == RENAME_NOREPLACE:
        raise FileExistsError(error, "rename target already exists", target_name)
    if error in UNAVAILABLE_ERRNOS:
        raise OSError(errno.ENOSYS, "requested renameat2 operation is unavailable")
    raise OSError(error, "renameat2 failed", source_name)


__all__ = [
    "DARWIN_FLAGS",
    "RENAME_EXCHANGE",
    "RENAME_NOREPLACE",
    "is_darwin",
    "native_rename",
    "rename_between_fds",
]
