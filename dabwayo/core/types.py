"""Core value types: colors, vectors, enums.

Internally the engine works in linear-ish float RGBA space with channel
values in [0, 1] and images stored as numpy arrays of shape (H, W, 4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Union

import numpy as np

__all__ = [
    "Color",
    "Vec2",
    "BlendMode",
    "Anchor",
    "Direction",
    "FitMode",
    "ColorLike",
]


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3,8})$")

_NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (229, 57, 53),
    "green": (67, 160, 71), "blue": (30, 136, 229), "yellow": (253, 216, 53),
    "orange": (251, 140, 0), "purple": (142, 36, 170), "pink": (236, 64, 122),
    "cyan": (0, 188, 212), "magenta": (216, 27, 96), "gray": (120, 120, 120),
    "grey": (120, 120, 120), "transparent": (0, 0, 0),
    "navy": (13, 27, 62), "teal": (0, 137, 123), "gold": (255, 193, 7),
    "slate": (51, 65, 85), "charcoal": (28, 28, 32), "ink": (15, 17, 26),
}


@dataclass(frozen=True)
class Color:
    """An RGBA color. Components are floats in [0, 1]."""

    r: float = 0.0
    g: float = 0.0
    b: float = 0.0
    a: float = 1.0

    @staticmethod
    def parse(value: "ColorLike") -> "Color":
        """Coerce many representations into a Color.

        Accepts: Color, hex string ("#RRGGBB"/"#RGB"/"#RRGGBBAA"), named
        color string, "transparent", (r,g,b) / (r,g,b,a) tuples in 0-255,
        or a single float (gray).
        """
        if isinstance(value, Color):
            return value
        if isinstance(value, (int, float)):
            v = float(value)
            return Color(v, v, v, 1.0)
        if isinstance(value, str):
            s = value.strip().lower()
            if s == "transparent":
                return Color(0, 0, 0, 0)
            if s in _NAMED:
                r, g, b = _NAMED[s]
                return Color(r / 255, g / 255, b / 255, 1.0)
            m = _HEX_RE.match(s)
            if not m:
                raise ValueError(f"Cannot parse color: {value!r}")
            h = m.group(1)
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            if len(h) == 4:
                h = "".join(c * 2 for c in h)
            vals = [int(h[i:i + 2], 16) / 255 for i in range(0, len(h), 2)]
            if len(vals) == 3:
                vals.append(1.0)
            return Color(*vals)
        if isinstance(value, (tuple, list)):
            vals = list(value)
            if len(vals) == 3:
                vals.append(255)
            if max(vals) > 1.0:
                vals = [v / 255 for v in vals]
            return Color(*[float(v) for v in vals[:4]])
        raise ValueError(f"Cannot parse color: {value!r}")

    def with_alpha(self, a: float) -> "Color":
        return Color(self.r, self.g, self.b, a)

    @property
    def rgb(self) -> Tuple[float, float, float]:
        return (self.r, self.g, self.b)

    @property
    def rgba(self) -> Tuple[float, float, float, float]:
        return (self.r, self.g, self.b, self.a)

    def to_uint8(self) -> Tuple[int, int, int, int]:
        return tuple(int(round(max(0.0, min(1.0, c)) * 255)) for c in self.rgba)

    def as_array(self) -> np.ndarray:
        return np.array(self.rgba, dtype=np.float32)


@dataclass(frozen=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    @staticmethod
    def parse(value: Union["Vec2", Tuple[float, float], list]) -> "Vec2":
        if isinstance(value, Vec2):
            return value
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return Vec2(float(value[0]), float(value[1]))
        raise ValueError(f"Cannot parse Vec2: {value!r}")

    def __iter__(self):
        yield self.x
        yield self.y


class BlendMode(str, Enum):
    NORMAL = "normal"
    ADD = "add"
    SCREEN = "screen"
    MULTIPLY = "multiply"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    LIGHTEN = "lighten"
    DARKEN = "darken"
    DIFFERENCE = "difference"


class Anchor(str, Enum):
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP = "top"
    TOP_RIGHT = "top_right"
    LEFT = "left"
    RIGHT = "right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM = "bottom"
    BOTTOM_RIGHT = "bottom_right"


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class FitMode(str, Enum):
    CONTAIN = "contain"
    COVER = "cover"
    STRETCH = "stretch"
    NONE = "none"


ColorLike = Union[Color, str, float, int, Tuple, list]
