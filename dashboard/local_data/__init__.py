"""Where this machine's own records live (lane w41-mac-b item 1, PR #2 by @ShawnCRMer, 6b2ee81).

Machine-local records (approved folders, folder grants, job authors, dismissed jobs, review decisions, output
consents, image recipes, the analysis / song-map / scene / stems / speech / subtitles / voice / music caches, posters,
prepared media, model hashes) sit under ``<records_base()>/hermes``; the optional engines under
``<engines_base()>/hermes/film-suite/engines``.

``LOCALAPPDATA`` wins wherever it is set (Windows always sets it).  Without it:
- macOS: ``~/Library/Application Support`` for both.  macOS empties its per-user temp folder, so a record kept there
  (approved folders, who started a job) would be lost.
- elsewhere (Linux): records in the temp folder, engines in ``~/AppData/Local``, exactly as before.

Standalone (stdlib only): loaded by path from every module that keeps a record, like ``dashboard/engine_process``.
The installers under ``scripts/`` run from a bare scripts folder and keep an inline copy of ``engines_base``
(``_machine_local``), tested to answer the same (tests/backend/test_w41_mac_b_local_data.py).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def is_macos() -> bool:
    """``sys.platform`` (not ``os.uname``) so a test can fake the platform; on CPython both say Darwin on a Mac."""
    return sys.platform == "darwin"


def application_support() -> str:
    return os.path.join(os.path.expanduser("~"), "Library", "Application Support")


def records_base() -> str:
    """The parent of ``hermes/`` for machine-local records."""
    return os.environ.get("LOCALAPPDATA") or (application_support() if is_macos() else tempfile.gettempdir())


def engines_base() -> str:
    """The parent of ``hermes/film-suite/engines`` for the optional engines."""
    return os.environ.get("LOCALAPPDATA") or (application_support() if is_macos() else str(Path.home() / "AppData" / "Local"))


__all__ = ["application_support", "engines_base", "is_macos", "records_base"]
