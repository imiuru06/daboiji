"""Local-filesystem storage — the default. Bytes stay on disk; the URI is the
absolute path. (The Studio serves them at /files/<basename>.)"""
from __future__ import annotations

import os
from typing import Optional

from .base import StorageProvider


class LocalStorage(StorageProvider):
    name = "local"

    def available(self) -> tuple[bool, str]:
        return (True, "local filesystem")

    def put(self, local_path: str, key: Optional[str] = None) -> str:
        return os.path.abspath(local_path)

    def localize(self, uri: str) -> str:
        return uri[len("file://"):] if uri.startswith("file://") else uri

    def url(self, uri: str) -> Optional[str]:
        return "/files/" + os.path.basename(uri) if uri else None

    def exists(self, uri: str) -> bool:
        return os.path.isfile(self.localize(uri))
