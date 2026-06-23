"""Clip transitions (in/out reveals).

A transition is evaluated with a visibility parameter ``p`` in [0, 1],
where p=1 means the clip is fully present and p=0 means fully gone. The
clip computes ``p`` from its in/out windows; the transition returns a
:class:`TransitionResult` describing how to modify the layer before it is
placed on the canvas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Type

import numpy as np

from ..render.context import RenderContext

_REGISTRY: Dict[str, Type["Transition"]] = {}


def register(name: str):
    def deco(cls):
        cls.name = name
        _REGISTRY[name] = cls
        return cls
    return deco


def from_spec(spec: dict) -> "Transition":
    name = spec.get("type", "fade")
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown transition {name!r}. Available: {', '.join(sorted(_REGISTRY))}"
        )
    params = {k: v for k, v in spec.items() if k not in ("type", "duration")}
    tr = _REGISTRY[name](**params)
    tr.duration = float(spec.get("duration", 0.5))
    return tr


def available() -> list:
    return sorted(_REGISTRY)


@dataclass
class TransitionResult:
    layer: np.ndarray
    opacity: float = 1.0
    offset: tuple = (0.0, 0.0)      # extra pixel offset
    scale: float = 1.0             # extra uniform scale


class Transition:
    name = "base"

    def __init__(self, **params):
        self.params = params
        self.duration = 0.5

    def apply(self, layer: np.ndarray, p: float, entering: bool,
              ctx: RenderContext) -> TransitionResult:
        raise NotImplementedError
