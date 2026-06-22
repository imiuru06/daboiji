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
from ..core.camera import apply_camera
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


def render_clip_layer(clip, ctx: RenderContext, t: float, cam_sample=None):
    """Render one clip; return ``(arr, x, y, opacity)`` for compositing."""
    lt = clip.local_time(t)
    layer = clip.element.render(ctx, lt)
    for fx in clip.effects:
        layer = fx.apply(layer, ctx, lt)

    samp = clip.transform.sample(lt)
    if not samp["explicit_position"]:
        samp["position"] = (ctx.width / 2.0, ctx.height / 2.0)
    if cam_sample is not None:
        samp = apply_camera(samp, cam_sample, clip.depth)
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

    arr, x, y = place_layer(
        layer, ctx.width, ctx.height,
        samp["position"], samp["scale"], samp["rotation"], samp["anchor"],
        extra_offset=offset, extra_scale=extra_scale,
    )
    return arr, x, y, opacity


def render_frame(timeline: Timeline, ctx: RenderContext, t: float) -> np.ndarray:
    bg = Color.parse(timeline.background)
    canvas = compositor.new_canvas(ctx.width, ctx.height, bg.with_alpha(1.0).rgba)
    cam_sample = (timeline.camera.sample(t, ctx.width, ctx.height)
                  if timeline.camera else None)
    for track in timeline.video_tracks:
        for clip in track.active_clips(t):
            arr, x, y, opacity = render_clip_layer(clip, ctx, t, cam_sample)
            canvas = compositor.composite(
                canvas, arr, x, y, opacity * track.opacity, clip.blend_mode
            )
    # master effects operate on the flattened (opaque) frame
    for fx in timeline.effects:
        canvas = fx.apply(canvas, ctx, t)
    rgb = compositor.flatten(canvas, bg.rgb)
    return compositor.to_uint8(rgb)


def render(timeline: Timeline, out_path: str, *, crf: int = 18,
           preset: str = "medium", progress: Optional[Callable] = None,
           t_start: float = 0.0, t_end: Optional[float] = None) -> RenderResult:
    """Render the timeline to MP4.

    ``t_start``/``t_end`` restrict output to a time window (seconds) — useful
    for quickly previewing a section you just edited without re-rendering the
    whole video. Audio is included only for a full render.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    duration = timeline.computed_duration()
    fps = timeline.fps
    is_range = t_start > 0.0 or (t_end is not None and t_end < duration)
    t_end = duration if t_end is None else min(t_end, duration)
    f0 = int(round(t_start * fps))
    f1 = int(round(t_end * fps))
    total = max(1, f1 - f0)

    audio_path = None
    if not is_range:
        audio_clips = [c for tr in timeline.audio_tracks for c in tr.clips]
        audio_path = mix_audio(audio_clips, duration) if audio_clips else None

    enc = FrameEncoder(out_path, timeline.width, timeline.height, fps,
                       crf=crf, preset=preset, audio_path=audio_path)
    try:
        for n, i in enumerate(range(f0, f1)):
            t = i / fps
            ctx = RenderContext(timeline.width, timeline.height, fps,
                                frame_index=i, time=t)
            enc.write(render_frame(timeline, ctx, t))
            if progress and (n % 10 == 0 or n == total - 1):
                progress(n + 1, total)
    finally:
        enc.close()
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass

    return RenderResult(out_path, timeline.width, timeline.height,
                        fps, total, total / fps)


def render_thumbnail(timeline: Timeline, out_path: str, t: float = 0.0) -> str:
    from PIL import Image
    ctx = RenderContext(timeline.width, timeline.height, timeline.fps,
                        frame_index=int(t * timeline.fps), time=t)
    rgb = render_frame(timeline, ctx, t)
    Image.fromarray(rgb, "RGB").save(out_path)
    return out_path
