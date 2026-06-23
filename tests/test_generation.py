"""Tests for the generative-video provider layer.

Only the local (procedural) provider runs here — it needs no GPU/network/key.
Remote/hosted adapters are exercised for selection + availability messaging.

Run: PYTHONPATH=. python -m pytest tests/test_generation.py -q
      (or: python tests/test_generation.py)
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import videoforge as vf
from videoforge.generation import GenRequest, get_provider, list_providers
from videoforge.generation.registry import _CONSTRUCTORS
from videoforge.render.encoder import ffmpeg_exe


def _is_h264(path: str) -> bool:
    probe = subprocess.run([ffmpeg_exe(), "-i", path], capture_output=True, text=True)
    return "Video: h264" in probe.stderr


def test_request_frame_math():
    r = GenRequest.from_kwargs("x", duration=2.0, fps=24.0)
    assert r.num_frames == 48
    assert abs(r.duration - 2.0) < 1e-6


def test_registry_lists_all_providers():
    rep = list_providers()
    assert set(rep["providers"]) == set(_CONSTRUCTORS)
    # local is always available
    assert rep["providers"]["local"]["available"] is True


def test_auto_selection_rules(monkeypatch=None):
    # no env -> local
    for k in ("VIDEOFORGE_VIDEOGEN_PROVIDER", "VIDEOFORGE_VIDEOGEN_URL",
              "REPLICATE_API_TOKEN", "FAL_KEY", "HF_TOKEN"):
        os.environ.pop(k, None)
    assert get_provider().name == "local"
    # url set -> remote
    os.environ["VIDEOFORGE_VIDEOGEN_URL"] = "https://example.com"
    assert get_provider().name == "remote"
    os.environ.pop("VIDEOFORGE_VIDEOGEN_URL")
    # explicit override wins
    assert get_provider("replicate").name == "replicate"


def test_remote_requires_url():
    os.environ.pop("VIDEOFORGE_VIDEOGEN_URL", None)
    ok, why = get_provider("remote").available()
    assert ok is False and "VIDEOFORGE_VIDEOGEN_URL" in why


def test_local_t2v_renders_h264():
    out = os.path.join(tempfile.mkdtemp(), "t2v.mp4")
    res = vf.generate_video("calm ocean at night", out, duration=1.0, fps=24,
                            width=256, height=144, seed=1, provider="local")
    assert res.provider == "local"
    assert res.frames == 24
    assert res.width == 256 and res.height == 144
    assert os.path.getsize(out) > 1000
    assert _is_h264(out)


def test_local_i2v_animates_image():
    # make a tiny source image
    import numpy as np
    from PIL import Image
    src = os.path.join(tempfile.mkdtemp(), "src.png")
    Image.fromarray((np.random.rand(120, 200, 3) * 255).astype("uint8")).save(src)
    out = os.path.join(os.path.dirname(src), "i2v.mp4")
    res = vf.generate_video("living photo", out, mode="i2v", image=src,
                            duration=1.0, fps=24, width=256, height=144,
                            provider="local")
    assert res.frames == 24
    assert _is_h264(out)


def test_generated_clip_composites_into_timeline():
    out_dir = tempfile.mkdtemp()
    gen = vf.generate_video("neon city", os.path.join(out_dir, "g.mp4"),
                            duration=1.0, fps=24, width=256, height=144,
                            provider="local")
    p = vf.Project(256, 144, fps=24, background="#000")
    t = p.track("video")
    t.add(vf.Project.video(gen.path, fit="cover"), start=0, duration=1.0)
    t.add(vf.Project.text("HI", size=40), start=0, duration=1.0)
    final = os.path.join(out_dir, "final.mp4")
    res = p.render(final, preset="ultrafast")
    assert res.frames == 24
    assert _is_h264(final)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
