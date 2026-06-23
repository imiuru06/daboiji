"""Auto-compose multiple media into one connected timeline.

Turns a list of clips (typically registered assets) into a ready-to-render
project spec: clips are laid out back-to-back, durations come from each clip's
media metadata, soft fade transitions join them, and an optional title intro
and a light cinematic master grade are added. This is the programmatic form of
the dashboard's "여러 미디어를 연결하는 클립" recipe.
"""
from __future__ import annotations

from typing import Optional

from .builder import Project

DEFAULT_CLIP_SECONDS = 4.0


def build_sequence_spec(clips: list[dict], *, width: int = 1280, height: int = 720,
                        fps: float = 24.0, background: str = "#05070d",
                        transition: str = "fade", transition_duration: float = 0.5,
                        title: Optional[str] = None, name: str = "sequence") -> dict:
    """Build a project spec that plays ``clips`` in order as one video.

    ``clips`` items: ``{"path": str, "duration": float|None}``. Returns the
    JSON-able project spec (not saved).
    """
    if not clips:
        raise ValueError("compose: no clips given")

    p = Project(width, height, fps=fps, background=background, name=name)
    track = p.track("video", "footage")
    t = 0.0
    for c in clips:
        dur = float(c.get("duration") or DEFAULT_CLIP_SECONDS)
        clip = track.add(Project.video(c["path"], fit="cover", size=[width, height]), t, dur)
        clip.transition_in(transition, transition_duration)
        clip.transition_out(transition, transition_duration)
        t += dur
    total = t

    if title:
        tt = p.track("video", "title")
        (tt.add(Project.text(title, font="display", size=max(36, int(height * 0.12)),
                             color="#ffffff", letter_spacing=4.0,
                             shadow={"color": "#000000aa", "offset": [0, 4], "blur": 18}),
                0.4, min(3.0, total))
           .position([width / 2, height * 0.16])
           .transition_in("fade", 0.5).transition_out("fade", 0.5))

    p.master_effect("color_grade", contrast=1.05, saturation=1.08)
    p.master_effect("vignette", amount=0.35, softness=0.6)
    p.spec["duration"] = round(total, 3)
    return p.spec
