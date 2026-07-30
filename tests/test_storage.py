"""Tests for the pluggable storage abstraction (local; s3 availability only)."""
import os
import pytest
from dabwayo.storage import list_backends, get_backend, StorageError
from dabwayo.storage.registry import _make


def test_backends_list_and_local_default(monkeypatch):
    monkeypatch.delenv("DABWAYO_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("DABWAYO_STORAGE_S3_BUCKET", raising=False)
    r = list_backends()
    assert r["backends"]["local"]["available"] is True
    assert r["active"] == "local"


def test_local_put_localize_url(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x" * 64)
    local = _make("local")
    uri = local.put(str(f))
    assert uri == os.path.abspath(str(f))
    assert local.localize(uri) == uri
    assert local.url(uri) == "/files/a.png"
    assert local.exists(uri) is True


def test_s3_unavailable_without_config(monkeypatch):
    monkeypatch.delenv("DABWAYO_STORAGE_S3_BUCKET", raising=False)
    ok, why = _make("s3").available()
    assert ok is False and "BUCKET" in why


def test_unknown_backend_rejected():
    with pytest.raises(StorageError):
        get_backend("bogus")
