"""Subtitle/caption parsing (SRT + WebVTT) — dependency-light, pure functions.

Turns a subtitle file/string into a list of timed cues that the caption MCP
tool lays onto the timeline as styled text clips. Kept separate from the tool
layer so it is trivially unit-testable.
"""
from __future__ import annotations

import re
from typing import List, Dict

__all__ = ["parse_captions", "parse_timestamp"]

# HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm / MM:SS.mmm (VTT); comma or dot; hours opt.
_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})")
_ARROW = re.compile(r"-->")


def parse_timestamp(ts: str) -> float:
    """Parse a single SRT/VTT timestamp to seconds. Accepts H:MM:SS,mmm,
    HH:MM:SS.mmm or MM:SS.mmm."""
    m = _TS.search(ts)
    if not m:
        raise ValueError(f"bad timestamp: {ts!r}")
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    millis = int(m.group(4).ljust(3, "0"))   # '5' -> 500ms, '50' -> 500ms? pad right
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def parse_captions(text: str) -> List[Dict]:
    """Parse SRT or WebVTT ``text`` into ``[{"start","end","text"}, ...]``.

    Robust to a leading ``WEBVTT`` header, numeric SRT indices, cue settings
    after the timestamp line (VTT), and multi-line cue text (joined with a
    newline). Cues without a valid timestamp line are skipped."""
    # normalise newlines, drop a BOM / WEBVTT header if present
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    cues: List[Dict] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        # find the line holding the "-->" arrow
        ts_idx = next((i for i, ln in enumerate(lines) if _ARROW.search(ln)), None)
        if ts_idx is None:
            continue                                    # header/NOTE/no timing
        left, right = _ARROW.split(lines[ts_idx], 1)
        try:
            start = parse_timestamp(left)
            end = parse_timestamp(right)                # ignores trailing cue settings
        except ValueError:
            continue
        body = "\n".join(lines[ts_idx + 1:]).strip()
        if not body or end <= start:
            continue
        cues.append({"start": start, "end": end, "text": body})
    return cues
