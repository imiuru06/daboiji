import sys
import types

import pytest

from dabwayo import dewatermark as dw


def _fake_requests(monkeypatch, *, status=200, content=b"MP4", ctype="video/mp4",
                   capture=None):
    mod = types.SimpleNamespace()

    class Resp:
        def __init__(self):
            self.status_code = status
            self.content = content
            self.text = content.decode("latin1")
            self.headers = {"Content-Type": ctype}

        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True, "model": "lama"}

    def post(url, data=None, files=None, headers=None, timeout=None):
        if capture is not None:
            capture["url"] = url
            capture["data"] = data
            capture["files"] = list(files or {})
        return Resp()

    def get(url, headers=None, timeout=None):
        return Resp()

    mod.post = post
    mod.get = get
    monkeypatch.setitem(sys.modules, "requests", mod)


def test_normalize_single_and_list():
    assert dw._normalize_regions([1, 2, 3, 4]) == [[1, 2, 3, 4]]
    assert dw._normalize_regions([[1, 2, 3, 4], [5, 6, 7, 8]]) == [[1, 2, 3, 4], [5, 6, 7, 8]]


def test_normalize_rejects_bad_region():
    with pytest.raises(dw.DewatermarkError):
        dw._normalize_regions([[1, 2, 3]])


def test_base_url_requires_env(monkeypatch):
    monkeypatch.delenv(dw.ENV_URL, raising=False)
    with pytest.raises(dw.DewatermarkError):
        dw._base_url(None)
    assert dw._base_url("https://x.test/") == "https://x.test"


def test_remove_watermark_uploads_and_saves(monkeypatch, tmp_path):
    cap = {}
    _fake_requests(monkeypatch, content=b"CLEANMP4", capture=cap)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"orig")
    out = tmp_path / "out.mp4"
    res = dw.remove_watermark(str(src), str(out), [10, 20, 30, 40],
                              base_url="https://lama.test")
    assert res == str(out)
    assert out.read_bytes() == b"CLEANMP4"
    assert cap["url"] == "https://lama.test/dewatermark"
    assert cap["data"]["regions"] == "[[10, 20, 30, 40]]"
    assert "file" in cap["files"]


def test_remove_watermark_errors_on_non_video(monkeypatch, tmp_path):
    _fake_requests(monkeypatch, ctype="application/json", content=b'{"detail":"boom"}')
    src = tmp_path / "in.mp4"
    src.write_bytes(b"orig")
    with pytest.raises(dw.DewatermarkError):
        dw.remove_watermark(str(src), str(tmp_path / "o.mp4"), [1, 2, 3, 4],
                            base_url="https://lama.test")


def test_remove_watermark_missing_input(monkeypatch, tmp_path):
    _fake_requests(monkeypatch)
    with pytest.raises(dw.DewatermarkError):
        dw.remove_watermark(str(tmp_path / "nope.mp4"), str(tmp_path / "o.mp4"),
                            [1, 2, 3, 4], base_url="https://lama.test")
