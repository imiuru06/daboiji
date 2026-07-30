"""Dabwayo — a modular video engine driven through an MCP tool interface.

The **supported, primary interface is the MCP tools** (``dabwayo.mcp_server`` /
the ``dabwayo.mcp_tools`` package): agents and the Studio web author, edit and
render projects by calling tools, all over one serializable JSON spec. Run it
with ``python -m dabwayo.mcp_server``.

Everything below (``Project``, ``Timeline``, ``render`` …) is the **low-level
engine** those tools drive. It stays importable for advanced/embedded use and
the test suite, but for authoring prefer the MCP tools — they are the single
place editing logic lives, so the engine and the web never diverge.

    >>> from dabwayo.builder import Project        # low-level engine (advanced)
    >>> p = Project(1280, 720, fps=30)
    >>> p.render("out.mp4")
"""
from __future__ import annotations

# Populate registries via import side effects.
from . import effects, elements, transitions  # noqa: F401
# Low-level engine surface — kept importable for advanced/embedded use and the
# test suite. The MCP tools (dabwayo.mcp_server) are the supported interface.
from .builder import Clip, Project, Track, keyframes  # noqa: F401
from .core import (  # noqa: F401
    Anchor, AnimatedProperty, BlendMode, Color, Direction, FitMode,
    Keyframe, Timeline, Transform,
)
from .render.context import RenderContext  # noqa: F401
from .render.engine import RenderResult, render, render_frame, render_thumbnail  # noqa: F401
from .generation import generate_video, list_providers as list_video_providers  # noqa: F401

__version__ = "0.1.0"


def capabilities() -> dict:
    """Machine-readable summary of what the engine can do (for discovery)."""
    from .effects.base import available as fx_available
    from .elements.base import available_types
    from .transitions.base import available as tr_available
    from .core.easing import REGISTRY as easings
    from .core.presets import CAMERA_PRESETS as _CAMERA_PRESETS
    from .core.presets import LAYOUT_MODES as _LAYOUT_MODES
    from .generation.registry import list_providers as _gen_providers
    return {
        "version": __version__,
        "elements": available_types(),
        "effects": fx_available(),
        "transitions": tr_available(),
        "blend_modes": [m.value for m in BlendMode],
        "easings": sorted(easings),
        "anchors": [a.value for a in Anchor],
        "camera_moves": list(_CAMERA_PRESETS),
        "layout_modes": list(_LAYOUT_MODES),
        "generators": _gen_providers(),
    }


__all__ = [
    "Project", "Track", "Clip", "keyframes", "Timeline", "Transform",
    "Color", "Anchor", "BlendMode", "Direction", "FitMode",
    "AnimatedProperty", "Keyframe", "render", "render_frame",
    "render_thumbnail", "RenderResult", "RenderContext", "capabilities",
    "generate_video", "list_video_providers",
    "__version__",
]
