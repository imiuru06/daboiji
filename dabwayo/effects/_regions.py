"""Build alpha masks from region specs.

A region spec is a dict (or list of dicts) describing a shape, used by the
censor/mask/inpaint effects to target part of the frame:

    {"shape": "rect",    "rect": [x, y, w, h]}
    {"shape": "ellipse", "rect": [x, y, w, h]}
    {"shape": "polygon", "points": [[x, y], ...]}

Optional top-level keys: ``feather`` (px soft edge), ``invert`` (bool),
``norm`` (interpret coords as 0..1 of frame size). Returns a float32 mask of
shape (H, W) in [0, 1].
"""
from __future__ import annotations

from typing import Union

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

RegionSpec = Union[dict, list]


def _draw_one(draw: ImageDraw.ImageDraw, spec: dict, w: int, h: int):
    norm = spec.get("norm", False)

    def sx(v):
        return v * w if norm else v

    def sy(v):
        return v * h if norm else v

    shape = spec.get("shape", "rect")
    if shape in ("rect", "rounded_rect"):
        x, y, rw, rh = spec["rect"]
        box = [sx(x), sy(y), sx(x + rw), sy(y + rh)]
        r = spec.get("radius", 0)
        if r:
            draw.rounded_rectangle(box, radius=r * (w if norm else 1), fill=255)
        else:
            draw.rectangle(box, fill=255)
    elif shape in ("ellipse", "circle"):
        x, y, rw, rh = spec["rect"]
        draw.ellipse([sx(x), sy(y), sx(x + rw), sy(y + rh)], fill=255)
    elif shape == "polygon":
        pts = [(sx(px), sy(py)) for px, py in spec["points"]]
        draw.polygon(pts, fill=255)
    else:
        raise ValueError(f"Unknown mask shape {shape!r}")


def build_mask(w: int, h: int, spec: RegionSpec) -> np.ndarray:
    """Return an (H, W) float32 mask in [0, 1] for the region spec."""
    specs = spec if isinstance(spec, list) else [spec]
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    feather = 0
    invert = False
    for s in specs:
        _draw_one(draw, s, w, h)
        feather = max(feather, s.get("feather", 0))
        invert = invert or s.get("invert", False)
    if feather > 0:
        img = img.filter(ImageFilter.GaussianBlur(feather))
    mask = np.asarray(img, np.float32) / 255.0
    if invert:
        mask = 1.0 - mask
    return mask
