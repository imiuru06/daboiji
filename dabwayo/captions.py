"""Subtitle/caption parsing (SRT + WebVTT) — dependency-light, pure functions.

Turns a subtitle file/string into a list of timed cues that the caption MCP
tool lays onto the timeline as styled text clips. Kept separate from the tool
layer so it is trivially unit-testable.
"""
from __future__ import annotations

import re
from typing import List, Dict

__all__ = ["parse_captions", "parse_timestamp", "words_from_cues", "group_words"]

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


def words_from_cues(cues: List[Dict]) -> List[Dict]:
    """Approximate per-word timings from line-level cues by splitting each cue's
    text into words and spreading them across the cue's span, weighted by word
    length. Use this when you only have line-level subtitles (SRT) but want
    word-timed captions. Returns ``[{"word","start","end"}, ...]``."""
    out: List[Dict] = []
    for c in cues:
        toks = str(c.get("text", "")).split()
        span = float(c["end"]) - float(c["start"])
        if not toks or span <= 0:
            continue
        weights = [max(1, len(t)) for t in toks]
        total = sum(weights)
        acc = float(c["start"])
        for tok, w in zip(toks, weights):
            d = span * w / total
            out.append({"word": tok, "start": round(acc, 3), "end": round(acc + d, 3)})
            acc += d
    return out


def group_words(words: List[Dict], size: int = 3) -> List[Dict]:
    """Group a word-timestamp list into pop-on chunks of ``size`` words each.
    Each group spans from its first word's start to its last word's end.
    Accepts ``word`` or ``text`` as the token key. Returns
    ``[{"text","start","end"}, ...]``."""
    size = max(1, int(size))
    norm = []
    for w in words:
        tok = (w.get("word") if isinstance(w, dict) else None) or (
            w.get("text") if isinstance(w, dict) else None)
        if tok is None or "start" not in w or "end" not in w:
            continue
        norm.append({"text": str(tok), "start": float(w["start"]), "end": float(w["end"])})
    groups: List[Dict] = []
    for i in range(0, len(norm), size):
        chunk = norm[i:i + size]
        groups.append({"text": " ".join(c["text"] for c in chunk),
                       "start": chunk[0]["start"], "end": chunk[-1]["end"]})
    return groups
