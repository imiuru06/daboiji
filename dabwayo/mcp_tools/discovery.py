"""Discovery tools: what the engine supports + how to author."""
from __future__ import annotations

from .. import capabilities as engine_capabilities
from .app import mcp, _HELP

__all__ = ["get_capabilities", "get_help"]


@mcp.tool()
def get_capabilities() -> dict:
    """List everything the engine supports: element types, effects,
    transitions, blend modes, easings and anchors. Call this first to learn
    which values are valid for the other tools."""
    return engine_capabilities()


@mcp.tool()
def get_help() -> str:
    """Return a concise authoring guide: coordinate system, the spec model,
    how keyframes/transitions/effects work, and a minimal example."""
    return _HELP
