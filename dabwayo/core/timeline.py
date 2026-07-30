"""Timeline data model: Clip, Track, Timeline.

This mirrors a non-linear editor: a Timeline owns ordered Tracks; each
Track owns Clips placed at absolute times. Visual tracks composite from
bottom (index 0) to top. Audio tracks are mixed separately by the encoder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from ..elements.base import Element, from_spec as element_from_spec
from ..effects.base import Effect, from_spec as effect_from_spec
from ..transitions.base import Transition, from_spec as transition_from_spec
from .camera import Camera
from .transform import Transform
from .types import BlendMode


class TrackKind(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class Clip:
    element: Element
    start: float = 0.0                 # absolute start time on timeline (s)
    duration: float = 5.0
    transform: Transform = field(default_factory=Transform)
    effects: List[Effect] = field(default_factory=list)
    blend_mode: BlendMode = BlendMode.NORMAL
    transition_in: Optional[Transition] = None
    transition_out: Optional[Transition] = None
    depth: float = 1.0                 # camera reaction: 1=foreground, 0=locked
    name: str = ""

    @property
    def end(self) -> float:
        return self.start + self.duration

    def active_at(self, t: float) -> bool:
        return self.start <= t < self.end + 1e-6

    def local_time(self, t: float) -> float:
        return t - self.start

    def visibility(self, t: float) -> float:
        """Combined in/out transition visibility p in [0,1] (1=fully present)."""
        lt = self.local_time(t)
        p = 1.0
        if self.transition_in and self.transition_in.duration > 0:
            p = min(p, max(0.0, min(1.0, lt / self.transition_in.duration)))
        if self.transition_out and self.transition_out.duration > 0:
            rem = self.duration - lt
            p = min(p, max(0.0, min(1.0, rem / self.transition_out.duration)))
        return p

    @staticmethod
    def from_spec(spec: dict) -> "Clip":
        clip = Clip(
            element=element_from_spec(spec["element"]),
            start=float(spec.get("start", 0.0)),
            duration=float(spec.get("duration", 5.0)),
            transform=Transform.from_spec(spec.get("transform")),
            effects=[effect_from_spec(e) for e in spec.get("effects", [])],
            blend_mode=BlendMode(spec.get("blend_mode", "normal")),
            depth=float(spec.get("depth", 1.0)),
            name=spec.get("name", ""),
        )
        if spec.get("transition_in"):
            clip.transition_in = transition_from_spec(spec["transition_in"])
        if spec.get("transition_out"):
            clip.transition_out = transition_from_spec(spec["transition_out"])
        return clip


@dataclass
class AudioClip:
    path: str
    start: float = 0.0
    duration: Optional[float] = None
    in_point: float = 0.0          # offset into source file
    gain_db: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    duck: Optional[dict] = None    # sidechain-free ducking envelope (see mixer)

    @staticmethod
    def from_spec(spec: dict) -> "AudioClip":
        return AudioClip(
            path=spec["path"], start=float(spec.get("start", 0.0)),
            duration=spec.get("duration"), in_point=float(spec.get("in_point", 0.0)),
            gain_db=float(spec.get("gain_db", 0.0)),
            fade_in=float(spec.get("fade_in", 0.0)),
            fade_out=float(spec.get("fade_out", 0.0)),
            duck=spec.get("duck"),
        )


@dataclass
class Track:
    kind: TrackKind = TrackKind.VIDEO
    clips: List = field(default_factory=list)
    name: str = ""
    enabled: bool = True
    opacity: float = 1.0

    def active_clips(self, t: float):
        return [c for c in self.clips if c.active_at(t)]

    @staticmethod
    def from_spec(spec: dict) -> "Track":
        kind = TrackKind(spec.get("kind", "video"))
        cls = AudioClip if kind == TrackKind.AUDIO else Clip
        return Track(
            kind=kind,
            clips=[cls.from_spec(c) for c in spec.get("clips", [])],
            name=spec.get("name", ""),
            enabled=spec.get("enabled", True),
            opacity=float(spec.get("opacity", 1.0)),
        )


@dataclass
class Timeline:
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    duration: Optional[float] = None    # None -> derived from content
    background: str = "#000000"
    tracks: List[Track] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)   # master/timeline effects
    camera: "Camera | None" = None
    name: str = "untitled"

    @property
    def video_tracks(self):
        return [t for t in self.tracks if t.kind == TrackKind.VIDEO and t.enabled]

    @property
    def audio_tracks(self):
        return [t for t in self.tracks if t.kind == TrackKind.AUDIO and t.enabled]

    def computed_duration(self) -> float:
        if self.duration:
            return self.duration
        end = 0.0
        for tr in self.tracks:
            for c in tr.clips:
                end = max(end, c.start + (c.duration or 0.0))
        return end or 5.0

    @property
    def total_frames(self) -> int:
        return max(1, int(round(self.computed_duration() * self.fps)))

    @staticmethod
    def from_spec(spec: dict) -> "Timeline":
        return Timeline(
            width=int(spec.get("width", 1920)),
            height=int(spec.get("height", 1080)),
            fps=float(spec.get("fps", 30.0)),
            duration=spec.get("duration"),
            background=spec.get("background", "#000000"),
            tracks=[Track.from_spec(t) for t in spec.get("tracks", [])],
            effects=[effect_from_spec(e) for e in spec.get("effects", [])],
            camera=Camera.from_spec(spec.get("camera")),
            name=spec.get("name", "untitled"),
        )
