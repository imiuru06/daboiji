"""First-class storyboard library — the *plan*, decoupled from render projects.

Previously a storyboard lived inside a render project's spec (one flat shot list
per project, bundling the creative plan with the assembled timeline). This makes
it a reusable store entity of its own (like character/environment bibles): a
named storyboard with **scenes**, each holding **shots**, and each shot binding
a **cast** (multiple characters), an environment and **props**. One storyboard
can drive many render projects; the render project is produced by *assembling*
it, keeping plan and output separate. (The old per-project storyboard tools keep
working for backward compatibility.)

Per ADR-0002 / ADR-0001, dabwayo owns this structured model + index; bytes and
ML stay external.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import List, Optional

from .service import STORE

__all__ = ["create", "get", "list_all", "update", "remove",
           "add_scene", "remove_scene", "move_scene", "iter_shots",
           "add_shot", "update_shot", "remove_shot", "move_shot", "new_shot"]

_SAFE = re.compile(r"[A-Za-z0-9_]+")


def _dir() -> str:
    d = os.path.join(STORE.root, "storyboards")
    os.makedirs(d, exist_ok=True)
    return d


def _path(sid: str) -> str:
    if not sid or not _SAFE.fullmatch(sid):
        raise ValueError(f"invalid storyboard id: {sid!r}")
    return os.path.join(_dir(), f"{sid}.json")


def _write(rec: dict) -> dict:
    with open(_path(rec["id"]), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    return rec


def create(name: str, description: str = "", width: int = 1080,
           height: int = 1920, fps: float = 24.0) -> dict:
    rec = {"id": "sb_" + uuid.uuid4().hex[:8], "name": name,
           "description": description, "width": int(width), "height": int(height),
           "fps": float(fps), "scenes": []}
    return _write(rec)


def get(sid: str) -> dict:
    p = _path(sid)
    if not os.path.exists(p):
        raise ValueError(f"storyboard not found: {sid}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def list_all() -> List[dict]:
    d = _dir()
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
    return out


def update(sid: str, patch: dict) -> dict:
    rec = get(sid)
    for k, v in (patch or {}).items():
        if k in ("id", "scenes"):
            continue
        if v is None:
            rec.pop(k, None)
        else:
            rec[k] = v
    return _write(rec)


def remove(sid: str) -> bool:
    p = _path(sid)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


# -- scenes ----------------------------------------------------------------
def add_scene(sid: str, name: str = "") -> dict:
    rec = get(sid)
    scene = {"id": "sc_" + uuid.uuid4().hex[:6], "name": name, "shots": []}
    rec.setdefault("scenes", []).append(scene)
    _write(rec)
    return scene


def remove_scene(sid: str, scene_id: str) -> dict:
    rec = get(sid)
    rec["scenes"] = [s for s in rec.get("scenes", []) if s.get("id") != scene_id]
    return _write(rec)


def move_scene(sid: str, scene_id: str, to_index: int) -> dict:
    """Reorder a scene to ``to_index`` within the storyboard."""
    rec = get(sid)
    scenes = rec.get("scenes", [])
    idx = next((i for i, s in enumerate(scenes) if s.get("id") == scene_id), None)
    if idx is None:
        raise ValueError(f"scene not found: {scene_id}")
    sc = scenes.pop(idx)
    scenes.insert(max(0, min(int(to_index), len(scenes))), sc)
    return _write(rec)


def _find_scene(rec: dict, scene_id: str):
    for s in rec.get("scenes", []):
        if s.get("id") == scene_id:
            return s
    raise ValueError(f"scene not found: {scene_id}")


def _find_shot(rec: dict, shot_id: str):
    for s in rec.get("scenes", []):
        for i, sh in enumerate(s.get("shots", [])):
            if sh.get("id") == shot_id:
                return s, i, sh
    raise ValueError(f"shot not found: {shot_id}")


def iter_shots(rec: dict):
    """Yield (scene, shot) for every shot in scene order."""
    for s in rec.get("scenes", []):
        for sh in s.get("shots", []):
            yield s, sh


# -- shots -----------------------------------------------------------------
def new_shot(prompt: str = "", duration: float = 4.0, mode: str = "t2v",
             caption: str = "", transition: str = "fade") -> dict:
    return {"id": "shot_" + uuid.uuid4().hex[:8], "prompt": prompt,
            "duration": float(duration), "mode": mode, "caption": caption,
            "transition": transition, "image": None, "media": None,
            "cast": [], "environment": None, "props": [], "camera": {}}


def add_shot(sid: str, scene_id: str, **fields) -> dict:
    rec = get(sid)
    scene = _find_scene(rec, scene_id)
    shot = new_shot(prompt=fields.get("prompt", ""), duration=fields.get("duration", 4.0),
                    mode=fields.get("mode", "t2v"), caption=fields.get("caption", ""),
                    transition=fields.get("transition", "fade"))
    for k in ("cast", "environment", "props", "camera", "image", "media"):
        if fields.get(k) is not None:
            shot[k] = fields[k]
    scene["shots"].append(shot)
    _write(rec)
    return shot


def update_shot(sid: str, shot_id: str, patch: dict) -> dict:
    rec = get(sid)
    _, _, shot = _find_shot(rec, shot_id)
    for k, v in (patch or {}).items():
        if k == "id":
            continue
        if v is None:
            shot.pop(k, None)
        else:
            shot[k] = v
    _write(rec)
    return shot


def remove_shot(sid: str, shot_id: str) -> dict:
    rec = get(sid)
    scene, i, _ = _find_shot(rec, shot_id)
    scene["shots"].pop(i)
    return _write(rec)


def move_shot(sid: str, shot_id: str, to_scene_id: Optional[str] = None,
              to_index: Optional[int] = None) -> dict:
    """Reorder a shot within its scene, or move it into another scene (append,
    or at ``to_index``). The shot keeps its id."""
    rec = get(sid)
    scene, i, shot = _find_shot(rec, shot_id)
    scene["shots"].pop(i)
    dest = _find_scene(rec, to_scene_id) if to_scene_id else scene
    ti = len(dest["shots"]) if to_index is None else max(0, min(int(to_index), len(dest["shots"])))
    dest["shots"].insert(ti, shot)
    return _write(rec)
