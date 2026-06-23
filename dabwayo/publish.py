"""Publish artifacts from an (ephemeral) agent sandbox to the durable VM Studio.

The Claude Code execution sandbox is reclaimed when the session ends, so any
rendered media there is lost unless pushed out. This uploads a finished file to
the Studio's ``POST /api/upload`` (base64 JSON) so it lands on the VM's
``OUTPUT_DIR`` and is registered as an asset — surviving disconnects and showing
up in the gallery/dashboard.

Configure the target with ``DABWAYO_STUDIO_URL`` (e.g. https://host/studio) and,
if the server sets ``DABWAYO_STUDIO_KEY``, the same key via ``DABWAYO_STUDIO_KEY``.
"""
from __future__ import annotations

import base64
import os
from typing import Optional

ENV_URL = "DABWAYO_STUDIO_URL"
ENV_KEY = "DABWAYO_STUDIO_KEY"


class PublishError(RuntimeError):
    pass


def publish(path: str, *, base_url: Optional[str] = None, role: str = "final",
            kind: str = "video", action: str = "render", provider: str = "engine",
            prompt: str = "", parent: Optional[str] = None,
            project: Optional[str] = None, api_key: Optional[str] = None,
            timeout: float = 600.0) -> dict:
    """Upload ``path`` to the VM Studio; returns the created asset record."""
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise PublishError("the 'requests' package is required") from e
    base = (base_url or os.environ.get(ENV_URL, "")).strip().rstrip("/")
    if not base:
        raise PublishError(f"set {ENV_URL} to your VM Studio URL")
    if not os.path.isfile(path):
        raise PublishError(f"file not found: {path}")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    body = {"filename": os.path.basename(path), "b64": b64, "role": role,
            "kind": kind, "action": action, "provider": provider,
            "prompt": prompt, "parent": parent, "project": project}
    headers = {"Content-Type": "application/json"}
    key = api_key or os.environ.get(ENV_KEY, "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = requests.post(base + "/api/upload", json=body, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        raise PublishError(f"upload to {base} failed: {e}") from e
    if r.status_code != 200:
        raise PublishError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()
