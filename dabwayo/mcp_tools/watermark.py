"""Watermark-removal tools (remote LaMa server). See dabwayo/dewatermark.py."""
from __future__ import annotations

import os
import time
import uuid
from typing import List, Optional

from .app import mcp, _OUTPUT_DIR, _log_activity_safe

__all__ = ["lama_health", "remove_watermark"]


@mcp.tool()
def lama_health() -> dict:
    """Check the remote LaMa watermark-removal server (DABWAYO_LAMA_URL).

    The heavy ML inpainter runs off-box on a Colab GPU server
    (colab/dabwayo_lama_server.ipynb). Returns its /health payload, or
    ``{"ok": false, "detail": ...}`` if it is not configured/reachable."""
    from ..dewatermark import health, DewatermarkError
    try:
        return {"ok": True, **health()}
    except DewatermarkError as e:
        return {"ok": False, "detail": str(e)}


@mcp.tool()
def remove_watermark(input_path: str, regions: List[List[int]],
                     out_path: Optional[str] = None, pad: int = 48,
                     feather: int = 4, dilate: int = 9) -> dict:
    """Erase a static watermark/logo from a video via the remote LaMa server.

    ``input_path`` is a local video file. ``regions`` is one or more boxes
    ``[[x, y, w, h], ...]`` (pixels, in the video's own resolution) covering the
    watermark — e.g. the Gemini/Veo ✦ sparkle (bottom-right) or a ModelScope
    'shutterstock' band. The server inpaints every frame on a padded ROI with
    LaMa (deep inpainting — far cleaner than classical fills on detailed,
    moving backgrounds) and muxes the original audio back, so sound is kept.

    Requires DABWAYO_LAMA_URL (run colab/dabwayo_lama_server.ipynb). ``pad``
    is the ROI padding, ``feather`` the blend softness, ``dilate`` grows the
    mask so edges are fully covered. Returns the cleaned ``out_path``."""
    from ..dewatermark import remove_watermark as _dewm
    from .. import assets as _assets
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"clean_{uuid.uuid4().hex[:8]}.mp4")
    t0 = time.time()
    _dewm(input_path, out_path, regions, pad=pad, feather=feather, dilate=dilate)
    parent = _assets.find_by_path(input_path)        # link provenance if known
    ast = _assets.register(out_path, kind="video", role="dewatermarked",
                           source={"action": "dewatermark", "provider": "lama",
                                   "parent": parent["id"] if parent else None,
                                   "params": {"regions": regions}})
    _log_activity_safe("dewatermark", "워터마크 제거(LaMa)",
                       [parent["id"] if parent else input_path], [ast["id"]])
    return {"ok": True, "path": out_path, "asset_id": ast["id"],
            "parent": parent["id"] if parent else None,
            "seconds": round(time.time() - t0, 2), "regions": regions}
