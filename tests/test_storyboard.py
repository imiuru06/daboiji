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


def test_generate_shot_binds_media_and_composes_from_references():
    # end-to-end with the offline 'local' provider; t2v so no image needed
    pid = M.create_project(256, 144, fps=8, name="p2")["project_id"]
    ch = M.create_reference("character", "Mina", "late-20s, dark bob")["reference"]
    s = M.add_shot(pid, prompt="looks to the light", duration=1, mode="t2v")["shot_id"]
    M.bind_shot(pid, s, character_id=ch["id"])
    g = M.generate_shot(pid, s, provider="local")
    assert g["path"] and g["provider"] == "local"
    assert "dark bob" in g["prompt"] and "looks to the light" in g["prompt"]
    shot = [x for x in M.get_project(pid)["storyboard"] if x["id"] == s][0]
    assert shot.get("media") == g["path"]           # bound back onto the shot
