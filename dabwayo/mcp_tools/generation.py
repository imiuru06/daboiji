"""Generative-video tools: list backends, generate a clip onto the timeline."""
from __future__ import annotations

import os
import time
import uuid
from typing import List, Optional

from .app import mcp, _OUTPUT_DIR, _log_activity_safe
from .clips import add_media

__all__ = ["list_video_providers", "generate_video"]


@mcp.tool()
def list_video_providers() -> dict:
    """List generative-video backends and whether each is ready (which API key
    / Colab URL is needed). The 'active' one is what generate_video will use."""
    from ..generation.registry import list_providers
    return list_providers()


@mcp.tool()
def generate_video(project_id: str, prompt: str, mode: str = "t2v",
                   image: Optional[str] = None, duration: float = 4.0,
                   fps: float = 24.0, width: int = 768, height: int = 432,
                   seed: Optional[int] = None, steps: int = 30,
                   guidance: float = 3.0, provider: Optional[str] = None,
                   add_to_timeline: bool = True, start: float = 0.0,
                   track: Optional[str] = None, fit: str = "cover",
                   transform: Optional[dict] = None,
                   effects: Optional[List[dict]] = None,
                   transition_in: Optional[dict] = None,
                   transition_out: Optional[dict] = None) -> dict:
    """Generate a video clip with a generative model and (by default) drop it
    onto the timeline as a ``video`` clip — so AI-generated footage composites
    with text/effects/camera/audio like anything else.

    mode='t2v' generates from ``prompt``; mode='i2v' animates ``image`` (a path)
    guided by ``prompt``. The backend is chosen by list_video_providers()'s
    'active' entry unless ``provider`` is given (local|remote|replicate|fal|
    huggingface). 'local' needs no GPU/key (abstract, not photoreal); 'remote'
    targets a Google Colab GPU server (set DABWAYO_VIDEOGEN_URL). If
    ``add_to_timeline`` is false, only the asset is produced.
    """
    from ..generation import generate_video as _gen
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(_OUTPUT_DIR, f"gen_{uuid.uuid4().hex[:8]}.mp4")
    t0 = time.time()
    res = _gen(prompt, out_path, mode=mode, image=image, duration=duration,
               fps=fps, width=width, height=height, seed=seed, steps=steps,
               guidance=guidance, provider=provider)
    info = res.as_dict()
    info["ok"] = True
    info["generate_seconds"] = round(time.time() - t0, 2)
    # register as an asset (provenance) + timeline log
    from .. import assets as _assets
    ast = _assets.register(res.path, kind="video", role="raw",
                           source={"action": "generate", "provider": res.provider,
                                   "prompt": prompt, "params": {"mode": mode,
                                   "duration": duration, "seed": seed, "steps": steps}},
                           projects=[project_id] if add_to_timeline else [])
    info["asset_id"] = ast["id"]
    _log_activity_safe("generate", f"{res.provider} {mode} 생성",
                       [f"prompt: {prompt[:60]}"], [ast["id"]])
    if add_to_timeline:
        clip = add_media(project_id, res.path, "video", start,
                         res.frames / float(res.fps), fit, None, track,
                         transform, effects, transition_in, transition_out)
        info["track"] = clip.get("track")
        info["clip_index"] = clip.get("clip_index")
    return info
