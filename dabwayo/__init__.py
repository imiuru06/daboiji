"""Dabwayo — a modular, scriptable video rendering engine with an MCP API.

Quick start
-----------
>>> from dabwayo import Project
>>> p = Project(1280, 720, fps=30, background="#0b0e16")
>>> t = p.track("video")
>>> t.add(Project.text("Hello", size=120), start=0, duration=3).transition_in("fade")
>>> p.render("out.mp4")

Everything is driven by a plain JSON spec, so projects are serializable and
editable by other tools/agents (see ``dabwayo.mcp_server``).
"""
from __future__ import annotations

# Populate registries via import side effects.
from . import effects, elements, transitions  # noqa: F401
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
    from .generation.registry import list_providers as _gen_providers
    return {
        "version": __version__,
        "elements": available_types(),
        "effects": fx_available(),
        "transitions": tr_available(),
        "blend_modes": [m.value for m in BlendMode],
        "easings": sorted(easings),
        "anchors": [a.value for a in Anchor],
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
