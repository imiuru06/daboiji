"""Layout helpers: align / distribute / grid multiple clips deterministically.

``add_clip`` only takes an absolute ``position``; laying out several overlays
(three callouts across the lower third, a caption in the safe-area centre, a
grid of thumbnails) meant the agent doing pixel math every time. ``align_clips``
raises that to a creative unit — name the arrangement, dabwayo writes each
clip's ``transform.position``. Pure geometry over the canvas, no ML.

Positions are set as anchor POINTS (anchor=center): a clip's centre is placed
at the computed point. This is robust for auto-sized content (text, callouts)
whose pixel extents aren't known ahead of render.
"""
from __future__ import annotations

from typing import List, Optional

from ..core.presets import LAYOUT_MODES as _MODES
from .app import mcp, _proj, _commit, _resolve_clip

__all__ = ["align_clips"]


def _bounds(spec: dict, bounds) -> List[float]:
    w = float(spec.get("width", 1920))
    h = float(spec.get("height", 1080))
    if bounds is None:
        return [0.0, 0.0, w, h]
    if bounds == "safe":                     # 90% centred title/action-safe area
        return [0.05 * w, 0.05 * h, 0.90 * w, 0.90 * h]
    if isinstance(bounds, (list, tuple)) and len(bounds) == 4:
        return [float(v) for v in bounds]
    raise ValueError("bounds must be null, 'safe', or [x, y, w, h]")


@mcp.tool()
def align_clips(project_id: str, mode: str = "center",
                clip_ids: Optional[List[str]] = None,
                track: Optional[str] = None, padding: float = 40.0,
                bounds: Optional[object] = None,
                columns: Optional[int] = None) -> dict:
    """Arrange several clips at once — align, distribute, or grid them.

    Selects the target clips (explicit ``clip_ids``, else every clip on
    ``track``, else all video clips) and writes each one's centre position.

    mode:
      center / center_h / center_v — centre in the bounds (both / x-only / y).
      top / bottom / left / right   — align that edge (inset by ``padding``).
      distribute_h / distribute_v   — spread evenly across the bounds axis
                                      (order follows selection order).
      grid                          — row-major grid (``columns`` or ~square).
      stack_v / stack_h             — pack from the top/left with ``padding`` gaps.

    ``bounds`` is null (full canvas), 'safe' (90% safe area), or ``[x,y,w,h]``.
    Positions are anchor points (each clip's centre lands on the point), so it
    works for auto-sized text/callouts. Set ``depth`` separately if needed."""
    spec = _proj(project_id)
    bx, by, bw, bh = _bounds(spec, bounds)
    cx, cy = bx + bw / 2.0, by + bh / 2.0

    # ---- select target clips (preserve requested order) ------------------
    targets = []
    if clip_ids:
        for cid in clip_ids:
            tr, idx = _resolve_clip(spec, None, None, cid)
            targets.append(tr["clips"][idx])
    else:
        for tr in spec.get("tracks", []):
            if tr.get("kind", "video") != "video":
                continue
            if track and tr.get("name") != track:
                continue
            targets.extend(tr.get("clips", []))
    n = len(targets)
    if n == 0:
        return {"ok": True, "mode": mode, "clips_affected": 0, "positions": []}

    def _pos(clip):
        t = clip.setdefault("transform", {})
        p = t.get("position")
        return [float(p[0]), float(p[1])] if (isinstance(p, (list, tuple))
                                              and len(p) == 2) else [cx, cy]

    def _set(clip, x, y):
        t = clip.setdefault("transform", {})
        t["position"] = [round(x, 2), round(y, 2)]
        t["anchor"] = "center"

    if mode == "center":
        for c in targets:
            _set(c, cx, cy)
    elif mode == "center_h":
        for c in targets:
            _set(c, cx, _pos(c)[1])
    elif mode == "center_v":
        for c in targets:
            _set(c, _pos(c)[0], cy)
    elif mode == "top":
        for c in targets:
            _set(c, _pos(c)[0], by + padding)
    elif mode == "bottom":
        for c in targets:
            _set(c, _pos(c)[0], by + bh - padding)
    elif mode == "left":
        for c in targets:
            _set(c, bx + padding, _pos(c)[1])
    elif mode == "right":
        for c in targets:
            _set(c, bx + bw - padding, _pos(c)[1])
    elif mode == "distribute_h":
        if n == 1:
            _set(targets[0], cx, _pos(targets[0])[1])
        else:
            usable = bw - 2 * padding
            for i, c in enumerate(targets):
                x = bx + padding + usable * (i / (n - 1))
                _set(c, x, _pos(c)[1])
    elif mode == "distribute_v":
        if n == 1:
            _set(targets[0], _pos(targets[0])[0], cy)
        else:
            usable = bh - 2 * padding
            for i, c in enumerate(targets):
                y = by + padding + usable * (i / (n - 1))
                _set(c, _pos(c)[0], y)
    elif mode == "grid":
        import math
        cols = int(columns) if columns else max(1, int(math.ceil(math.sqrt(n))))
        rows = max(1, int(math.ceil(n / cols)))
        cellw, cellh = bw / cols, bh / rows
        for i, c in enumerate(targets):
            r, col = divmod(i, cols)
            _set(c, bx + cellw * (col + 0.5), by + cellh * (r + 0.5))
    elif mode == "stack_v":
        y = by + padding
        step = (bh - 2 * padding) / max(1, n)
        for c in targets:
            _set(c, cx, y + step / 2.0)
            y += step
    elif mode == "stack_h":
        x = bx + padding
        step = (bw - 2 * padding) / max(1, n)
        for c in targets:
            _set(c, x + step / 2.0, cy)
            x += step
    else:
        raise ValueError(f"Unknown mode {mode!r}. Available: {', '.join(_MODES)}")

    _commit(project_id, spec)
    positions = [{"clip_id": c.get("id", ""),
                  "position": c["transform"]["position"]} for c in targets]
    return {"ok": True, "mode": mode, "bounds": [bx, by, bw, bh],
            "clips_affected": n, "positions": positions}
