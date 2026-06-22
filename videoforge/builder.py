"""Ergonomic project builder.

The canonical project representation is a plain JSON-able ``dict`` (the
"spec"). :class:`Project` accumulates that spec through fluent helpers and
can render it or serialize it. Because everything is a dict, projects are
trivially storable, diff-able, and editable by other agents/tools.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .core.timeline import Timeline
from .render.engine import RenderResult, render, render_thumbnail


def keyframes(*pairs, default=None) -> dict:
    """Build a keyframed property.

    ``keyframes((0, 0), (1.0, 100, "ease_out_cubic"))`` -> animated property
    where each tuple is (time, value[, easing]).
    """
    kfs = []
    for p in pairs:
        if len(p) == 2:
            kfs.append({"time": p[0], "value": p[1]})
        else:
            kfs.append({"time": p[0], "value": p[1], "easing": p[2]})
    return {"default": default if default is not None else (pairs[0][1] if pairs else 0), "keyframes": kfs}


class Clip:
    """Wraps a clip spec dict and exposes chainable mutators."""

    def __init__(self, spec: dict):
        self.spec = spec

    def transform(self, **kw) -> "Clip":
        self.spec.setdefault("transform", {}).update(kw)
        return self

    def position(self, value) -> "Clip":
        return self.transform(position=value)

    def scale(self, value) -> "Clip":
        return self.transform(scale=value)

    def rotation(self, value) -> "Clip":
        return self.transform(rotation=value)

    def opacity(self, value) -> "Clip":
        return self.transform(opacity=value)

    def anchor(self, value) -> "Clip":
        return self.transform(anchor=value)

    def blend(self, mode: str) -> "Clip":
        self.spec["blend_mode"] = mode
        return self

    def depth(self, value: float) -> "Clip":
        """Camera reaction: 1=foreground (full parallax), 0=locked backdrop."""
        self.spec["depth"] = value
        return self

    def effect(self, type: str, **params) -> "Clip":
        self.spec.setdefault("effects", []).append({"type": type, **params})
        return self

    def fx(self, *effects: dict) -> "Clip":
        self.spec.setdefault("effects", []).extend(effects)
        return self

    def transition_in(self, type: str = "fade", duration: float = 0.5, **kw) -> "Clip":
        self.spec["transition_in"] = {"type": type, "duration": duration, **kw}
        return self

    def transition_out(self, type: str = "fade", duration: float = 0.5, **kw) -> "Clip":
        self.spec["transition_out"] = {"type": type, "duration": duration, **kw}
        return self


class Track:
    def __init__(self, spec: dict):
        self.spec = spec

    def add(self, element: dict, start: float = 0.0, duration: float = 5.0, **kw) -> Clip:
        clip = {"element": element, "start": start, "duration": duration, **kw}
        self.spec.setdefault("clips", []).append(clip)
        return Clip(clip)


class Project:
    def __init__(self, width: int = 1920, height: int = 1080, fps: float = 30.0,
                 background: str = "#0b0e16", duration: Optional[float] = None,
                 name: str = "untitled"):
        self.spec: Dict[str, Any] = {
            "name": name, "width": width, "height": height, "fps": fps,
            "background": background, "tracks": [], "effects": [],
        }
        if duration:
            self.spec["duration"] = duration

    # ---- structure ---------------------------------------------------
    def track(self, kind: str = "video", name: str = "") -> Track:
        t = {"kind": kind, "name": name, "clips": []}
        self.spec["tracks"].append(t)
        return Track(t)

    def audio(self, path: str, start: float = 0.0, **kw) -> "Project":
        tr = self.track("audio", name=kw.pop("name", "audio"))
        tr.spec["clips"].append({"path": path, "start": start, **kw})
        return self

    def master_effect(self, type: str, **params) -> "Project":
        self.spec["effects"].append({"type": type, **params})
        return self

    def camera(self, pan=None, zoom=None, rotation=None, focus=None) -> "Project":
        """Set a keyframeable virtual camera (pan px, zoom, rotation deg).
        Combine with per-clip ``depth`` for parallax."""
        cam = {}
        if pan is not None:
            cam["pan"] = pan
        if zoom is not None:
            cam["zoom"] = zoom
        if rotation is not None:
            cam["rotation"] = rotation
        if focus is not None:
            cam["focus"] = focus
        self.spec["camera"] = cam
        return self

    # ---- element factories (static dicts) ----------------------------
    @staticmethod
    def solid(color: str, size=None) -> dict:
        d = {"type": "solid", "color": color}
        if size:
            d["size"] = list(size)
        return d

    @staticmethod
    def gradient(stops, kind="linear", angle=90.0, **kw) -> dict:
        return {"type": "gradient", "stops": stops, "kind": kind, "angle": angle, **kw}

    @staticmethod
    def text(text: str, **kw) -> dict:
        return {"type": "text", "text": text, **kw}

    @staticmethod
    def image(path: str, **kw) -> dict:
        return {"type": "image", "path": path, **kw}

    @staticmethod
    def video(path: str, **kw) -> dict:
        return {"type": "video", "path": path, **kw}

    @staticmethod
    def shape(shape: str = "rect", **kw) -> dict:
        return {"type": "shape", "shape": shape, **kw}

    # ---- serialization & render --------------------------------------
    def to_dict(self) -> dict:
        return self.spec

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.spec, indent=indent)

    def save(self, path: str) -> str:
        with open(path, "w") as f:
            f.write(self.to_json())
        return path

    @staticmethod
    def load(path: str) -> "Project":
        with open(path) as f:
            return Project.from_dict(json.load(f))

    @staticmethod
    def from_dict(spec: dict) -> "Project":
        p = Project()
        p.spec = spec
        return p

    def timeline(self) -> Timeline:
        return Timeline.from_spec(self.spec)

    def render(self, out_path: str, **kw) -> RenderResult:
        return render(self.timeline(), out_path, **kw)

    def thumbnail(self, out_path: str, t: float = 0.0) -> str:
        return render_thumbnail(self.timeline(), out_path, t)
