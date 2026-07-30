"""Tests for animate_clip — per-clip motion presets compiled to transform
keyframes, verified against the real engine Transform sampler."""
from dabwayo.mcp_tools import create_project, add_text, add_media  # noqa
from dabwayo.mcp_tools import motion as M
from dabwayo.mcp_tools.app import _proj
from dabwayo.core.transform import Transform


def _new():
    return create_project(width=1000, height=1000, fps=30.0)["project_id"]


def _clip0(pid):
    return _proj(pid)["tracks"][0]["clips"][0]


def _transform(clip):
    return Transform.from_spec(clip.get("transform", {}))


def test_float_oscillates_vertically_around_base():
    pid = _new()
    cid = add_text(pid, "hi", duration=4.0,
                   position=[500, 400])["clip_id"]
    M.animate_clip(pid, "float", clip_id=cid, amount=20, cycles=1)
    tf = _transform(_clip0(pid))
    p0 = tf.sample(0.0)["position"]
    assert abs(p0[0] - 500) < 1e-6 and abs(p0[1] - 400) < 1e-6   # starts at base
    ys = [tf.sample(t)["position"][1] for t in [0.0, 1.0, 2.0, 3.0]]
    assert max(ys) - min(ys) > 10                                # actually moves
    xs = [tf.sample(t)["position"][0] for t in [0.0, 1.0, 2.0]]
    assert max(xs) - min(xs) < 1e-6                              # x locked


def test_pulse_oscillates_scale():
    pid = _new()
    cid = add_text(pid, "hi", duration=3.0)["clip_id"]
    M.animate_clip(pid, "pulse", clip_id=cid, amount=0.1, cycles=2)
    tf = _transform(_clip0(pid))
    scales = [tf.sample(t)["scale"][0] for t in
              [i * 0.1 for i in range(30)]]
    assert max(scales) > 1.05 and min(scales) < 0.96            # throbs ±


def test_spin_rotates_full_turns():
    pid = _new()
    cid = add_text(pid, "hi", duration=2.0)["clip_id"]
    M.animate_clip(pid, "spin", clip_id=cid, loops=2)
    tf = _transform(_clip0(pid))
    assert abs(tf.sample(0.0)["rotation"]) < 1e-6
    assert abs(tf.sample(2.0)["rotation"] - 720.0) < 1e-6       # 2 full turns


def test_pop_overshoots_then_settles():
    pid = _new()
    cid = add_text(pid, "hi", duration=3.0)["clip_id"]
    M.animate_clip(pid, "pop", clip_id=cid)
    tf = _transform(_clip0(pid))
    assert tf.sample(0.0)["scale"][0] < 1.0                     # starts small
    peak = max(tf.sample(t * 0.05)["scale"][0] for t in range(11))
    assert peak > 1.0                                          # overshoots
    assert abs(tf.sample(0.5)["scale"][0] - 1.0) < 1e-6        # settles to 1


def test_shake_decays_to_base():
    pid = _new()
    cid = add_text(pid, "hi", duration=3.0, position=[500, 500])["clip_id"]
    M.animate_clip(pid, "shake", clip_id=cid, amount=30)
    tf = _transform(_clip0(pid))
    early = tf.sample(0.05)["position"]
    assert abs(early[0] - 500) > 5 or abs(early[1] - 500) > 5   # jitters early
    # last keyframe amplitude is smaller than the first jitter (decay)
    kfs = _clip0(pid)["transform"]["position"]["keyframes"]
    import math
    amp = lambda kf: math.hypot(kf["value"][0] - 500, kf["value"][1] - 500)
    assert amp(kfs[1]) > amp(kfs[-1])


def test_animate_around_existing_keyframed_position():
    pid = _new()
    cid = add_text(pid, "hi", duration=4.0)["clip_id"]
    # give it an explicit position first, then float should center on it
    _proj(pid)  # ensure exists
    M.animate_clip(pid, "float", clip_id=cid, amount=15, cycles=1)
    # re-applying reads first key as base -> stays anchored near center
    M.animate_clip(pid, "float", clip_id=cid, amount=15, cycles=1)
    tf = _transform(_clip0(pid))
    p0 = tf.sample(0.0)["position"]
    assert abs(p0[0] - 500) < 1.0                              # canvas center x


def test_bad_preset_raises():
    pid = _new()
    cid = add_text(pid, "hi", duration=2.0)["clip_id"]
    try:
        M.animate_clip(pid, "moonwalk", clip_id=cid)
        assert False
    except ValueError as e:
        assert "moonwalk" in str(e)


def test_registered_and_in_capabilities():
    import dabwayo
    from dabwayo.mcp_tools.app import mcp
    import asyncio
    names = {t.name for t in
             asyncio.get_event_loop().run_until_complete(mcp.list_tools())}
    assert "animate_clip" in names
    assert "float" in dabwayo.capabilities()["motion_presets"]
