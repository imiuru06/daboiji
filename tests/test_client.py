import pytest

from dabwayo.client import Job, VideoGenClient, VideoGenError, _job_from_payload
from dabwayo.config import Config


def make_client():
    return VideoGenClient(Config(base_url="https://svc.test", provider="remote"))


def test_job_from_payload_variants():
    job = _job_from_payload({"id": "abc", "state": "queued", "percent": "0.25"})
    assert job.job_id == "abc"
    assert job.status == "queued"
    assert job.progress == 0.25
    assert not job.done and not job.failed


def test_job_done_via_status_and_url():
    assert Job(job_id="1", status="completed").done
    assert Job(job_id="1", video_url="https://x/v.mp4").done
    assert Job(job_id="1", status="failed").failed


def test_job_from_payload_rejects_non_dict():
    with pytest.raises(VideoGenError):
        _job_from_payload([1, 2, 3])


def test_generate_remembers_working_path(monkeypatch):
    client = make_client()
    calls = []

    def fake_request(method, url, *, body=None, raw=False, timeout=None):
        calls.append(url)
        # First candidate path (/generate) fails, second (/api/generate) wins.
        if url == "https://svc.test/generate":
            raise VideoGenError("404")
        return {"job_id": "job-1", "status": "queued"}

    monkeypatch.setattr(client, "_request", fake_request)

    job = client.generate("a cat", duration=4)
    assert job.job_id == "job-1"
    assert client.generate_path == "/api/generate"
    assert calls[0].endswith("/generate")
    assert calls[1].endswith("/api/generate")


def test_generate_includes_prompt_and_provider(monkeypatch):
    client = make_client()
    seen = {}

    def fake_request(method, url, *, body=None, raw=False, timeout=None):
        seen.update(body or {})
        return {"job_id": "x"}

    monkeypatch.setattr(client, "_request", fake_request)
    client.generate("hello", seed=7)
    assert seen["prompt"] == "hello"
    assert seen["seed"] == 7
    assert seen["provider"] == "remote"


def test_wait_polls_until_done(monkeypatch):
    client = make_client()
    states = iter(
        [
            Job(job_id="j", status="running", progress=0.5),
            Job(job_id="j", status="completed", video_url="https://svc.test/v.mp4"),
        ]
    )
    monkeypatch.setattr(client, "get_status", lambda job_id: next(states))

    seen = []
    final = client.wait(
        "j",
        poll_interval=0,
        on_progress=seen.append,
        _sleep=lambda s: None,
    )
    assert final.status == "completed"
    assert len(seen) == 2


def test_wait_raises_on_failure(monkeypatch):
    client = make_client()
    monkeypatch.setattr(client, "get_status", lambda job_id: Job(job_id="j", status="error"))
    with pytest.raises(VideoGenError):
        client.wait("j", poll_interval=0, _sleep=lambda s: None)


def test_wait_times_out(monkeypatch):
    client = make_client()
    monkeypatch.setattr(client, "get_status", lambda job_id: Job(job_id="j", status="running"))
    times = iter([0.0, 0.0, 100.0])
    with pytest.raises(VideoGenError):
        client.wait(
            "j",
            poll_interval=0,
            max_wait=10,
            _sleep=lambda s: None,
            _now=lambda: next(times),
        )


def test_download_writes_file(monkeypatch, tmp_path):
    client = make_client()
    monkeypatch.setattr(client, "_request", lambda *a, **k: b"VIDEOBYTES")
    dest = tmp_path / "out.mp4"
    client.download(Job(job_id="j", video_url="https://svc.test/v.mp4"), str(dest))
    assert dest.read_bytes() == b"VIDEOBYTES"


def test_download_resolves_relative_url(monkeypatch, tmp_path):
    client = make_client()
    captured = {}

    def fake_request(method, url, *, body=None, raw=False, timeout=None):
        captured["url"] = url
        return b"x"

    monkeypatch.setattr(client, "_request", fake_request)
    client.download("/files/v.mp4", str(tmp_path / "o.mp4"))
    assert captured["url"] == "https://svc.test/files/v.mp4"


def test_download_without_url_raises():
    client = make_client()
    with pytest.raises(VideoGenError):
        client.download(Job(job_id="j"), "out.mp4")
