"""2D transform applied to a rendered layer before compositing.

Supports animatable position, scale, rotation, anchor and opacity. The
transform places a layer onto the timeline canvas; coordinates are in
pixels with the origin at the top-left of the frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .keyframe import AnimatedProperty
from .types import Anchor


@dataclass
class Transform:
    # position of the anchor point on the canvas, in pixels
    position: AnimatedProperty = field(default_factory=lambda: AnimatedProperty([0.0, 0.0]))
    scale: AnimatedProperty = field(default_factory=lambda: AnimatedProperty([1.0, 1.0]))
    rotation: AnimatedProperty = field(default_factory=lambda: AnimatedProperty(0.0))
    opacity: AnimatedProperty = field(default_factory=lambda: AnimatedProperty(1.0))
    anchor: Anchor = Anchor.CENTER
    explicit_position: bool = False     # False -> engine centers on canvas

    @staticmethod
    def from_spec(spec: dict | None) -> "Transform":
        spec = spec or {}
        t = Transform()
        if "position" in spec:
            t.position = AnimatedProperty.coerce(spec["position"])
            t.explicit_position = True
        if "scale" in spec:
            s = spec["scale"]
            if isinstance(s, (int, float)):
                s = [float(s), float(s)]
            t.scale = AnimatedProperty.coerce(s)
        if "rotation" in spec:
            t.rotation = AnimatedProperty.coerce(spec["rotation"])
        if "opacity" in spec:
            t.opacity = AnimatedProperty.coerce(spec["opacity"])
        if "anchor" in spec:
            t.anchor = Anchor(spec["anchor"])
        return t

    def sample(self, t: float) -> dict:
        pos = self.position.at(t)
        scale = self.scale.at(t)
        if isinstance(scale, (int, float)):
            scale = [float(scale), float(scale)]
        return {
            "position": (float(pos[0]), float(pos[1])),
            "scale": (float(scale[0]), float(scale[1])),
            "rotation": float(self.rotation.at(t)),
            "opacity": float(self.opacity.at(t)),
            "anchor": self.anchor,
            "explicit_position": self.explicit_position,
        }


def anchor_offset(anchor: Anchor, w: int, h: int) -> tuple[float, float]:
    """Offset (in layer pixels) from the layer's top-left to its anchor."""
    fx = {
        Anchor.TOP_LEFT: 0.0, Anchor.LEFT: 0.0, Anchor.BOTTOM_LEFT: 0.0,
        Anchor.TOP: 0.5, Anchor.CENTER: 0.5, Anchor.BOTTOM: 0.5,
        Anchor.TOP_RIGHT: 1.0, Anchor.RIGHT: 1.0, Anchor.BOTTOM_RIGHT: 1.0,
    }[anchor]
    fy = {
        Anchor.TOP_LEFT: 0.0, Anchor.TOP: 0.0, Anchor.TOP_RIGHT: 0.0,
        Anchor.LEFT: 0.5, Anchor.CENTER: 0.5, Anchor.RIGHT: 0.5,
        Anchor.BOTTOM_LEFT: 1.0, Anchor.BOTTOM: 1.0, Anchor.BOTTOM_RIGHT: 1.0,
    }[anchor]
    return fx * w, fy * h
