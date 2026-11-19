"""Per-clip framing, the pure numbers (lane w46-d, issue #4): no imports outside the standard library, so the
export (timeline_export/frame_chain.py) loads it by path like speed_curve.py. Twin: src/timeline/ops/timeline-frame.js.

``frame {fit?, zoom, x, y, move?}`` is documented in ops_frame.py. ``value_at`` is the whole-permille value a split
hands on; ``progress`` is the exact share of a move on a record frame that the viewer and the export draw.
A split clip's ``move.part {at, of}`` (lane w47-p3) makes it show frames ``at ..`` of the original ``of``-frame move.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

FITS = ("fit", "fill", "stretch")  # the same three as schema.FITS (test_timeline_frame_export checks it)
ZOOM_MIN, ZOOM_MAX = 1000, 8000
SHIFT_MAX = 1000
FRAME_EASES = ("linear", "smooth")
NEUTRAL = {"zoom": 1000, "x": 0, "y": 0}


def check_frame(value: Any, path: str, duration: int | None = None) -> str | None:
    """Why ``value`` is not a valid clip frame (None when it is). Shared by the schema; ``duration`` (the clip's
    frames, when given) bounds ``move.part``."""
    if type(value) is not dict:
        return f"{path}: must be an object"
    keys = set(value)
    if "part" in value and "move" not in value:
        return f"{path}.part: a part belongs to a move, and this clip has no move"
    if not {"zoom", "x", "y"} <= keys or keys - {"fit", "zoom", "x", "y", "move"}:
        return f"{path}: holds zoom, x, y and optionally fit and move"
    if "fit" in value and (type(value["fit"]) is not str or value["fit"] not in FITS):
        return f"{path}.fit: must be one of " + "|".join(FITS)
    for name, part in (("", value), (".move", value.get("move"))):
        if name and "move" not in value:
            continue
        if name:
            if type(part) is not dict or set(part) - {"part"} != {"zoom", "x", "y", "ease"}:
                return f"{path}.move: holds zoom, x, y, ease and optionally part"
            if type(part["ease"]) is not str or part["ease"] not in FRAME_EASES:
                return f"{path}.move.ease: must be one of " + "|".join(FRAME_EASES)
            if "part" in part:
                why = _part(part["part"], path + ".move.part", duration)
                if why:
                    return why
        why = _values(part, path + name)
        if why:
            return why
    return None


def _part(part: Any, path: str, duration: int | None) -> str | None:
    if type(part) is not dict or set(part) != {"at", "of"}:
        return f"{path}: holds at and of"
    at, of = part["at"], part["of"]
    if type(at) is not int or type(of) is not int or at < 0 or of < 1:
        return f"{path}: at is a whole number from 0 and of a whole number from 1"
    if type(duration) is int and at + duration > of:
        return f"{path}: the clip's {duration} frames from frame {at} run past the move's {of} frames"
    return None


def _values(part: dict[str, Any], path: str) -> str | None:
    if type(part["zoom"]) is not int or not ZOOM_MIN <= part["zoom"] <= ZOOM_MAX:
        return f"{path}.zoom: must be an integer in {ZOOM_MIN}..{ZOOM_MAX}"
    for key in ("x", "y"):
        if type(part[key]) is not int or not -SHIFT_MAX <= part[key] <= SHIFT_MAX:
            return f"{path}.{key}: must be an integer in {-SHIFT_MAX}..{SHIFT_MAX}"
    return None


def _round_half_up(num: int, den: int) -> int:
    return (2 * num + den) // (2 * den)


def value_at(start: int, end: int, ease: str, k: int, duration: int) -> int:
    """The value on frame ``k`` (0-based) of a move from ``start`` (frame 0) to ``end`` (frame
    ``duration - 1``), rounded half up to a whole permille. linear: t = k / (D - 1);
    smooth: 3 t^2 - 2 t^3 (smoothstep)."""
    if duration <= 1 or k <= 0:
        return start
    if k >= duration - 1:
        return end
    n = duration - 1
    if ease == "smooth":
        return start + _round_half_up((end - start) * (3 * k * k * n - 2 * k * k * k), n * n * n)
    return start + _round_half_up((end - start) * k, n)


def progress(ease: str, k: int, duration: int) -> Fraction:
    """The share (0..1) of a move on record frame ``k`` of ``duration`` (frames past either end hold)."""
    if duration <= 1 or k <= 0:
        return Fraction(0)
    if k >= duration - 1:
        return Fraction(1)
    t = Fraction(k, duration - 1)
    return 3 * t * t - 2 * t * t * t if ease == "smooth" else t


# A split keeps the ORIGINAL move (lane w47-p3, #8): ``move.part {at, of}`` says this clip shows frames
# ``at .. at + duration - 1`` of a move that runs ``of`` frames; zoom/x/y and move.zoom/x/y stay the original
# start and end values. Without ``part`` a move runs over the clip itself (``at`` 0, ``of`` = its duration).

def part_span(move: dict[str, Any] | None, offset: int, whole: int) -> tuple[int, int]:
    """(frame index in the move, the move's frames) for frame ``offset`` of a ``whole``-frame clip."""
    part = (move or {}).get("part")
    return (part["at"] + offset, part["of"]) if part else (offset, whole)


def values_at(frame: dict[str, Any], k: int, duration: int) -> dict[str, int]:
    """zoom, x, y (whole permille) of a clip's frame on its record frame ``k`` (0-based) of ``duration``."""
    move = frame.get("move")
    if move is None:
        return {key: frame[key] for key in NEUTRAL}
    index, whole = part_span(move, k, duration)
    return {key: value_at(frame[key], move[key], move["ease"], index, whole) for key in NEUTRAL}


def progress_of(frame: dict[str, Any], k: int, duration: int) -> Fraction:
    """The exact share of the move on the clip's record frame ``k`` (0 without a move)."""
    move = frame.get("move")
    if move is None:
        return Fraction(0)
    index, whole = part_span(move, k, duration)
    return progress(move["ease"], index, whole)


def rebase(frame: dict[str, Any], duration: int) -> dict[str, Any]:
    """A frame with ``move.part`` as a move of its own: start and end become the values on this clip's first and
    last frame (whole permille), ``part`` is dropped. Any other frame comes back unchanged."""
    move = frame.get("move")
    if move is None or "part" not in move:
        return frame
    out = {key: value for key, value in frame.items() if key != "move"}
    out.update(values_at(frame, 0, duration))
    out["move"] = {**values_at(frame, duration - 1, duration), "ease": move["ease"]}
    return out


def part_fits(frame: Any, duration: int) -> bool:
    """False when a clip's ``move.part`` no longer holds its ``duration`` frames (an edit moved an edge past it)."""
    part = ((frame or {}).get("move") or {}).get("part")
    return part is None or (part["at"] >= 0 and part["at"] + duration <= part["of"])
