"""Storyboard structure + deterministic assembly (no generation required)."""
from dabwayo import mcp_server as M


def _proj():
    return M.create_project(1280, 720, fps=24, name="sb")["project_id"]


def test_add_list_update_remove_shot():
    pid = _proj()
    a = M.add_shot(pid, prompt="A", duration=2)["shot_id"]
    b = M.add_shot(pid, prompt="B", duration=3, caption="hi")["shot_id"]
    assert M.list_shots(pid)["count"] == 2
    M.update_shot(pid, a, {"duration": 5})
    shots = {s["id"]: s for s in M.get_project(pid)["storyboard"]}
    assert shots[a]["duration"] == 5
    # id is immutable
    M.update_shot(pid, a, {"id": "HACK"})
    assert a in {s["id"] for s in M.get_project(pid)["storyboard"]}
    M.remove_shot(pid, b)
    assert M.list_shots(pid)["count"] == 1


def test_assemble_places_placeholders_and_captions_without_generation():
    pid = _proj()
    M.add_shot(pid, prompt="scene one", duration=2, caption="one")
    M.add_shot(pid, prompt="scene two", duration=3, caption="two")
    r = M.assemble_storyboard(pid, generate=False)
    assert r["generated"] == 0                      # no external calls
    assert len(r["clips"]) == 2 and r["duration"] == 5.0
    tracks = {t["track"]: len(t["clips"]) for t in M.list_clips(pid)["tracks"]}
    assert tracks.get("video") == 2 and tracks.get("captions") == 2


def test_storyboard_state_is_ignored_by_engine():
    # storyboard lives in the spec but must not break rendering/estimate
    pid = _proj()
    M.add_shot(pid, prompt="x", duration=2)
    M.assemble_storyboard(pid, generate=False)
    est = M.estimate(pid)
    assert est["duration"] == 2.0
