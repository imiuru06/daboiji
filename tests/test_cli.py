import json

import pytest

import dabwayo.cli as cli
from dabwayo.client import Job
from dabwayo.config import Config


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DABWAYO_VIDEOGEN_URL", "https://svc.test")
    monkeypatch.setenv("DABWAYO_VIDEOGEN_PROVIDER", "remote")


def test_config_command(capsys):
    assert cli.main(["config"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["base_url"] == "https://svc.test"
    assert out["provider"] == "remote"
    assert out["api_key_set"] is False


def test_missing_url_returns_2(monkeypatch, capsys):
    monkeypatch.delenv("DABWAYO_VIDEOGEN_URL", raising=False)
    assert cli.main(["config"]) == 2
    assert "error:" in capsys.readouterr().err


def test_generate_flow(monkeypatch, tmp_path, capsys):
    dest = tmp_path / "v.mp4"

    def fake_generate(self, prompt, **params):
        assert prompt == "a cat"
        assert params["duration"] == 3.0
        assert params["seed"] == 11
        assert params["fps"] == 24  # from --param
        return Job(job_id="j", status="queued")

    def fake_wait(self, job, **kwargs):
        return Job(job_id="j", status="completed", video_url="https://svc.test/v.mp4")

    def fake_download(self, job, out):
        with open(out, "wb") as fh:
            fh.write(b"data")
        return out

    monkeypatch.setattr(cli.VideoGenClient, "generate", fake_generate)
    monkeypatch.setattr(cli.VideoGenClient, "wait", fake_wait)
    monkeypatch.setattr(cli.VideoGenClient, "download", fake_download)

    rc = cli.main(
        ["generate", "a cat", "-o", str(dest), "--duration", "3", "--seed", "11", "--param", "fps=24"]
    )
    assert rc == 0
    assert dest.read_bytes() == b"data"
    assert str(dest) in capsys.readouterr().out


def test_param_coercion():
    assert cli._coerce("true") is True
    assert cli._coerce("42") == 42
    assert cli._coerce("1.5") == 1.5
    assert cli._coerce("hello") == "hello"


def test_ping_command(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.VideoGenClient, "ping", lambda self: {"path": "/health", "status": 200, "body": "ok"}
    )
    assert cli.main(["ping"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == 200
