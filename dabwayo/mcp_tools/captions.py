"""Caption / subtitle / lower-third tools.

``add_captions`` imports an SRT or WebVTT file (or string) and lays each cue
onto the timeline as a styled, legible subtitle text clip (its own track, safe
bottom margin, stroke + shadow). ``add_lower_third`` drops a name/subtitle
title in the lower-left. Both reuse ``add_clip`` so every caption gets a stable
clip id and flows through the same render path as any other clip.
"""
from __future__ import annotations

import os
from typing import Optional

from .app import mcp, _proj
from .clips import add_clip

__all__ = ["add_captions", "add_lower_third", "add_word_captions"]


def _legible_text(text, size, font, color, stroke, stroke_width, max_width, align="center"):
    el = {"type": "text", "text": text, "size": int(size), "font": font,
          "color": color, "align": align,
          "shadow": {"color": "#000000cc", "offset": [0, 3], "blur": 8}}
    if max_width:
        el["max_width"] = int(max_width)
    if stroke:
        el["stroke"] = stroke
        el["stroke_width"] = int(stroke_width)
    return el


@mcp.tool()
def add_captions(project_id: str, srt: Optional[str] = None,
                 path: Optional[str] = None, track: str = "captions",
                 font: str = "sans-bold", size: Optional[int] = None,
                 color: str = "#ffffff", stroke: str = "#000000",
                 stroke_width: int = 3, max_width: Optional[int] = None,
                 bottom_margin: Optional[int] = None, offset: float = 0.0,
                 fade: float = 0.0) -> dict:
    """Import subtitles (SRT or WebVTT) and lay each cue on the timeline as a
    styled subtitle clip.

    Provide the subtitles as ``srt`` (raw text) or ``path`` (a .srt/.vtt file).
    Cues are placed on their own ``track`` (default 'captions'), centered near
    the bottom with a safe margin, white text with a stroke + shadow for
    legibility over any footage. ``size`` / ``max_width`` / ``bottom_margin``
    default to sensible fractions of the canvas. ``offset`` shifts every cue in
    time (to sync against a clip that doesn't start at 0); ``fade`` adds a short
    in/out fade to each cue. Returns the created clip ids."""
    if not srt and not path:
        raise ValueError("provide subtitles via 'srt' (text) or 'path' (file)")
    if path and not srt:
        if not os.path.exists(path):
            raise ValueError(f"subtitle file not found: {path}")
        with open(path, "r", encoding="utf-8-sig") as f:
            srt = f.read()

    from ..captions import parse_captions
    cues = parse_captions(srt)
    if not cues:
        return {"ok": False, "error": "no cues parsed", "count": 0}

    spec = _proj(project_id)
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))
    size = size or max(18, round(h * 0.055))
    max_width = max_width or round(w * 0.8)
    bottom_margin = bottom_margin or round(h * 0.08)
    y = h - bottom_margin
    trans = {"type": "fade", "duration": fade} if fade and fade > 0 else None

    clip_ids = []
    for cue in cues:
        el = _legible_text(cue["text"], size, font, color, stroke, stroke_width, max_width)
        transform = {"position": [round(w / 2), y], "anchor": "bottom"}
        r = add_clip(project_id, el, cue["start"] + offset,
                     cue["end"] - cue["start"], track, transform,
                     None, "normal", trans, trans)
        clip_ids.append(r["clip_id"])
    return {"ok": True, "count": len(clip_ids), "track": track,
            "clip_ids": clip_ids,
            "span": [cues[0]["start"] + offset, cues[-1]["end"] + offset]}


@mcp.tool()
def add_word_captions(project_id: str, words: Optional[list] = None,
                      srt: Optional[str] = None, path: Optional[str] = None,
                      track: str = "captions", group_size: int = 3,
                      font: str = "sans-bold", size: Optional[int] = None,
                      color: str = "#ffffff", stroke: str = "#000000",
                      stroke_width: int = 4, bottom_margin: Optional[int] = None,
                      offset: float = 0.0) -> dict:
    """Lay punchy word-timed "pop-on" captions (Reels/Opus-Clip style): a few
    words at a time appear in sync with speech, one group after another.

    Provide ``words`` as ASR word timestamps — a list of
    ``{"word"/"text","start","end"}`` (e.g. Whisper word output) — OR give
    ``srt``/``path`` line-level subtitles and per-word times are approximated by
    spreading each line's words across its span. ``group_size`` words show at
    once (1 = one word at a time, very punchy; 3 = short phrases). Styled larger
    than normal subtitles, centered near the bottom with stroke + shadow. Every
    group is a stable clip. Returns the clip ids."""
    from ..captions import parse_captions, words_from_cues, group_words
    if not words:
        if not srt and not path:
            raise ValueError("provide 'words' (ASR timestamps) or 'srt'/'path'")
        if path and not srt:
            if not os.path.exists(path):
                raise ValueError(f"subtitle file not found: {path}")
            with open(path, "r", encoding="utf-8-sig") as f:
                srt = f.read()
        words = words_from_cues(parse_captions(srt))
    groups = group_words(words, group_size)
    if not groups:
        return {"ok": False, "error": "no word groups", "count": 0}

    spec = _proj(project_id)
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))
    size = size or max(22, round(h * 0.062))
    bottom_margin = bottom_margin or round(h * 0.10)
    y = h - bottom_margin

    clip_ids = []
    for g in groups:
        el = _legible_text(g["text"], size, font, color, stroke, stroke_width,
                           round(w * 0.86))
        transform = {"position": [round(w / 2), y], "anchor": "bottom"}
        r = add_clip(project_id, el, g["start"] + offset,
                     max(0.05, g["end"] - g["start"]), track, transform)
        clip_ids.append(r["clip_id"])
    return {"ok": True, "count": len(clip_ids), "groups": len(groups),
            "track": track, "clip_ids": clip_ids,
            "span": [groups[0]["start"] + offset, groups[-1]["end"] + offset]}


@mcp.tool()
def add_lower_third(project_id: str, name: str, subtitle: str = "",
                    start: float = 0.0, duration: float = 4.0,
                    track: str = "lower_third", font: str = "sans-bold",
                    color: str = "#ffffff", accent: str = "#ffffff",
                    left_margin: Optional[int] = None,
                    bottom_margin: Optional[int] = None,
                    transition: str = "slide") -> dict:
    """Add a lower-third title (a name with an optional subtitle) in the
    lower-left — the standard "who is speaking" caption.

    ``name`` is the primary line; ``subtitle`` the smaller line under it.
    Placed with a safe left/bottom margin, stroke + shadow for legibility, and
    a short ``transition`` in/out ('slide'|'fade'|'none'). Returns the clip
    ids (name, and subtitle if given)."""
    spec = _proj(project_id)
    w = int(spec.get("width", 1920))
    h = int(spec.get("height", 1080))
    left = left_margin or round(w * 0.06)
    bottom = bottom_margin or round(h * 0.12)
    name_size = max(22, round(h * 0.05))
    sub_size = max(16, round(h * 0.032))
    tin = None if transition == "none" else {"type": transition, "duration": 0.4}
    tout = None if transition == "none" else {"type": transition, "duration": 0.3}

    ids = []
    # subtitle sits below the name; name baseline above it
    if subtitle:
        el_sub = _legible_text(subtitle, sub_size, font, color, "#000000", 2,
                               round(w * 0.5), align="left")
        r = add_clip(project_id, el_sub, start, duration, track,
                     {"position": [left, h - bottom], "anchor": "bottom_left"},
                     None, "normal", tin, tout)
        ids.append(r["clip_id"])
    el_name = _legible_text(name, name_size, font, accent, "#000000", 3,
                            round(w * 0.6), align="left")
    r = add_clip(project_id, el_name, start, duration, track,
                 {"position": [left, h - bottom - round(sub_size * 1.4)],
                  "anchor": "bottom_left"},
                 None, "normal", tin, tout)
    ids.append(r["clip_id"])
    return {"ok": True, "track": track, "clip_ids": ids}
