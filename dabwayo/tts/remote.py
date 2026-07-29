"""Off-box TTS: a self-hosted HTTP server, OpenAI TTS, or ElevenLabs."""
from __future__ import annotations

import os
from typing import Optional

from .base import VoiceProvider, TTSError

ENV_URL = "DABWAYO_TTS_URL"
ENV_KEY = "DABWAYO_TTS_KEY"


def _write_stream(resp, out_path):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)


class RemoteTTSProvider(VoiceProvider):
    """POST text to your own TTS server.

    Contract:  POST /synthesize  (json: {text, voice}) -> audio bytes (mp3/wav).
    """
    name = "remote"

    def available(self) -> tuple[bool, str]:
        return (bool(os.environ.get(ENV_URL)),
                "configured" if os.environ.get(ENV_URL) else f"set {ENV_URL}")

    def synth(self, text: str, out_path: str, voice: Optional[str] = None) -> dict:
        try:
            import requests
        except ImportError as e:  # pragma: no cover
            raise TTSError("the 'requests' package is required") from e
        url = os.environ.get(ENV_URL, "").rstrip("/")
        if not url:
            raise TTSError(f"set {ENV_URL} to your TTS server")
        headers = {}
        key = os.environ.get(ENV_KEY)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            r = requests.post(f"{url}/synthesize",
                              json={"text": text, "voice": voice or ""},
                              headers=headers, stream=True, timeout=300)
            r.raise_for_status()
            _write_stream(r, out_path)
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"remote TTS failed: {e}") from e
        return {"path": out_path, "provider": "remote", "voice": voice or "default",
                "format": os.path.splitext(out_path)[1].lstrip(".") or "mp3"}


class OpenAITTSProvider(VoiceProvider):
    name = "openai"

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("OPENAI_API_KEY"):
            return (False, "set OPENAI_API_KEY")
        try:
            import openai  # noqa: F401
            return (True, "openai configured")
        except ImportError:
            return (False, "pip install openai")

    def synth(self, text: str, out_path: str, voice: Optional[str] = None) -> dict:
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise TTSError("pip install openai") from e
        client = OpenAI()
        try:
            with client.audio.speech.with_streaming_response.create(
                    model=os.environ.get("DABWAYO_TTS_MODEL", "tts-1"),
                    voice=voice or "alloy", input=text) as resp:
                resp.stream_to_file(out_path)
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"OpenAI TTS failed: {e}") from e
        return {"path": out_path, "provider": "openai", "voice": voice or "alloy",
                "format": os.path.splitext(out_path)[1].lstrip(".") or "mp3"}


class ElevenLabsProvider(VoiceProvider):
    name = "elevenlabs"

    def available(self) -> tuple[bool, str]:
        return (bool(os.environ.get("ELEVENLABS_API_KEY")),
                "configured" if os.environ.get("ELEVENLABS_API_KEY") else "set ELEVENLABS_API_KEY")

    def synth(self, text: str, out_path: str, voice: Optional[str] = None) -> dict:
        try:
            import requests
        except ImportError as e:  # pragma: no cover
            raise TTSError("the 'requests' package is required") from e
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise TTSError("set ELEVENLABS_API_KEY")
        vid = voice or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        try:
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                headers={"xi-api-key": key, "accept": "audio/mpeg"},
                json={"text": text, "model_id": os.environ.get("DABWAYO_TTS_MODEL", "eleven_multilingual_v2")},
                stream=True, timeout=300)
            r.raise_for_status()
            _write_stream(r, out_path)
        except Exception as e:  # noqa: BLE001
            raise TTSError(f"ElevenLabs TTS failed: {e}") from e
        return {"path": out_path, "provider": "elevenlabs", "voice": vid, "format": "mp3"}
