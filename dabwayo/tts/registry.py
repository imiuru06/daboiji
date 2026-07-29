"""TTS provider selection — pluggable and optional.

Default (``DABWAYO_TTS_PROVIDER`` unset/``auto``):
  1. DABWAYO_TTS_URL set        -> remote (your TTS server)
  2. ELEVENLABS_API_KEY set     -> elevenlabs
  3. OPENAI_API_KEY set         -> openai
  4. local pyttsx3 if installed -> local
  5. else raise — optional; add_audio your own narration instead.
"""
from __future__ import annotations

import os
from typing import Optional

from .base import VoiceProvider, TTSError
from .local import Pyttsx3Provider
from .remote import RemoteTTSProvider, OpenAITTSProvider, ElevenLabsProvider

_CONSTRUCTORS = {
    "local": Pyttsx3Provider,
    "remote": RemoteTTSProvider,
    "openai": OpenAITTSProvider,
    "elevenlabs": ElevenLabsProvider,
}
_AUTO_HOSTED = ["elevenlabs", "openai"]


def _make(name: str) -> VoiceProvider:
    n = name.lower()
    if n not in _CONSTRUCTORS:
        raise TTSError(f"unknown TTS provider {name!r}; choose from {sorted(_CONSTRUCTORS)}")
    return _CONSTRUCTORS[n]()


def get_provider(name: Optional[str] = None) -> VoiceProvider:
    choice = (name or os.environ.get("DABWAYO_TTS_PROVIDER", "auto")).lower()
    if choice != "auto":
        return _make(choice)
    if os.environ.get("DABWAYO_TTS_URL"):
        return _make("remote")
    for hosted in _AUTO_HOSTED:
        if _make(hosted).available()[0]:
            return _make(hosted)
    if _make("local").available()[0]:
        return _make("local")
    raise TTSError(
        "no TTS provider available. Configure one — DABWAYO_TTS_URL, "
        "ELEVENLABS_API_KEY, OPENAI_API_KEY, or `pip install pyttsx3` — or skip "
        "TTS and add_audio your own narration file.")


def list_providers() -> dict:
    out = {}
    for nm in _CONSTRUCTORS:
        ok, why = _make(nm).available()
        out[nm] = {"available": ok, "detail": why}
    try:
        active = get_provider().name
    except TTSError:
        active = None
    return {"active": active, "providers": out,
            "optional": "TTS is optional — add_audio your own file needs no provider"}


def synth(text: str, out_path: str, provider: Optional[str] = None,
          voice: Optional[str] = None) -> dict:
    return get_provider(provider).synth(text, out_path, voice=voice)
