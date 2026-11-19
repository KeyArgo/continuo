"""One line of caller-supplied text inside a refusal (lane w45-s11, cold review of s10: High 3, Medium 1, Medium 2).

A refusal that echoes what the caller sent (a key, an id, a field name, a folder, a project name) must stay one line of
bounded length: a key ``bad\\nINJECTED`` made a second, misleading line in an agent-visible refusal, and a long folder
pushed the artist's way out of a 600-character message. ``one_line`` is the one sanitiser every such refusal uses:
control, format (bidi marks such as U+202E), surrogate and line/paragraph separator characters and the listed zero-width
code points (w45-s14, see _ZERO_WIDTH_RANGES) become a space, and the
text is cut to ``limit`` characters ending with an ellipsis. Stdlib only, touches nothing; loaded by file path
(like local_path.py) by routes/shared, generation/ and voice/ modules.
"""
from __future__ import annotations

import unicodedata
from typing import Any

_HIDDEN = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
# Lane w45-s14 item 3 (cold review of s11, Medium): the explicit zero-width policy. Besides the categories above, these
# default-ignorable code points are not legitimate text in an echoed key, id, folder or name and become a space, whatever
# their category (U+034F COMBINING GRAPHEME JOINER is Mn and passed s11's filter): U+034F, the Hangul fillers U+115F/U+1160,
# U+3164 and U+FFA0, the Khmer inherent vowels U+17B4/U+17B5, the Mongolian selectors and vowel separator U+180B-U+180F,
# U+200B-U+200F (ZWJ U+200D included: refusal echoes are keys and names, not emoji prose), U+2060-U+206F, U+FEFF and the
# tag block U+E0000-U+E0FFF (tags and the supplementary variation selectors). Kept on purpose: ordinary combining marks
# (e + U+0301 stays readable) and the text/emoji variation selectors U+FE0E/U+FE0F.
_ZERO_WIDTH_RANGES = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x200B, 0x200F),
                      (0x2060, 0x206F), (0x3164, 0x3164), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xE0000, 0xE0FFF))
_KEPT = frozenset({0xFE0E, 0xFE0F})
ELLIPSIS = "\u2026"


def _hidden(ch: str) -> bool:
    point = ord(ch)
    if point in _KEPT:
        return False
    return unicodedata.category(ch) in _HIDDEN or any(low <= point <= high for low, high in _ZERO_WIDTH_RANGES)


def one_line(value: Any, limit: int = 120) -> str:
    """``value`` as text: hidden characters -> spaces, at most ``limit`` characters (cut ends with an ellipsis)."""
    text = "".join(" " if _hidden(ch) else ch for ch in str(value))
    if limit < 1:
        return ""
    return text if len(text) <= limit else text[: limit - 1] + ELLIPSIS


def fit(head: str, tail: str, limit: int) -> str:
    """``head + tail`` within ``limit`` characters; ``head`` is cut first, so ``tail`` (the way out) always survives."""
    room = limit - len(tail)
    if room <= 0:
        return tail[:limit]
    return (head if len(head) <= room else head[: max(room - 1, 0)] + ELLIPSIS) + tail


__all__ = ["ELLIPSIS", "fit", "one_line"]
