"""Keyframe-based animation of scalar and vector properties.

An :class:`AnimatedProperty` is the universal mechanism for motion in the
engine. A property is either a constant or a series of keyframes. At render
time each clip evaluates its animated properties at the local clip time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Union

from . import easing
from .types import Color

Number = Union[float, int]
Animatable = Union[Number, Sequence[float], Color]


@dataclass
class Keyframe:
    time: float                      # local clip time in seconds
    value: Animatable
    easing: str = "ease_in_out"      # easing used to reach THIS keyframe


def _lerp(a, b, f):
    if isinstance(a, Color) or isinstance(b, Color):
        a = a if isinstance(a, Color) else Color.parse(a)
        b = b if isinstance(b, Color) else Color.parse(b)
        return Color(
            a.r + (b.r - a.r) * f,
            a.g + (b.g - a.g) * f,
            a.b + (b.b - a.b) * f,
            a.a + (b.a - a.a) * f,
        )
    if isinstance(a, (list, tuple)):
        return [av + (bv - av) * f for av, bv in zip(a, b)]
    return a + (b - a) * f


@dataclass
class AnimatedProperty:
    """A value that may be constant or driven by keyframes."""

    default: Animatable = 0.0
    keyframes: List[Keyframe] = field(default_factory=list)

    @staticmethod
    def coerce(value) -> "AnimatedProperty":
        if isinstance(value, AnimatedProperty):
            return value
        if isinstance(value, dict) and "keyframes" in value:
            kfs = [
                Keyframe(k["time"], k["value"], k.get("easing", "ease_in_out"))
                for k in value["keyframes"]
            ]
            return AnimatedProperty(value.get("default", 0.0), kfs)
        return AnimatedProperty(default=value)

    def add(self, time: float, value: Animatable, easing: str = "ease_in_out") -> "AnimatedProperty":
        self.keyframes.append(Keyframe(time, value, easing))
        self.keyframes.sort(key=lambda k: k.time)
        return self

    @property
    def is_animated(self) -> bool:
        return len(self.keyframes) > 0

    def at(self, t: float):
        """Evaluate the property at local time ``t`` (seconds)."""
        kfs = self.keyframes
        if not kfs:
            return self.default
        if t <= kfs[0].time:
            return kfs[0].value
        if t >= kfs[-1].time:
            return kfs[-1].value
        for i in range(1, len(kfs)):
            if t <= kfs[i].time:
                prev, nxt = kfs[i - 1], kfs[i]
                span = nxt.time - prev.time
                f = 0.0 if span <= 0 else (t - prev.time) / span
                f = easing.get(nxt.easing)(max(0.0, min(1.0, f)))
                return _lerp(prev.value, nxt.value, f)
        return kfs[-1].value
