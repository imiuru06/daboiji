"""Asset registry — the JSON management layer for media + provenance.

Generated/processed clips used to land in ``OUTPUT_DIR`` with random names and
no record of how they were made. This registry gives every media file a stable
record under ``<STORE>/assets/<id>.json`` describing:

  • what it is        — kind (video/image/audio), media metadata
  • how it was made   — source: {action, provider, prompt, parent, params}
  • where it's used   — projects: [project_id, ...]

The ``source.parent`` link forms a **provenance graph**, which is exactly how
multiple media get connected and traced:

    raw (Veo t2v) ──▶ dewatermarked (LaMa) ──▶ edited (engine) ──▶ final

See ``STORE.md`` for the full store layout and JSON schemas.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

from .service import STORE

KINDS = ("video", "image", "audio")
ROLES = ("raw", "dewatermarked", "edited", "broll", "final", "upload", "other")


# -- paths -----------------------------------------------------------------
def assets_dir() -> str:
    d = os.path.join(STORE.root, "assets")
    os.makedirs(d, exist_ok=True)
    return d


def _rec_path(aid: str) -> str:
    return os.path.join(assets_dir(), f"{aid}.json")


def new_id() -> str:
    return "ast_" + uuid.uuid4().hex[:10]


# -- io --------------------------------------------------------------------
def _write(rec: dict) -> dict:
    p = _rec_path(rec["id"])
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)                       # atomic
    return rec


def exists(aid: str) -> bool:
    return os.path.isfile(_rec_path(aid))


def get(aid: str) -> dict:
    with open(_rec_path(aid), encoding="utf-8") as f:
        return json.load(f)


def ids() -> list[str]:
    d = assets_dir()
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def list_assets() -> list[dict]:
    return [get(i) for i in ids()]


def find_by_path(path: str) -> Optional[dict]:
    """Return the asset whose file is ``path`` (for parent linking), if any."""
    ap = os.path.abspath(path)
    for rec in list_assets():
        if rec.get("path") == ap:
            return rec
    return None


# -- media probe -----------------------------------------------------------
def probe_media(path: str) -> dict:
    """Best-effort (width, height, fps, frames, duration, has_audio)."""
    info: dict = {}
    try:
        import imageio.v2 as imageio
        r = imageio.get_reader(path)
        m = r.get_meta_data()
        sz = m.get("size") or (0, 0)
        fps = float(m.get("fps") or 0)
        try:
            n = r.count_frames()
        except Exception:  # noqa: BLE001
            n = int(m.get("nframes") or 0)
        r.close()
        info = {"width": int(sz[0]), "height": int(sz[1]), "fps": fps,
                "frames": int(n),
                "duration": round(n / fps, 3) if fps else None}
    except Exception:  # noqa: BLE001
        pass
    return info


# -- register / mutate -----------------------------------------------------
def register(path: str, *, kind: str = "video", role: str = "other",
             source: Optional[dict] = None, projects: Optional[list] = None,
             tags: Optional[list] = None, probe: bool = True,
             aid: Optional[str] = None) -> dict:
    """Register ``path`` as an asset and return the record.

    source: provenance dict ``{action, provider, prompt, parent, params}``.
    If ``source['parent']`` is omitted but a registered asset matches an input
    path, callers can resolve it via :func:`find_by_path` first.
    """
    rec = {
        "id": aid or new_id(),
        "kind": kind,
        "role": role,
        "path": os.path.abspath(path),
        "source": source or {},
        "media": probe_media(path) if probe else {},
        "projects": projects or [],
        "tags": tags or [],
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return _write(rec)


def link_project(aid: str, pid: str) -> dict:
    rec = get(aid)
    if pid not in rec["projects"]:
        rec["projects"].append(pid)
        _write(rec)
    return rec


def prune() -> list[str]:
    """Drop asset records whose underlying file no longer exists. Returns the
    removed ids (housekeeping for the store)."""
    removed = []
    for aid in ids():
        try:
            rec = get(aid)
        except Exception:  # noqa: BLE001
            continue
        if not os.path.isfile(rec.get("path", "")):
            os.remove(_rec_path(aid))
            removed.append(aid)
    return removed


def lineage(aid: str) -> list[dict]:
    """Walk the provenance chain from this asset back to its root ancestor."""
    chain, seen = [], set()
    cur: Optional[str] = aid
    while cur and cur not in seen and exists(cur):
        seen.add(cur)
        rec = get(cur)
        chain.append(rec)
        cur = (rec.get("source") or {}).get("parent")
    return chain


# -- manifest / index ------------------------------------------------------
def build_index() -> dict:
    """A single manifest over the whole store: projects + assets summaries."""
    projects = []
    for pid in STORE.ids():
        if pid.startswith("_"):
            continue
        try:
            s = STORE[pid]
        except Exception:  # noqa: BLE001
            continue
        projects.append({
            "id": pid, "name": s.get("name", pid),
            "resolution": [s.get("width"), s.get("height")],
            "fps": s.get("fps"), "tracks": len(s.get("tracks", [])),
        })
    assets = [{
        "id": a["id"], "kind": a["kind"], "role": a["role"],
        "duration": (a.get("media") or {}).get("duration"),
        "parent": (a.get("source") or {}).get("parent"),
        "provider": (a.get("source") or {}).get("provider"),
        "projects": a.get("projects", []), "created": a.get("created"),
        # served URL so the gallery can play/show the media directly
        "file": ("/files/" + os.path.basename(a["path"])) if a.get("path") else None,
    } for a in list_assets()]
    return {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "store_root": STORE.root,
        "counts": {"projects": len(projects), "assets": len(assets)},
        "projects": projects,
        "assets": assets,
    }
