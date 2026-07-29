"""Asset-registry tools: register, list, inspect, tidy, publish, compose. See STORE.md."""
from __future__ import annotations

import uuid
from typing import List, Optional

from .app import mcp, _PROJECTS, _log_activity_safe

__all__ = ["register_asset", "list_assets", "get_asset", "store_index",
           "organize_store", "publish_to_studio", "compose_sequence"]


@mcp.tool()
def register_asset(path: str, kind: str = "video", role: str = "other",
                   action: str = "upload", provider: str = "",
                   prompt: str = "", parent: Optional[str] = None,
                   tags: Optional[List[str]] = None) -> dict:
    """Register a media file as a tracked asset with provenance.

    Stores a record under <STORE>/assets/<id>.json (see STORE.md). ``role``:
    raw|dewatermarked|edited|broll|final|upload|other. ``parent`` links to the
    asset this was derived from — that link forms the provenance graph that
    connects multiple media (raw -> dewatermarked -> edited -> final)."""
    from .. import assets as _assets
    src = {"action": action, "provider": provider, "prompt": prompt}
    if parent:
        src["parent"] = parent
    return _assets.register(path, kind=kind, role=role, source=src, tags=tags)


@mcp.tool()
def list_assets() -> dict:
    """List all registered assets (id, kind, role, media, source, projects)."""
    from .. import assets as _assets
    return {"assets": _assets.list_assets()}


@mcp.tool()
def get_asset(asset_id: str, with_lineage: bool = True) -> dict:
    """Get one asset record; with_lineage walks source.parent back to the root
    so you can see how the media was built up from other media."""
    from .. import assets as _assets
    rec = _assets.get(asset_id)
    if with_lineage:
        rec = {**rec, "lineage": [a["id"] for a in _assets.lineage(asset_id)]}
    return rec


@mcp.tool()
def store_index() -> dict:
    """Whole-store manifest: project + asset summaries with counts (see STORE.md)."""
    from .. import assets as _assets
    return _assets.build_index()


@mcp.tool()
def organize_store() -> dict:
    """Housekeeping: drop asset records whose files are gone, then return the
    refreshed manifest. Use to tidy the store after deleting media."""
    from .. import assets as _assets
    pruned = _assets.prune()
    return {"ok": True, "pruned": pruned, "index": _assets.build_index()}


@mcp.tool()
def publish_to_studio(path: str, role: str = "final", kind: str = "video",
                      action: str = "render", provider: str = "engine",
                      prompt: str = "", parent: Optional[str] = None,
                      project: Optional[str] = None) -> dict:
    """Upload a finished file to the durable VM Studio (DABWAYO_STUDIO_URL).

    The Claude Code sandbox is ephemeral, so call this to persist a result on
    the VM: it is saved to the VM's OUTPUT_DIR, registered as an asset (with
    provenance), and appears in the gallery/dashboard — surviving disconnects.
    Returns the created asset record + its /files URL."""
    from ..publish import publish
    return publish(path, role=role, kind=kind, action=action, provider=provider,
                   prompt=prompt, parent=parent, project=project)


@mcp.tool()
def compose_sequence(asset_ids: List[str], project_id: Optional[str] = None,
                     transition: str = "fade", transition_duration: float = 0.5,
                     title: Optional[str] = None, name: str = "sequence",
                     width: Optional[int] = None, height: Optional[int] = None,
                     fps: float = 24.0) -> dict:
    """Auto-place multiple assets onto one timeline as a connected video.

    Lays the given ``asset_ids`` back-to-back in order, takes each clip's length
    from its media metadata, joins them with soft ``transition`` (default fade),
    and adds an optional ``title`` intro + a light cinematic grade. Creates (or
    updates ``project_id``) a project, links every source asset to it (keeping
    provenance), and returns the project — ready for render_project. width/height
    default to the first asset's resolution."""
    from .. import assets as _assets, compose
    if not asset_ids:
        raise ValueError("compose_sequence: asset_ids is empty")
    recs = [_assets.get(a) for a in asset_ids]
    clips = [{"path": r["path"], "duration": (r.get("media") or {}).get("duration")}
             for r in recs]
    m0 = recs[0].get("media") or {}
    w = width or m0.get("width") or 1280
    h = height or m0.get("height") or 720
    spec = compose.build_sequence_spec(
        clips, width=int(w), height=int(h), fps=fps, transition=transition,
        transition_duration=transition_duration, title=title, name=name)
    pid = project_id or uuid.uuid4().hex[:12]
    _PROJECTS[pid] = spec
    for a in asset_ids:
        try:
            _assets.link_project(a, pid)
        except Exception:  # noqa: BLE001
            pass
    _log_activity_safe("compose", f"{len(asset_ids)}개 클립 시퀀스 구성",
                       asset_ids, [f"project:{pid}"])
    return {"ok": True, "project_id": pid, "clips": len(asset_ids),
            "duration": spec.get("duration"), "resolution": [int(w), int(h)]}
