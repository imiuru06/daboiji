"""Review-comment tools: read/write timestamped feedback on an asset.

Closes the loop between the shared viewer (where an audience leaves notes
pinned to a moment) and the agent (which reads them and edits accordingly)."""
from __future__ import annotations

from .app import mcp

__all__ = ["list_comments", "add_comment"]


@mcp.tool()
def list_comments(asset_id: str) -> dict:
    """List an asset's timestamped review comments (sorted by their video time).

    Use this to read audience/reviewer feedback left on the shared viewer and
    act on it — each comment has ``t`` (seconds into the video), ``text`` and
    ``author``."""
    from ..comments import list_comments as _list
    items = _list(asset_id)
    return {"ok": True, "asset_id": asset_id, "count": len(items), "comments": items}


@mcp.tool()
def add_comment(asset_id: str, t: float, text: str, author: str = "") -> dict:
    """Add a review comment pinned at ``t`` seconds on an asset (the same feed
    the shared viewer reads/writes). Returns the stored comment."""
    from ..comments import add_comment as _add
    return {"ok": True, "comment": _add(asset_id, t, text, author)}
