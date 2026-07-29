"""First-class storyboard library (ADR-0002) — decoupled, multi-cast, props."""
from dabwayo import mcp_server as M


def test_storyboard_is_reusable_store_entity_with_scenes_and_shots():
    sb = M.create_storyboard("Ep1", "test", width=1920, height=1080)["storyboard"]
    assert sb["id"].startswith("sb_") and sb["width"] == 1920
    sc = M.add_scene(sb["id"], "opening")["scene"]
    sh = M.add_storyboard_shot(sb["id"], sc["id"], prompt="a", duration=2)["shot_id"]
    M.add_storyboard_shot(sb["id"], sc["id"], prompt="b", duration=3)
    lst = M.list_storyboards()["storyboards"]
    row = [r for r in lst if r["id"] == sb["id"]][0]
    assert row["scenes"] == 1 and row["shots"] == 2
    # editable in place
    M.update_storyboard_shot(sb["id"], sh, {"caption": "hi"})
    got = M.get_storyboard(sb["id"])["storyboard"]
    assert got["scenes"][0]["shots"][0]["caption"] == "hi"


def test_multi_cast_and_props_resolve():
    a = M.create_reference("character", "Mina", "woman, dark bob")["reference"]
    b = M.create_reference("character", "Jun", "man, glasses")["reference"]
    env = M.create_reference("environment", "Cafe", "cozy cafe")["reference"]
    prop = M.create_reference("prop", "Cup", "a ceramic cup")["reference"]
    sb = M.create_storyboard("multi")["storyboard"]
    sc = M.add_scene(sb["id"])["scene"]
    sh = M.add_storyboard_shot(
        sb["id"], sc["id"], prompt="they talk",
        cast=[{"character_id": a["id"]}, {"character_id": b["id"]}],
        environment={"id": env["id"]}, props=[{"prop_id": prop["id"]}],
        camera={"angle": "two-shot"})["shot_id"]
    r = M.resolve_storyboard_shot(sb["id"], sh)
    for token in ("dark bob", "glasses", "cozy cafe", "ceramic cup", "two-shot", "they talk"):
        assert token in r["prompt"]


def test_one_storyboard_assembles_into_many_projects():
    sb = M.create_storyboard("reuse", width=256, height=144, fps=8)["storyboard"]
    sc = M.add_scene(sb["id"])["scene"]
    M.add_storyboard_shot(sb["id"], sc["id"], prompt="x", duration=1)
    p1 = M.assemble_storyboard_project(sb["id"])["project_id"]
    p2 = M.assemble_storyboard_project(sb["id"])["project_id"]
    assert p1 != p2                                    # plan reused, outputs separate
    assert M.get_storyboard(sb["id"])["storyboard"]["id"] == sb["id"]   # plan still in store
    assert M.estimate(p1)["duration"] == 1.0
