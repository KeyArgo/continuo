"""A picture clip's own framing in the film (lane w46-d, issue #4): fit, zoom, position and one move.

The clip's ``frame {fit?, zoom, x, y, move?}`` (timeline/ops_frame.py) becomes one ffmpeg chain:

1. ``pre``: the source is scaled to its fitted size at the sequence format (fit = inside the frame,
   fill = covering it, stretch = the frame exactly), centred on a canvas that holds both the frame and the
   fitted picture, with a black border of ``BORDER`` pixels;
2. ``post``: ffmpeg ``perspective`` (sense destination, evaluated per frame) sends the canvas's corners to
   the canvas scaled by the zoom about its centre and shifted by x/y, so the picture moves by fractions of
   a pixel (no stepping); outside the picture the black border is repeated; then the frame is cut from
   the canvas's centre.

Record frame ``k`` of the clip (counted over the clip's whole length, ``offset`` included, see PlanClip)
shows the move's share ``progress(ease, k, duration)``: frames before the first or after the last hold.
A split clip's ``move.part {at, of}`` (lane w47-p3) is read by model._clip as offset ``at`` into a move of ``of``
frames, so each part draws exactly the frames of the original move it shows.
A frame with zoom 1000, x 0, y 0 and no move is only a fit, rendered by the cut's own fit chain with the
clip's fit, exactly as a cut-wide fit renders it; a clip without ``frame`` is not touched at all.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Mapping

BORDER = 4
_RANGE = "out_range=tv"


def frame_math():
    """dashboard/timeline/frame_math.py, the one place of the move's numbers (loaded by path, like speed_curve)."""
    name = "film_suite_frame_math"
    if name not in sys.modules:
        path = Path(__file__).resolve().parents[1] / "timeline" / "frame_math.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def read_frame(raw: Any, item_id: str, invalid) -> dict[str, Any] | None:
    """The clip's frame from the document (None when absent); ``invalid(message)`` builds the refusal."""
    if raw is None:
        return None
    why = frame_math().check_frame(raw, f"{item_id}.frame")
    if why:
        raise invalid(why[:1].upper() + why[1:] + ".")
    return dict(raw)


def moves(frame: Mapping[str, Any] | None) -> bool:
    """True when the frame needs the per-frame chain (zoom, position or a move), not only a fit."""
    if not frame:
        return False
    return frame.get("move") is not None or (frame["zoom"], frame["x"], frame["y"]) != (1000, 0, 0)


def fitted_size(width: int, height: int, src_w: int, src_h: int, fit: str) -> tuple[int, int]:
    """The picture's size at the sequence format (even pixels, as the cut-wide fit scales it)."""
    if fit == "stretch":
        return width, height
    if fit == "fill":
        scale_w, scale_h = width * src_h, height * src_w  # compare width/src_w with height/src_h exactly
        if scale_w >= scale_h:
            w, h = width, -(-src_h * width // src_w)
        else:
            w, h = -(-src_w * height // src_h), height
    else:
        if width * src_h <= height * src_w:
            w, h = width, src_h * width // src_w
        else:
            w, h = src_w * height // src_h, height
    return w + (w % 2), h + (h % 2)


def canvas(width: int, height: int, fitted: tuple[int, int]) -> tuple[int, int]:
    """Canvas holding the frame and the fitted picture, plus the black border on every side."""
    return max(width, fitted[0]) + 2 * BORDER, max(height, fitted[1]) + 2 * BORDER


def pre_chain(width: int, height: int, src_w: int, src_h: int, fit: str) -> tuple[str, tuple[int, int]]:
    """Scale to the fitted size and centre on the bordered canvas; returns the chain and the canvas size."""
    fw, fh = fitted_size(width, height, src_w, src_h, fit)
    cw, ch = canvas(width, height, (fw, fh))
    chain = (f"scale={fw}:{fh}:flags=lanczos:{_RANGE},setsar=1,"
             f"pad={cw}:{ch}:{(cw - fw) // 2}:{(ch - fh) // 2}:color=black")
    return chain, (cw, ch)


def _num(value: Any) -> str:
    text = f"{float(value):.9f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def post_chain(width: int, height: int, size: tuple[int, int], frame: Mapping[str, Any], offset: int, duration: int) -> str:
    """Per-frame zoom and shift on the canvas, then the frame cut from its centre (record frame k = offset + in - 1)."""
    cw, ch = size
    move = frame.get("move")
    z0, x0, y0 = frame["zoom"] / 1000, frame["x"] * width / 1000, frame["y"] * height / 1000
    if move is None or duration <= 1:
        z, ox, oy = _num(z0), _num(x0), _num(y0)
        evaluate = "init"
    else:
        z1, x1, y1 = move["zoom"] / 1000, move["x"] * width / 1000, move["y"] * height / 1000
        t = f"clip((in-1+{offset})/{duration - 1}\\,0\\,1)"  # perspective counts in from 1 (measured, ffmpeg 7.1.1)
        p = f"({t}*{t}*(3-2*{t}))" if move["ease"] == "smooth" else f"({t})"
        z = f"({_num(z0)}+{_num(z1 - z0)}*{p})"
        ox = f"({_num(x0)}+{_num(x1 - x0)}*{p})"
        oy = f"({_num(y0)}+{_num(y1 - y0)}*{p})"
        evaluate = "frame"
    left, right = f"{cw / 2:g}+{ox}-{cw / 2:g}*{z}", f"{cw / 2:g}+{ox}+{cw / 2:g}*{z}"
    top, bottom = f"{ch / 2:g}+{oy}-{ch / 2:g}*{z}", f"{ch / 2:g}+{oy}+{ch / 2:g}*{z}"
    corners = {"x0": left, "y0": top, "x1": right, "y1": top, "x2": left, "y2": bottom, "x3": right, "y3": bottom}
    spec = ":".join(f"{key}='{value}'" for key, value in corners.items())
    return (f"perspective={spec}:sense=destination:eval={evaluate}:interpolation=cubic,"
            f"crop={width}:{height}:{(cw - width) // 2}:{(ch - height) // 2},setsar=1,format=yuv420p")


def clip_fit(frame: Mapping[str, Any] | None, plan_fit: str) -> str:
    return (frame or {}).get("fit") or plan_fit


def chain_for(width: int, height: int, src_w: int, src_h: int, frame: Mapping[str, Any], plan_fit: str,
              offset: int, duration: int) -> str:
    """The whole per-clip chain (pre + post) for a clip that moves()."""
    pre, size = pre_chain(width, height, src_w, src_h, clip_fit(frame, plan_fit))
    return f"{pre},{post_chain(width, height, size, frame, offset, duration)}"
