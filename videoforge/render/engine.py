"""Render orchestrator: timeline -> frames -> encoded video.

Pipeline per frame:
  1. start from the timeline background
  2. for each video track (bottom to top):
       for each active clip:
         render element -> apply clip effects -> place via transform
         -> apply transition -> composite with blend mode and opacity
  3. apply master/timeline effects to the flattened frame
  4. encode the frame
Audio tracks are mixed separately and muxed by the encoder.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..audio.mixer import mix_audio
from ..core.timeline import Timeline, TrackKind
from ..core.types import Color
from . import compositor
from .context import RenderContext
from .encoder import FrameEncoder
from .rasterizer import place_layer


@dataclass
class RenderResult:
    path: str
    width: int
    height: int
    fps: float
    frames: int
    duration: float


def render_clip_layer(clip, ctx: RenderContext, t: float) -> tuple[np.ndarray, float]:
    """Render one clip to a canvas-sized RGBA layer + opacity. None if hidden."""
    lt = clip.local_time(t)
    layer = clip.element.render(ctx, lt)
    for fx in clip.effects:
        layer = fx.apply(layer, ctx, lt)

    samp = clip.transform.sample(lt)
    if not samp["explicit_position"]:
        samp["position"] = (ctx.width / 2.0, ctx.height / 2.0)
    opacity = samp["opacity"]
    offset = (0.0, 0.0)
    extra_scale = 1.0

    p = clip.visibility(t)
    entering = lt < (clip.transition_in.duration if clip.transition_in else 0)
    active_tr = None
    if clip.transition_in and lt < clip.transition_in.duration:
        active_tr = clip.transition_in
    elif clip.transition_out and (clip.duration - lt) < clip.transition_out.duration:
        active_tr = clip.transition_out
        entering = False
    if active_tr is not None and p < 1.0:
        res = active_tr.apply(layer, p, entering, ctx)
        layer = res.layer
        opacity *= res.opacity
        offset = res.offset
        extra_scale = res.scale

    placed = place_layer(
        layer, ctx.width, ctx.height,
        samp["position"], samp["scale"], samp["rotation"], samp["anchor"],
        extra_offset=offset, extra_scale=extra_scale,
    )
    return placed, opacity


def render_frame(timeline: Timeline, ctx: RenderContext, t: float) -> np.ndarray:
    bg = Color.parse(timeline.background)
    canvas = compositor.new_canvas(ctx.width, ctx.height, bg.with_alpha(1.0).rgba)
    for track in timeline.video_tracks:
        for clip in track.active_clips(t):
            placed, opacity = render_clip_layer(clip, ctx, t)
            canvas = compositor.composite(
                canvas, placed, opacity * track.opacity, clip.blend_mode
            )
    # master effects operate on the flattened (opaque) frame
    for fx in timeline.effects:
        canvas = fx.apply(canvas, ctx, t)
    rgb = compositor.flatten(canvas, bg.rgb)
    return compositor.to_uint8(rgb)


def render(timeline: Timeline, out_path: str, *, crf: int = 18,
           preset: str = "medium", progress: Optional[Callable] = None) -> RenderResult:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    total = timeline.total_frames
    duration = timeline.computed_duration()

    audio_clips = [c for tr in timeline.audio_tracks for c in tr.clips]
    audio_path = mix_audio(audio_clips, duration) if audio_clips else None

    enc = FrameEncoder(out_path, timeline.width, timeline.height, timeline.fps,
                       crf=crf, preset=preset, audio_path=audio_path)
    try:
        for i in range(total):
            t = i / timeline.fps
            ctx = RenderContext(timeline.width, timeline.height, timeline.fps,
                                frame_index=i, time=t)
            enc.write(render_frame(timeline, ctx, t))
            if progress and (i % 10 == 0 or i == total - 1):
                progress(i + 1, total)
    finally:
        enc.close()
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass

    return RenderResult(out_path, timeline.width, timeline.height,
                        timeline.fps, total, duration)


def render_thumbnail(timeline: Timeline, out_path: str, t: float = 0.0) -> str:
    from PIL import Image
    ctx = RenderContext(timeline.width, timeline.height, timeline.fps,
                        frame_index=int(t * timeline.fps), time=t)
    rgb = render_frame(timeline, ctx, t)
    Image.fromarray(rgb, "RGB").save(out_path)
    return out_path
