"""Timestamped review comments on an asset (Frame.io-style feedback).

A viewer leaves a note pinned to a moment in the video; the agent can read
them back and act. Stored as one small JSON file per asset under the shared
store, so comments survive alongside the project data.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import List, Dict

from .service import STORE

__all__ = ["add_comment", "list_comments"]

_SAFE = re.compile(r"[A-Za-z0-9_]+")


def _safe_id(asset_id: str) -> str:
    if not asset_id or not _SAFE.fullmatch(asset_id):
        raise ValueError(f"invalid asset id: {asset_id!r}")
    return asset_id


def _path(asset_id: str) -> str:
    d = os.path.join(STORE.root, "comments")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{_safe_id(asset_id)}.json")


def list_comments(asset_id: str) -> List[Dict]:
    """Return the asset's comments, sorted by their timeline time ``t``."""
    p = _path(asset_id)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = []
    return sorted(data, key=lambda c: c.get("t", 0))


def add_comment(asset_id: str, t: float, text: str, author: str = "") -> Dict:
    """Append a comment pinned at ``t`` seconds. Returns the stored record."""
    text = (text or "").strip()
    if not text:
        raise ValueError("comment text is empty")
    rec = {"id": "cm_" + uuid.uuid4().hex[:8],
           "t": round(float(t or 0), 2),
           "text": text[:2000],
           "author": (author or "anon").strip()[:60] or "anon",
           "created": time.time()}
    data = list_comments(asset_id)
    data.append(rec)
    with open(_path(asset_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return rec
