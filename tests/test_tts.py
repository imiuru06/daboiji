"""Tests for the pluggable TTS provider registry (no synthesis required)."""
import pytest
from dabwayo.tts import list_providers, get_provider
from dabwayo.tts.base import TTSError


def _clear(monkeypatch):
    for k in ("DABWAYO_TTS_URL", "DABWAYO_TTS_PROVIDER",
              "ELEVENLABS_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_list_providers_reports_all(monkeypatch):
    _clear(monkeypatch)
    r = list_providers()
    assert set(r["providers"]) == {"local", "remote", "openai", "elevenlabs"}
    assert "optional" in r


def test_auto_raises_when_nothing_available(monkeypatch):
    _clear(monkeypatch)
    import dabwayo.tts.local as L
    monkeypatch.setattr(L.Pyttsx3Provider, "available", lambda self: (False, "no"))
    with pytest.raises(TTSError):
        get_provider()


def test_env_selects_remote_then_elevenlabs(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("DABWAYO_TTS_URL", "https://example.com")
    assert get_provider().name == "remote"
    monkeypatch.delenv("DABWAYO_TTS_URL")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "x")
    assert get_provider().name == "elevenlabs"


def test_unknown_provider_rejected():
    with pytest.raises(TTSError):
        get_provider("bogus")
