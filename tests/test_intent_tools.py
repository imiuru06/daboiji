"""Tests for the intent-level tools: camera_move, set_focus, align_clips,
duck_audio — plus the mixer ducking envelope they compile to."""
import os

from dabwayo.mcp_tools import (
    create_project, add_text, add_background, add_media, add_voiceover,  # noqa
)
from dabwayo.mcp_tools import camera as C
from dabwayo.mcp_tools import layout as L
from dabwayo.mcp_tools import audio as A
from dabwayo.mcp_tools.app import _proj, _commit
from dabwayo.audio.mixer import _duck_expr
from dabwayo.core.camera import Camera


def _new(**kw):
    return create_project(width=1920, height=1080, fps=30.0, **kw)["project_id"]


# --------------------------------------------------------------------------
# camera_move
# --------------------------------------------------------------------------
def test_push_in_compiles_to_zoom_keyframes():
    pid = _new()
    add_background(pid, duration=6.0)
    r = C.camera_move(pid, "push_in", amount=0.2, duration=4.0)
    cam = _proj(pid)["camera"]
    assert "zoom" in cam and "keyframes" in cam["zoom"]
    kfs = cam["zoom"]["keyframes"]
    assert kfs[0]["value"] == 1.0 and abs(kfs[-1]["value"] - 1.2) < 1e-6
    # sample the real engine Camera to prove it animates
    c = Camera.from_spec(cam)
    assert c.zoom.at(0.0) == 1.0
    assert abs(c.zoom.at(4.0) - 1.2) < 1e-6
    assert 1.0 < c.zoom.at(2.0) < 1.2


def test_moves_compose():
    pid = _new()
    add_background(pid, duration=5.0)
    C.camera_move(pid, "push_in")
    C.camera_move(pid, "pan_right", amount=100.0, duration=5.0)
    cam = _proj(pid)["camera"]
    assert "zoom" in cam and "pan" in cam            # both channels present
    c = Camera.from_spec(cam)
    assert c.pan.at(5.0)[0] > 0


def test_ken_burns_sets_zoom_and_pan():
    pid = _new()
    add_background(pid, duration=5.0)
    C.camera_move(pid, "ken_burns", direction="down_right")
    cam = _proj(pid)["camera"]
    assert "zoom" in cam and "pan" in cam
    drift = cam["pan"]["keyframes"][-1]["value"]
    assert drift[0] > 0 and drift[1] > 0             # down-right drift


def test_hold_clears_camera():
    pid = _new()
    add_background(pid, duration=5.0)
    C.camera_move(pid, "push_in")
    C.camera_move(pid, "hold")
    assert _proj(pid)["camera"] == {}


def test_bad_preset_raises():
    pid = _new()
    add_background(pid, duration=5.0)
    try:
        C.camera_move(pid, "barrel_roll")
        assert False
    except ValueError as e:
        assert "barrel_roll" in str(e)


# --------------------------------------------------------------------------
# set_focus (depth of field)
# --------------------------------------------------------------------------
def test_dof_blurs_by_depth_distance():
    pid = _new()
    fg = add_media(pid, "a.png", duration=5.0, transform={"position": [960, 540]})
    bg = add_background(pid, duration=5.0)
    # push the background far in depth
    sp = _proj(pid)
    sp["tracks"][0]["clips"][0]["depth"] = 1.0
    sp["tracks"][0]["clips"][1]["depth"] = 0.0
    _commit(pid, sp)
    C.set_focus(pid, focus_depth=1.0, aperture=1.0, max_blur=14.0)
    sp = _proj(pid)
    fg_clip = sp["tracks"][0]["clips"][0]
    bg_clip = sp["tracks"][0]["clips"][1]
    # foreground (at focus plane) sharp -> no dof blur added
    assert not any(f.get("_dof") for f in fg_clip.get("effects", []))
    # background (far) blurred
    bg_blur = [f for f in bg_clip.get("effects", []) if f.get("_dof")]
    assert bg_blur and bg_blur[0]["radius"] > 0


def test_dof_is_idempotent():
    pid = _new()
    add_background(pid, duration=5.0)
    sp = _proj(pid)
    sp["tracks"][0]["clips"][0]["depth"] = 0.0
    _commit(pid, sp)
    C.set_focus(pid, focus_depth=1.0, aperture=1.0)
    C.set_focus(pid, focus_depth=1.0, aperture=1.0)
    clip = _proj(pid)["tracks"][0]["clips"][0]
    assert len([f for f in clip["effects"] if f.get("_dof")]) == 1   # not doubled


def test_rack_focus_keyframes_blur():
    pid = _new()
    add_background(pid, duration=5.0)
    sp = _proj(pid)
    sp["tracks"][0]["clips"][0]["depth"] = 0.0
    _commit(pid, sp)
    C.set_focus(pid, focus_depth=1.0, pull_to=0.0, duration=2.0, aperture=1.0)
    clip = _proj(pid)["tracks"][0]["clips"][0]
    dof = [f for f in clip["effects"] if f.get("_dof")][0]
    assert "keyframes" in dof["radius"]              # animated (rack) focus
    kfs = dof["radius"]["keyframes"]
    assert kfs[0]["value"] > kfs[-1]["value"]        # far->focus: blur -> sharp


# --------------------------------------------------------------------------
# align_clips
# --------------------------------------------------------------------------
def test_center_places_all_at_canvas_center():
    pid = _new()
    ids = [add_text(pid, f"t{i}", duration=5.0)["clip_id"] for i in range(3)]
    r = L.align_clips(pid, mode="center", clip_ids=ids)
    for p in r["positions"]:
        assert p["position"] == [960.0, 540.0]


def test_distribute_h_spreads_evenly():
    pid = _new()
    ids = [add_text(pid, f"t{i}", duration=5.0)["clip_id"] for i in range(3)]
    r = L.align_clips(pid, mode="distribute_h", clip_ids=ids, padding=60)
    xs = [p["position"][0] for p in r["positions"]]
    assert xs[0] == 60 and abs(xs[-1] - (1920 - 60)) < 1e-6
    assert xs[0] < xs[1] < xs[2]                     # monotonic spread


def test_grid_rows_and_cols():
    pid = _new()
    ids = [add_text(pid, f"t{i}", duration=5.0)["clip_id"] for i in range(4)]
    r = L.align_clips(pid, mode="grid", clip_ids=ids, columns=2)
    pts = [tuple(p["position"]) for p in r["positions"]]
    assert len(set(pts)) == 4                         # four distinct cells
    # row 0 above row 1
    assert pts[0][1] < pts[2][1]


def test_safe_area_bounds():
    pid = _new()
    ids = [add_text(pid, "x", duration=5.0)["clip_id"]]
    r = L.align_clips(pid, mode="top", clip_ids=ids, bounds="safe", padding=0)
    assert abs(r["positions"][0]["position"][1] - 0.05 * 1080) < 1e-6


# --------------------------------------------------------------------------
# duck_audio + mixer envelope
# --------------------------------------------------------------------------
def test_duck_computes_windows_from_vo_spans():
    pid = _new()
    sp = _proj(pid)
    # place a long music bed + two explicit-duration VO clips
    sp["tracks"].append({"kind": "audio", "name": "audio", "clips": [
        {"id": "music", "path": "m.mp3", "start": 0.0, "duration": 30.0,
         "gain_db": 0.0, "fade_in": 0.0, "fade_out": 0.0, "in_point": 0.0},
        {"id": "vo1", "path": "v1.wav", "start": 2.0, "duration": 3.0,
         "gain_db": 0.0, "in_point": 0.0},
        {"id": "vo2", "path": "v2.wav", "start": 10.0, "duration": 4.0,
         "gain_db": 0.0, "in_point": 0.0},
    ]})
    _commit(pid, sp)
    r = A.duck_audio(pid, music_clip_id="music", under=["vo1", "vo2"],
                     amount_db=-14.0)
    assert r["music_clip_id"] == "music"
    assert [2.0, 5.0] in r["windows"] and [10.0, 14.0] in r["windows"]
    music = _proj(pid)["tracks"][-1]["clips"][0]
    assert music["duck"]["amount_db"] == -14.0


def test_duck_default_picks_longest_as_music():
    pid = _new()
    sp = _proj(pid)
    sp["tracks"].append({"kind": "audio", "name": "audio", "clips": [
        {"id": "vo", "path": "v.wav", "start": 1.0, "duration": 2.0},
        {"id": "bed", "path": "m.mp3", "start": 0.0, "duration": 20.0},
    ]})
    _commit(pid, sp)
    r = A.duck_audio(pid)
    assert r["music_clip_id"] == "bed"
    assert [1.0, 3.0] in r["windows"]


def test_clear_ducking():
    pid = _new()
    sp = _proj(pid)
    sp["tracks"].append({"kind": "audio", "name": "audio", "clips": [
        {"id": "m", "path": "m.mp3", "start": 0.0, "duration": 20.0,
         "duck": {"windows": [[1, 2]], "amount_db": -12}},
    ]})
    _commit(pid, sp)
    assert A.clear_ducking(pid)["cleared"] == 1
    assert "duck" not in _proj(pid)["tracks"][-1]["clips"][0]


def test_duck_expr_shape():
    duck = {"windows": [[2.0, 5.0], [10.0, 14.0]], "amount_db": -12.0,
            "attack": 0.25, "release": 0.6}
    expr = _duck_expr(1.0, 0.0, duck)
    assert "min(" in expr                             # two windows -> min()
    assert "if(lt(t," in expr                         # piecewise ramps
    # single window, no min()
    expr1 = _duck_expr(0.5, 0.0, {"windows": [[2.0, 5.0]], "amount_db": -6.0})
    assert "min(" not in expr1 and expr1.startswith("0.5")


def test_duck_expr_is_valid_ffmpeg_volume_expression():
    """Prove the compiled envelope is a filter ffmpeg accepts + actually
    dips the level. Renders a tone, ducks a window, checks mid-window is
    quieter than outside."""
    import numpy as np
    import subprocess
    import tempfile
    from dabwayo.render.encoder import ffmpeg_exe
    ff = ffmpeg_exe()
    d = tempfile.mkdtemp()
    tone = os.path.join(d, "tone.wav")
    # 6s 440Hz tone
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    tone], capture_output=True)
    duck = {"windows": [[2.0, 4.0]], "amount_db": -20.0,
            "attack": 0.1, "release": 0.1}
    expr = _duck_expr(1.0, 0.0, duck)
    out = os.path.join(d, "ducked.wav")
    p = subprocess.run([ff, "-y", "-i", tone, "-af",
                        f"volume=eval=frame:volume='{expr}'", out],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-800:]
    # read back with ffmpeg -> raw and compare RMS in/out of the window
    raw = os.path.join(d, "o.f32le")
    subprocess.run([ff, "-y", "-i", out, "-f", "f32le", "-ac", "1",
                    "-ar", "48000", raw], capture_output=True)
    a = np.fromfile(raw, dtype="<f4")
    sr = 48000
    outside = a[int(0.5 * sr):int(1.5 * sr)]
    inside = a[int(2.8 * sr):int(3.2 * sr)]
    rms = lambda x: float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    assert rms(inside) < 0.4 * rms(outside)          # meaningfully ducked
