"""Dabwayo MCP server — backward-compatible entrypoint.

The tool definitions now live in the ``dabwayo.mcp_tools`` package, split into
category modules (discovery, projects, clips, editing, generation, watermark,
music, assets, dashboard, inspection, render). This module is kept so the
existing import path, console script and function names all keep working:

* ``python -m dabwayo.mcp_server`` and the ``dabwayo-mcp`` entry point run
  ``main`` below (stdio by default; DABWAYO_MCP_TRANSPORT=http for remote).
* ``from dabwayo import mcp_server as M`` still exposes every tool as a plain
  callable (e.g. ``M.add_text(...)`` as the Studio REST layer uses it), plus
  the shared ``mcp`` instance.

To add or change a tool, edit the relevant module under ``dabwayo/mcp_tools/``
— not this file.
"""
from __future__ import annotations

from .mcp_tools import *          # noqa: F401,F403  (re-export all tool functions)
from .mcp_tools import mcp, main  # noqa: F401  (explicit: instance + entrypoint)
# Also expose the shared state/helpers that used to be module-level here, so
# code reaching for internals (e.g. mcp_server._PROJECTS) keeps working.
from .mcp_tools.app import (  # noqa: F401
    _PROJECTS, _OUTPUT_DIR, _MUSIC_DIR, _HELP,
    _proj, _commit, _video_track, _log_activity_safe,
    _new_clip_id, _deep_merge, _find_track, _clip_summary, _resolve_clip,
)


if __name__ == "__main__":
    main()
