"""Operator-dashboard tools (Studio): activity log + consolidated status."""
from __future__ import annotations

from typing import List, Optional

from .app import mcp

__all__ = ["log_activity", "studio_status"]


@mcp.tool()
def log_activity(action: str, summary: str, inputs: Optional[List[str]] = None,
                 outputs: Optional[List[str]] = None, notes: str = "") -> dict:
    """Record one pipeline step to the shared activity log shown on the Studio
    dashboard (the ② timeline). Call this after each meaningful step so a human
    can see what was done and the before -> after at a glance.

    action: short verb (e.g. 'generate', 'dewatermark', 'render', 'compose').
    summary: one-line description. inputs/outputs: file paths or short refs
    that form the before -> after. notes: optional extra context."""
    from ..studio.guide import append_activity
    ev = append_activity({"action": action, "summary": summary,
                          "inputs": inputs or [], "outputs": outputs or [],
                          "notes": notes})
    return {"ok": True, "event": ev}


@mcp.tool()
def studio_status() -> dict:
    """Consolidated operator view (same data the Studio dashboard shows):
    high-level actions the pipeline can do, the prompt cookbook (incl. linking
    multiple media into one video), the engine primitives, and the activity
    timeline. Use this to answer 'what can I do / what was done / which prompts
    to use' in one shot."""
    from ..studio.guide import dashboard_data
    return dashboard_data()
