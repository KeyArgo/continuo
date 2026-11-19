"""Per-clip framing in Cut (lane w46-d, issue #4; ``studio.timeline/1.1``).

Twin of ``desktop/film-suite/src/timeline/ops/timeline-frame.js``; the shared fixture suite
``tests/backend/fixtures/timeline/frame.json`` runs against both.

A V1 picture clip (take, picture or footage) may carry ``frame {fit?, zoom, x, y, move?}``:

- ``fit`` (fit | fill | stretch, optional) overrides the cut's ``format.fit`` for this clip only;
- ``zoom`` in permille of the fitted size (1000 = as fitted, 1000..8000);
- ``x``, ``y`` in permille of the frame, the picture's centre from the frame's centre (x right, y down,
  -1000..1000);
- ``move {zoom, x, y, ease linear|smooth}`` (optional) is the value on the clip's LAST frame; the
  clip's own ``zoom/x/y`` is the value on its first. A move always spans the whole clip, so trims,
  fit_to_beats and fit_to_fill keep it valid with no extra rule.

Values are integers so the document stays exact in both twins. A split (lane w47-p3, #8) keeps the
ORIGINAL move on both parts and records which of its frames each part shows: ``move.part {at, of}``
(``of`` the original move's frames, ``at`` the original index of the part's first frame); every frame of
both parts is then exactly the unsplit clip's (frame_math.values_at). A clip without ``part`` runs its move
over itself, exactly as before. A trim of a part's in edge moves ``at`` with it; editing zoom, position or
the move of a part rebases it (its own first and last frame become start and end, ``part`` is dropped), and
so does an edit that leaves the part reaching outside the original move. A frame that says nothing (no fit,
zoom 1000, x 0, y 0, no move) is removed, so a cut without framing stays byte-identical.

``set_frame {clip, fit? (null = the cut's fit), zoom?, x?, y?, move? {zoom?, x?, y?, ease?} | null}``
sets it; keys not given keep their value, a move's missing keys take the clip's start values and
``ease`` defaults to ``smooth``. A slow push-in: ``zoom 1000, move {zoom 1080}``.
"""
from __future__ import annotations

from typing import Any

from .schema import FITS, fail
from .frame_math import (FRAME_EASES, NEUTRAL, SHIFT_MAX, ZOOM_MAX, ZOOM_MIN, check_frame, part_fits,  # noqa: F401
                         part_span, rebase, value_at)  # (schema reads check_frame here)


def _o():
    from . import ops
    return ops


def _tidy(frame: dict[str, Any]) -> dict[str, Any] | None:
    """Drop a move that goes nowhere; None for a frame that says nothing."""
    move = frame.get("move")
    if move is not None and all(move[key] == frame[key] for key in NEUTRAL):
        frame.pop("move")
    if "fit" not in frame and "move" not in frame and all(frame[key] == value for key, value in NEUTRAL.items()):
        return None
    return frame


def split_frame(left: dict[str, Any], right: dict[str, Any], whole: int) -> None:
    """After a split (durations already set): both parts keep the original move; ``part`` names their frames of it."""
    frame = left.get("frame")
    if frame is None or frame.get("move") is None:
        return
    move = frame["move"]
    at, of = part_span(move, 0, whole)
    left["frame"] = {**frame, "move": {**move, "part": {"at": at, "of": of}}}
    right["frame"] = {**frame, "move": {**move, "part": {"at": at + left["duration_frames"], "of": of}}}


def shift_part(item: dict[str, Any], applied: int) -> None:
    """The clip's in edge moved ``applied`` record frames later: its first frame is that much further into the move."""
    part = ((item.get("frame") or {}).get("move") or {}).get("part")
    if part is not None and applied:
        part["at"] += applied


def fix_parts(timeline: dict[str, Any] | None) -> None:
    """After any verb: a part whose clip now reaches outside the original move is rebased onto the clip."""
    for track in (timeline or {}).get("tracks", ()):
        for item in track.get("items") or ():
            if item.get("type") == "clip" and not part_fits(item.get("frame"), item["duration_frames"]):
                tidy = _tidy(rebase(item["frame"], item["duration_frames"]))
                if tidy is None:
                    item.pop("frame")
                else:
                    item["frame"] = tidy


def _shift(value: Any, name: str) -> int:
    return _o()._int(value, name, -SHIFT_MAX, SHIFT_MAX)


def op_set_frame(state, args, ctx):
    o = _o()
    o._args(args, ("clip",), ("fit", "zoom", "x", "y", "move"))
    if not any(key in args for key in ("fit", "zoom", "x", "y", "move")):
        o._bad("set_frame takes fit, zoom, x, y and/or move")
    timeline = o._timeline(state, args)
    track, _index, item = o._picture(timeline, args["clip"])
    if track["role"] != "storyline":
        fail("not_framable", f"{item['id']} is on {track['id']}; framing is for picture clips on V1")
    if item["source"]["kind"] == "cut":
        fail("not_framable", f"{item['id']} is a nested cut; it keeps the framing of its own clips")
    o._unlocked(track)
    frame = dict(item.get("frame") or NEUTRAL)
    if any(key in args for key in ("zoom", "x", "y", "move")):  # lane w47-p3: a part of a split move becomes its own move
        frame = dict(rebase(frame, item["duration_frames"]))
    if "fit" in args:
        if args["fit"] is None:
            frame.pop("fit", None)
        elif type(args["fit"]) is not str or args["fit"] not in FITS:
            o._bad("fit must be " + " | ".join(FITS) + " or null")
        else:
            frame["fit"] = args["fit"]
    if "zoom" in args:
        frame["zoom"] = o._int(args["zoom"], "zoom", ZOOM_MIN, ZOOM_MAX)
    for key in ("x", "y"):
        if key in args:
            frame[key] = _shift(args[key], key)
    if "move" in args:
        move = args["move"]
        if move is None:
            frame.pop("move", None)
        else:
            if type(move) is not dict or set(move) - {"zoom", "x", "y", "ease"}:
                o._bad("move must be {zoom?, x?, y?, ease?} or null")
            old = frame.get("move") or {}
            ease = move.get("ease", old.get("ease", "smooth"))
            if type(ease) is not str or ease not in FRAME_EASES:
                o._bad("move.ease must be " + " | ".join(FRAME_EASES))
            frame["move"] = {
                "zoom": o._int(move.get("zoom", old.get("zoom", frame["zoom"])), "move.zoom", ZOOM_MIN, ZOOM_MAX),
                "x": _shift(move.get("x", old.get("x", frame["x"])), "move.x"),
                "y": _shift(move.get("y", old.get("y", frame["y"])), "move.y"),
                "ease": ease,
            }
    tidy = _tidy({key: frame[key] for key in ("fit", "zoom", "x", "y", "move") if key in frame})
    if tidy is None:
        item.pop("frame", None)
    else:
        item["frame"] = tidy
    return {"op": "set_frame", "clip": item["id"], "frame": None if tidy is None else dict(tidy)}


FRAME_OPS = {"set_frame": op_set_frame}
