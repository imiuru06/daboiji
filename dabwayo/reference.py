"""Creative reference library — character & environment "bibles".

Structured, reusable creative references stored under the shared store
(``<STORE>/characters/<id>.json``, ``<STORE>/environments/<id>.json``). Each
entity has canonical ``base_refs`` (asset ids of reference sheets) and
``variants`` (outfit/pose/expression for characters; time/lighting/mood/focus
for environments), each with its own ``prompt_fragment`` and ``refs``.

Per ADR-0001, dabwayo owns this *structured model + index*; the reference-image
*bytes* are ordinary assets (pluggable storage) and the *ML consistency* is the
generation provider's job. This module is pure bookkeeping — no ML, no rendering.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import List, Optional

from .service import STORE

__all__ = ["create", "get", "list_all", "update", "remove",
           "add_variant", "remove_variant", "attach_ref", "detach_ref"]

_KINDS = {"character": "characters", "environment": "environments"}
_PREFIX = {"character": "char", "environment": "env"}
_SAFE = re.compile(r"[A-Za-z0-9_]+")


def _check_kind(kind: str) -> str:
    if kind not in _KINDS:
        raise ValueError(f"unknown reference kind {kind!r}; use 'character' or 'environment'")
    return kind


def _dir(kind: str) -> str:
    d = os.path.join(STORE.root, _KINDS[_check_kind(kind)])
    os.makedirs(d, exist_ok=True)
    return d


def _path(kind: str, eid: str) -> str:
    if not eid or not _SAFE.fullmatch(eid):
        raise ValueError(f"invalid id: {eid!r}")
    return os.path.join(_dir(kind), f"{eid}.json")


def _new_id(kind: str) -> str:
    return f"{_PREFIX[kind]}_{uuid.uuid4().hex[:8]}"


def _write(kind: str, rec: dict) -> dict:
    with open(_path(kind, rec["id"]), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    return rec


def create(kind: str, name: str, description: str = "") -> dict:
    _check_kind(kind)
    rec = {"id": _new_id(kind), "kind": kind, "name": name,
           "description": description, "base_refs": [], "variants": []}
    return _write(kind, rec)


def get(kind: str, eid: str) -> dict:
    p = _path(kind, eid)
    if not os.path.exists(p):
        raise ValueError(f"{kind} not found: {eid}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def list_all(kind: str) -> List[dict]:
    d = _dir(kind)
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
    return out


def update(kind: str, eid: str, patch: dict) -> dict:
    rec = get(kind, eid)
    for k, v in (patch or {}).items():
        if k in ("id", "kind", "variants", "base_refs"):
            continue                       # structural fields have their own ops
        if v is None:
            rec.pop(k, None)
        else:
            rec[k] = v
    return _write(kind, rec)


def remove(kind: str, eid: str) -> bool:
    p = _path(kind, eid)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def add_variant(kind: str, eid: str, label: str, prompt_fragment: str = "",
                refs: Optional[list] = None, attributes: Optional[dict] = None) -> dict:
    """Add a variant. ``attributes`` carries kind-specific fields — for a
    character e.g. {"kind":"outfit"}; for an environment e.g.
    {"time_of_day":"dawn","lighting":"cool","mood":"quiet","focus":"shallow"}."""
    rec = get(kind, eid)
    v = {"id": f"v_{uuid.uuid4().hex[:6]}", "label": label,
         "prompt_fragment": prompt_fragment, "refs": list(refs or []),
         **(attributes or {})}
    rec.setdefault("variants", []).append(v)
    _write(kind, rec)
    return v


def remove_variant(kind: str, eid: str, variant_id: str) -> dict:
    rec = get(kind, eid)
    rec["variants"] = [v for v in rec.get("variants", []) if v.get("id") != variant_id]
    return _write(kind, rec)


def attach_ref(kind: str, eid: str, asset_id: str,
               variant_id: Optional[str] = None) -> dict:
    """Link a reference-image asset id to the entity's base_refs, or to a
    variant's refs when ``variant_id`` is given."""
    rec = get(kind, eid)
    if variant_id:
        for v in rec.get("variants", []):
            if v.get("id") == variant_id:
                v.setdefault("refs", []).append(asset_id)
                break
        else:
            raise ValueError(f"variant not found: {variant_id}")
    else:
        rec.setdefault("base_refs", []).append(asset_id)
    return _write(kind, rec)


def detach_ref(kind: str, eid: str, asset_id: str,
               variant_id: Optional[str] = None) -> dict:
    rec = get(kind, eid)
    if variant_id:
        for v in rec.get("variants", []):
            if v.get("id") == variant_id:
                v["refs"] = [a for a in v.get("refs", []) if a != asset_id]
    else:
        rec["base_refs"] = [a for a in rec.get("base_refs", []) if a != asset_id]
    return _write(kind, rec)
