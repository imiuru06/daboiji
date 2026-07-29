"""Storage backend selection + asset-level put/localize.

Default (``DABWAYO_STORAGE_BACKEND`` unset/``auto``): s3 if configured, else
local. Override by name via the env var or an explicit ``backend=``.
"""
from __future__ import annotations

import os
from typing import Optional

from .base import StorageProvider, StorageError
from .local import LocalStorage
from .s3 import S3Storage

_CONSTRUCTORS = {"local": LocalStorage, "s3": S3Storage}


def _make(name: str) -> StorageProvider:
    n = name.lower()
    if n not in _CONSTRUCTORS:
        raise StorageError(f"unknown storage backend {name!r}; choose from {sorted(_CONSTRUCTORS)}")
    return _CONSTRUCTORS[n]()


def get_backend(name: Optional[str] = None) -> StorageProvider:
    choice = (name or os.environ.get("DABWAYO_STORAGE_BACKEND", "auto")).lower()
    if choice != "auto":
        return _make(choice)
    if _make("s3").available()[0]:
        return _make("s3")
    return _make("local")


def list_backends() -> dict:
    out = {}
    for nm in _CONSTRUCTORS:
        ok, why = _make(nm).available()
        out[nm] = {"available": ok, "detail": why}
    return {"active": get_backend().name, "backends": out}


# -- asset-level operations (index stays in dabwayo, bytes move) ------------
def put_asset(asset_id: str, backend: Optional[str] = None) -> dict:
    """Upload an asset's bytes to a storage backend and update its record's
    ``backend`` + ``uri`` (the index entry now points at the new location)."""
    from .. import assets as _assets
    rec = _assets.get(asset_id)
    local = rec.get("path") or localize_asset(asset_id)
    provider = get_backend(backend)
    uri = provider.put(local, key=f"{asset_id}_{os.path.basename(local)}")
    rec["backend"] = provider.name
    rec["uri"] = uri
    _assets._write(rec)
    return rec


def localize_asset(asset_id: str) -> str:
    """Return a local readable path for an asset regardless of its backend
    (downloads from remote backends into the cache)."""
    from .. import assets as _assets
    rec = _assets.get(asset_id)
    backend = rec.get("backend", "local")
    if backend == "local":
        return rec.get("path") or _make("local").localize(rec.get("uri", ""))
    return get_backend(backend).localize(rec["uri"])


def asset_url(asset_id: str) -> Optional[str]:
    """A deliverable URL for the asset via its backend (presigned for s3,
    /files/… for local)."""
    from .. import assets as _assets
    rec = _assets.get(asset_id)
    backend = rec.get("backend", "local")
    uri = rec.get("uri") or rec.get("path", "")
    return get_backend(backend).url(uri)
