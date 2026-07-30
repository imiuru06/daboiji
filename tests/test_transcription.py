"""Tests for the pluggable ASR provider registry (no models required)."""
import pytest
from dabwayo.transcription import list_providers, get_provider
from dabwayo.transcription.base import ASRError, Transcript, Word


def test_list_providers_reports_all(monkeypatch):
    for k in ("DABWAYO_ASR_URL", "DABWAYO_ASR_PROVIDER", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = list_providers()
    assert set(r["providers"]) == {"local", "remote", "openai"}
    assert "optional" in r


def test_auto_raises_when_nothing_available(monkeypatch):
    for k in ("DABWAYO_ASR_URL", "DABWAYO_ASR_PROVIDER", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    # force local unavailable regardless of host env
    import dabwayo.transcription.local as L
    monkeypatch.setattr(L.LocalWhisperProvider, "_backend", lambda self: None)
    with pytest.raises(ASRError):
        get_provider()


def test_env_url_selects_remote(monkeypatch):
    monkeypatch.setenv("DABWAYO_ASR_URL", "https://example.com")
    monkeypatch.delenv("DABWAYO_ASR_PROVIDER", raising=False)
    assert get_provider().name == "remote"


def test_explicit_and_unknown_provider(monkeypatch):
    assert get_provider("remote").name == "remote"
    with pytest.raises(ASRError):
        get_provider("bogus")


def test_transcript_serialisation():
    t = Transcript("hi there", [Word("hi", 0.0, 0.4), Word("there", 0.4, 0.9)],
                   language="en", provider="local")
    d = t.as_dict()
    assert d["text"] == "hi there" and d["provider"] == "local"
    assert d["words"][0] == {"word": "hi", "start": 0.0, "end": 0.4}
