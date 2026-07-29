"""Template tools: fill a data-driven template into a ready-to-render project.

The "feed data, get a branded video" model — list templates, see their
placeholders, then create a project from a template + a data dict."""
from __future__ import annotations

import uuid
from typing import Optional

from .app import mcp, _PROJECTS, _log_activity_safe

__all__ = ["list_templates", "get_template", "create_from_template"]


@mcp.tool()
def list_templates() -> dict:
    """List the available video templates with their description, fillable
    placeholders and default values. Templates live in the templates dir
    (DABWAYO_TEMPLATES_DIR, default ./templates)."""
    from .. import templates as _t
    out = []
    for name in _t.list_builtin():
        try:
            tpl = _t.load(name)
        except Exception:  # noqa: BLE001
            continue
        out.append({"name": name,
                    "description": tpl.get("description", ""),
                    "placeholders": sorted(_t.placeholders(tpl["spec"])),
                    "defaults": tpl.get("defaults", {})})
    return {"ok": True, "count": len(out), "templates": out}


@mcp.tool()
def get_template(name: str) -> dict:
    """Return a template's raw definition (defaults + spec + placeholders)."""
    from .. import templates as _t
    tpl = _t.load(name)
    return {"ok": True, "name": name, "description": tpl.get("description", ""),
            "defaults": tpl.get("defaults", {}),
            "placeholders": sorted(_t.placeholders(tpl["spec"])),
            "spec": tpl["spec"]}


@mcp.tool()
def create_from_template(template: str, data: Optional[dict] = None,
                         project_id: Optional[str] = None) -> dict:
    """Fill a template with ``data`` and store it as a ready-to-render project.

    ``template`` is a builtin name (see list_templates) or a path to a .json
    template. ``data`` overrides the template's defaults for each placeholder
    (e.g. {"title": "...", "subtitle": "...", "duration": 5}). Returns the new
    ``project_id`` (render it with render_project), the resolution, and any
    placeholders left unfilled. Author templates by dropping a
    {name, description, defaults, spec} JSON in the templates dir."""
    from .. import templates as _t
    tpl = _t.load(template)
    merged = {**tpl.get("defaults", {}), **(data or {})}
    filled, missing = _t.fill(tpl["spec"], merged)
    pid = project_id or uuid.uuid4().hex[:12]
    _PROJECTS[pid] = filled
    _log_activity_safe("template", f"템플릿 '{template}' 채우기",
                       [template], [f"project:{pid}"])
    return {"ok": True, "project_id": pid, "template": template,
            "resolution": [filled.get("width"), filled.get("height")],
            "missing": missing, "applied": merged}
