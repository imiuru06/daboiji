"""Voiceover / TTS tools: list providers, synthesize narration, add it to the mix.

Follows the reviewed asset principle: dabwayo wraps the external voice model
(provider), then owns only the *index* (registers the result as a tracked
asset) and places it on the timeline — the bytes live wherever the output dir
points. TTS is optional: add_audio your own narration if you have no provider."""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from .app import mcp, _proj, _commit, _OUTPUT_DIR, _log_activity_safe, _new_clip_id

__all__ = ["list_tts_providers", "synthesize_voice", "add_voiceover"]


@mcp.tool()
def list_tts_providers() -> dict:
    """List text-to-speech backends and whether each is ready (which key/URL or
    package it needs), plus the active one. TTS is optional — narration can also
    be a file you add with add_audio."""
    from ..tts import list_providers
    return {"ok": True, **list_providers()}


@mcp.tool()
def synthesize_voice(text: str, out_path: Optional[str] = None,
                     provider: Optional[str] = None, voice: str = "",
                     register: bool = True) -> dict:
    """Synthesize narration from ``text`` to an audio file.

    ``provider`` picks a backend (local|remote|openai|elevenlabs); omit to
    auto-select. ``voice`` is a provider-specific voice id/name. By default the
    result is registered as a tracked audio asset (provenance) and its path +
    asset_id returned. Requires a configured provider (see list_tts_providers)."""
    from ..tts import synth
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"vo_{uuid.uuid4().hex[:8]}.mp3")
    t0 = time.time()
    res = synth(text, out_path, provider=provider, voice=voice or None)
    info = {"ok": True, **res, "seconds": round(time.time() - t0, 2)}
    if register:
        from .. import assets as _assets
        ast = _assets.register(res["path"], kind="audio", role="voiceover",
                               source={"action": "tts", "provider": res["provider"],
                                       "prompt": text[:200],
                                       "params": {"voice": res.get("voice")}})
        info["asset_id"] = ast["id"]
        _log_activity_safe("tts", f"보이스오버({res['provider']})",
                           [text[:60]], [ast["id"]])
    return info


@mcp.tool()
def add_voiceover(project_id: str, text: str, start: float = 0.0,
                  provider: Optional[str] = None, voice: str = "",
                  gain_db: float = 0.0, fade_in: float = 0.0,
                  fade_out: float = 0.0) -> dict:
    """Synthesize narration and add it to the project's soundtrack in one call.

    Combines synthesize_voice with add_audio: TTS the ``text`` (via the active
    provider), register it, and place it on an audio track at ``start`` with the
    given level/fades. Needs a configured TTS provider; for narration you
    already have, use add_audio directly. Returns the audio clip id + asset id."""
    spec = _proj(project_id)                       # validate early
    v = synthesize_voice(text, provider=provider, voice=voice, register=True)
    track = None
    for tr in spec["tracks"]:
        if tr.get("kind") == "audio":
            track = tr
            break
    if track is None:
        track = {"kind": "audio", "name": "audio", "clips": []}
        spec["tracks"].append(track)
    clip = {"id": _new_clip_id(), "path": v["path"], "start": start,
            "duration": None, "gain_db": gain_db, "fade_in": fade_in,
            "fade_out": fade_out, "in_point": 0.0}
    track["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "clip_id": clip["id"], "asset_id": v.get("asset_id"),
            "path": v["path"], "provider": v["provider"]}
