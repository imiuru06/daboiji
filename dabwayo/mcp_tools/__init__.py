"""Dabwayo MCP tools, split into category modules.

Importing this package builds the single shared ``mcp`` instance (in ``app``)
and imports every category module, which registers all ``@mcp.tool()``s onto
it. Each tool function is also hoisted into this package's namespace so callers
(and the backward-compatible ``dabwayo.mcp_server`` shim) can do
``from dabwayo.mcp_tools import add_text`` exactly as before.

Categories:
  discovery · projects · clips · editing · generation · watermark ·
  music · assets · dashboard · inspection · render
"""
from __future__ import annotations

from .app import mcp, main

# Import order matters only where one module imports another (generation ->
# clips); keeping clips before generation avoids a partial-import surprise.
from . import (  # noqa: E402
    discovery, projects, clips, editing, captions, transcribe, voiceover,
    storyboard, storyboards, reference, generation, watermark, music, assets,
    storage, dashboard, inspection, render, comments, templates,
)

_MODULES = [discovery, projects, clips, editing, captions, transcribe,
            voiceover, storyboard, storyboards, reference, generation, watermark,
            music, assets, storage, dashboard, inspection, render, comments,
            templates]

# Hoist every category module's public tool functions to the package namespace
# so `dabwayo.mcp_tools.add_text` (and the mcp_server shim) resolve them.
__all__ = ["mcp", "main"]
for _m in _MODULES:
    for _name in getattr(_m, "__all__", []):
        globals()[_name] = getattr(_m, _name)
        __all__.append(_name)

del _m, _name
