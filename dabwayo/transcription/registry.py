"""ASR provider selection — pluggable and optional.

Default (``DABWAYO_ASR_PROVIDER`` unset/``auto``):
  1. if ``DABWAYO_ASR_URL`` set        -> remote (your Whisper HTTP server)
  2. else a hosted provider whose key is set (openai)
  3. else ``local`` Whisper if installed (faster-whisper / openai-whisper)
  4. else raise — ASR is optional; pass words to add_word_captions instead.

Override by name via the env var or ``provider=``.
"""
from __future__ import annotations

import os
from typing import Optional

from .base import ASRProvider, Transcript, ASRError
from .local import LocalWhisperProvider
from .remote import RemoteASRProvider, OpenAIASRProvider

_CONSTRUCTORS = {
    "local": LocalWhisperProvider,
    "remote": RemoteASRProvider,
    "openai": OpenAIASRProvider,
}
_AUTO_HOSTED = ["openai"]


def _make(name: str) -> ASRProvider:
    n = name.lower()
    if n not in _CONSTRUCTORS:
        raise ASRError(f"unknown ASR provider {name!r}; choose from {sorted(_CONSTRUCTORS)}")
    return _CONSTRUCTORS[n]()


def get_provider(name: Optional[str] = None) -> ASRProvider:
    choice = (name or os.environ.get("DABWAYO_ASR_PROVIDER", "auto")).lower()
    if choice != "auto":
        return _make(choice)
    if os.environ.get("DABWAYO_ASR_URL"):
        return _make("remote")
    for hosted in _AUTO_HOSTED:
        if _make(hosted).available()[0]:
            return _make(hosted)
    if _make("local").available()[0]:
        return _make("local")
    raise ASRError(
        "no ASR provider available. Configure one — DABWAYO_ASR_URL (your Whisper "
        "server), OPENAI_API_KEY, or `pip install faster-whisper` — or skip ASR and "
        "pass a word list to add_word_captions.")


def list_providers() -> dict:
    out = {}
    for nm in _CONSTRUCTORS:
        ok, why = _make(nm).available()
        out[nm] = {"available": ok, "detail": why}
    try:
        active = get_provider().name
    except ASRError:
        active = None
    return {"active": active, "providers": out,
            "optional": "ASR is optional — add_word_captions(words=[...]) needs no provider"}


def transcribe(audio_path: str, provider: Optional[str] = None,
               language: Optional[str] = None) -> Transcript:
    return get_provider(provider).transcribe(audio_path, language=language)
