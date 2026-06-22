"""Smoke and unit tests for the VideoForge engine.

Run: PYTHONPATH=. python -m pytest tests/ -q   (or: python tests/test_engine.py)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import videoforge as vf
from videoforge.core import easing
from videoforge.core.keyframe import AnimatedProperty
from videoforge.core.types import Color
from videoforge.render.encoder import ffmpeg_exe


def test_color_parse():
    assert Color.parse("#ffffff").to_uint8() == (255, 255, 255, 255)
    assert Color.parse("#f00").to_uint8() == (255, 0, 0, 255)
    assert Color.parse("transparent").a == 0.0
    assert Color.parse((255, 128, 0)).to_uint8() == (255, 128, 0, 255)
    assert Color.parse("navy").to_uint8()[3] == 255


def test_easing_bounds():
    for name, fn in easing.REGISTRY.items():
        assert abs(fn(0.0)) < 1e-6, name
        assert abs(fn(1.0) - 1.0) < 1e-6, name


def test_keyframe_interpolation():
    p = AnimatedProperty.coerce({"keyframes": [
        {"time": 0, "value": 0, "easing": "linear"},
        {"time": 2, "value": 100, "easing": "linear"},
    ]})
    assert p.at(-1) == 0
    assert abs(p.at(1) - 50) < 1e-6
    assert p.at(5) == 100


def test_capabilities_nonempty():
    caps = vf.capabilities()
    for key in ("elements", "effects", "transitions"):
        assert len(caps[key]) > 0, key
    assert "glow" in caps["effects"]
    assert "text" in caps["elements"]


def test_render_frame_shape():
    p = vf.Project(160, 90, fps=10, background="#101820")
    tr = p.track("video")
    tr.add(vf.Project.text("hi", size=24), 0, 1).effect("glow")
    frame = vf.render_frame(p.timeline(), vf.RenderContext(160, 90, 10, time=0.5), 0.5)
    assert frame.shape == (90, 160, 3)
    assert frame.dtype == np.uint8


def test_spec_roundtrip(tmp_path=None):
    tmp = tmp_path or tempfile.mkdtemp()
    p = vf.Project(160, 90, fps=10)
    p.track("video").add(vf.Project.solid("#ff0000"), 0, 1)
    spec_path = os.path.join(str(tmp), "p.json")
    p.save(spec_path)
    loaded = vf.Project.load(spec_path)
    assert loaded.spec["width"] == 160
    assert json.loads(p.to_json())["tracks"][0]["clips"][0]["element"]["type"] == "solid"


def test_new_effects_registered():
    fx = vf.capabilities()["effects"]
    for name in ("fog", "mosaic", "inpaint", "lama_inpaint", "chroma_key", "mask"):
        assert name in fx, name


def test_chroma_key_makes_transparent():
    from videoforge.effects.keying import ChromaKey
    img = np.zeros((4, 4, 4), np.float32)
    img[..., 1] = 1.0  # pure green
    img[..., 3] = 1.0
    out = ChromaKey(key="#00ff00", tolerance=0.1, softness=0.05).apply(
        img, vf.RenderContext(4, 4, 1), 0.0)
    assert out[..., 3].max() < 0.01  # green keyed out


def test_mosaic_region_and_inpaint_run():
    from videoforge.effects.censor import Inpaint, Mosaic
    ctx = vf.RenderContext(64, 64, 1)
    img = np.random.default_rng(0).random((64, 64, 4)).astype(np.float32)
    img[..., 3] = 1.0
    m = Mosaic(block=8, region={"shape": "rect", "rect": [10, 10, 20, 20]}).apply(img, ctx, 0)
    assert m.shape == img.shape
    ip = Inpaint(region={"shape": "rect", "rect": [10, 10, 20, 20]}, radius=3).apply(img, ctx, 0)
    assert ip.shape == img.shape


def test_camera_parallax_shifts_position():
    from videoforge.core.camera import Camera, apply_camera
    cam = Camera.from_spec({"pan": [100, 0], "zoom": 1.0})
    s = cam.sample(0.0, 1000, 1000)
    base = {"position": (500, 500), "scale": (1, 1), "rotation": 0, "opacity": 1,
            "anchor": vf.Anchor.CENTER, "explicit_position": True}
    near = apply_camera(base, s, depth=1.0)
    far = apply_camera(base, s, depth=0.0)
    assert near["position"][0] < far["position"][0]  # foreground moves more


def test_full_render_produces_valid_mp4():
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "t.mp4")
    p = vf.Project(160, 90, fps=10, background="#0b0e16")
    bg = p.track("video", "bg")
    bg.add(vf.Project.gradient([[0, "#234"], [1, "#012"]]), 0, 1)
    tx = p.track("video", "tx")
    (tx.add(vf.Project.text("ok", size=30, color="#fff"), 0, 1)
       .transition_in("zoom", 0.3).effect("glow"))
    p.master_effect("vignette", amount=0.3)
    res = p.render(out, preset="ultrafast")
    assert os.path.getsize(out) > 1000
    # validate container with ffprobe (via ffmpeg -i)
    probe = subprocess.run([ffmpeg_exe(), "-i", out], capture_output=True, text=True)
    assert "Video: h264" in probe.stderr
    assert res.frames == 10


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
