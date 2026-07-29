"""Storage backend interface — where asset *bytes* live.

Per ADR-0001, dabwayo owns the asset *index* (the registry) but delegates the
*bytes* to a pluggable backend so assets are portable across machines/agents
(no hard local paths). ``local`` is the default; ``s3`` (and others) are opt-in.
An asset record carries ``{backend, uri}``; ``localize`` yields a readable local
path regardless of where the bytes actually are.
"""
from __future__ import annotations

from typing import Optional


class StorageError(RuntimeError):
    pass


class StorageProvider:
    name = "base"

    def available(self) -> tuple[bool, str]:
        return (False, "not implemented")

    def put(self, local_path: str, key: Optional[str] = None) -> str:
        """Store the bytes at ``local_path`` and return a backend URI."""
        raise NotImplementedError

    def localize(self, uri: str) -> str:
        """Return a local readable path for ``uri`` (downloading if remote)."""
        raise NotImplementedError

    def url(self, uri: str) -> Optional[str]:
        """A deliverable URL for ``uri`` if the backend has one, else None."""
        return None

    def exists(self, uri: str) -> bool:
        return False
