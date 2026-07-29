"""Storage tools: where asset bytes live (pluggable), while the index stays in
the registry. Move an asset's bytes to a backend, get a deliverable URL, or
localize (download) it for reading. ADR-0001 phase 3."""
from __future__ import annotations

from typing import Optional

from .app import mcp

__all__ = ["list_storage_backends", "put_asset", "asset_url", "localize_asset"]


@mcp.tool()
def list_storage_backends() -> dict:
    """List storage backends for asset bytes and whether each is ready (local is
    always available; s3 needs boto3 + DABWAYO_STORAGE_S3_BUCKET), plus the
    active one. The asset *index* (registry) is unaffected — only where the
    bytes live changes."""
    from ..storage import list_backends
    return {"ok": True, **list_backends()}


@mcp.tool()
def put_asset(asset_id: str, backend: Optional[str] = None) -> dict:
    """Upload an asset's bytes to a storage backend (default: the active one)
    and update its registry record's ``backend`` + ``uri`` — the index entry now
    points at the new location, so the asset is portable across machines/agents."""
    from ..storage import put_asset as _put
    rec = _put(asset_id, backend=backend)
    return {"ok": True, "asset_id": asset_id, "backend": rec.get("backend"),
            "uri": rec.get("uri")}


@mcp.tool()
def asset_url(asset_id: str) -> dict:
    """Return a deliverable URL for an asset via its backend (a presigned URL for
    s3, /files/… for local)."""
    from ..storage import asset_url as _url
    return {"ok": True, "asset_id": asset_id, "url": _url(asset_id)}


@mcp.tool()
def localize_asset(asset_id: str) -> dict:
    """Ensure an asset's bytes are available locally (downloading from a remote
    backend into the cache if needed) and return the local path — for tools that
    read the file (render, add_media, watermark …)."""
    from ..storage import localize_asset as _loc
    return {"ok": True, "asset_id": asset_id, "path": _loc(asset_id)}
