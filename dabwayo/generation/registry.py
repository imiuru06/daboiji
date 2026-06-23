"""Provider selection.

Default behaviour (``DABWAYO_VIDEOGEN_PROVIDER`` unset or ``auto``):
  1. if ``DABWAYO_VIDEOGEN_URL`` is set     -> remote (Colab / GPU server)
  2. else first hosted provider whose key is set (replicate/fal/huggingface)
  3. else ``local`` (always available, procedural)

Override explicitly by name via the env var or the ``provider=`` argument.
"""
from __future__ import annotations

import os
from typing import Optional

from .base import VideoGenProvider
from .local import LocalProvider
from .remote import (FalProvider, HuggingFaceProvider, RemoteHTTPProvider,
                     ReplicateProvider)

_CONSTRUCTORS = {
    "local": LocalProvider,
    "remote": RemoteHTTPProvider,
    "replicate": ReplicateProvider,
    "huggingface": HuggingFaceProvider,
    "fal": FalProvider,
}
# hosted providers tried (in order) during auto-selection
_AUTO_HOSTED = ["replicate", "fal", "huggingface"]


def _make(name: str) -> VideoGenProvider:
    name = name.lower()
    if name not in _CONSTRUCTORS:
        raise ValueError(f"unknown provider {name!r}; "
                         f"choose from {sorted(_CONSTRUCTORS)}")
    return _CONSTRUCTORS[name]()


def get_provider(name: Optional[str] = None) -> VideoGenProvider:
    """Resolve a provider instance from an explicit name, the
    ``DABWAYO_VIDEOGEN_PROVIDER`` env var, or auto-detection."""
    choice = (name or os.environ.get("DABWAYO_VIDEOGEN_PROVIDER", "auto")).lower()
    if choice != "auto":
        return _make(choice)
    if os.environ.get("DABWAYO_VIDEOGEN_URL"):
        return _make("remote")
    for hosted in _AUTO_HOSTED:
        if _make(hosted).available()[0]:
            return _make(hosted)
    return _make("local")


def list_providers() -> dict:
    """Availability report for every provider (for discovery/diagnostics)."""
    out = {}
    for nm in _CONSTRUCTORS:
        ok, why = _make(nm).available()
        out[nm] = {"available": ok, "detail": why}
    active = get_provider()
    return {"active": active.name, "providers": out,
            "configure": {
                "env": "DABWAYO_VIDEOGEN_PROVIDER (auto|local|remote|replicate|fal|huggingface)",
                "remote_url": "DABWAYO_VIDEOGEN_URL (Colab/GPU server)",
                "colab_notebook": "colab/dabwayo_gpu_server.ipynb"}}
