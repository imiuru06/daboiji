"""Off-box ASR backends: a self-hosted HTTP Whisper server (like the LaMa /
video-gen Colab pattern) and hosted OpenAI Whisper."""
from __future__ import annotations

import os
from typing import Optional

from .base import ASRProvider, Transcript, Word, ASRError

ENV_URL = "DABWAYO_ASR_URL"
ENV_KEY = "DABWAYO_ASR_KEY"


class RemoteASRProvider(ASRProvider):
    """POST the audio to your own Whisper HTTP server.

    Contract (implement it on the box that has the GPU/model):
        POST /transcribe  (multipart: file=<audio>, language=<opt>)
          -> {"text": "...", "language": "en",
              "words": [{"word": "...", "start": 0.0, "end": 0.4}, ...]}
    """
    name = "remote"

    def available(self) -> tuple[bool, str]:
        return (bool(os.environ.get(ENV_URL)),
                "configured" if os.environ.get(ENV_URL)
                else f"set {ENV_URL} to a Whisper HTTP server")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Transcript:
        try:
            import requests
        except ImportError as e:  # pragma: no cover
            raise ASRError("the 'requests' package is required") from e
        url = os.environ.get(ENV_URL, "").rstrip("/")
        if not url:
            raise ASRError(f"set {ENV_URL} to your Whisper HTTP server")
        if not os.path.exists(audio_path):
            raise ASRError(f"audio not found: {audio_path}")
        headers = {}
        key = os.environ.get(ENV_KEY)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            with open(audio_path, "rb") as f:
                r = requests.post(f"{url}/transcribe", files={"file": f},
                                  data={"language": language or ""},
                                  headers=headers, timeout=600)
            r.raise_for_status()
            j = r.json()
        except Exception as e:  # noqa: BLE001
            raise ASRError(f"remote ASR request failed: {e}") from e
        words = [Word(str(w.get("word", "")), float(w["start"]), float(w["end"]))
                 for w in j.get("words", []) if "start" in w and "end" in w]
        return Transcript(j.get("text", ""), words, j.get("language", ""), "remote")


class OpenAIASRProvider(ASRProvider):
    """Hosted OpenAI Whisper with word timestamps. Needs OPENAI_API_KEY."""
    name = "openai"

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("OPENAI_API_KEY"):
            return (False, "set OPENAI_API_KEY")
        try:
            import openai  # noqa: F401
            return (True, "openai configured")
        except ImportError:
            return (False, "pip install openai")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Transcript:
        if not os.path.exists(audio_path):
            raise ASRError(f"audio not found: {audio_path}")
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise ASRError("pip install openai") from e
        client = OpenAI()
        try:
            with open(audio_path, "rb") as f:
                r = client.audio.transcriptions.create(
                    model=os.environ.get("DABWAYO_ASR_MODEL", "whisper-1"),
                    file=f, response_format="verbose_json",
                    timestamp_granularities=["word"], language=language or None)
        except Exception as e:  # noqa: BLE001
            raise ASRError(f"OpenAI transcription failed: {e}") from e
        words = [Word(w.word, float(w.start), float(w.end)) for w in (getattr(r, "words", None) or [])]
        return Transcript(getattr(r, "text", ""), words,
                          getattr(r, "language", "") or (language or ""), "openai")
