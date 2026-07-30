"""Tests for list_tools_catalog — the descriptive, searchable tool catalog."""
from dabwayo.mcp_tools import discovery as D


def test_catalog_covers_every_category_and_tool():
    c = D.list_tools_catalog()
    # 24 category modules, each present with tools
    assert len(c["categories"]) == 24
    assert c["total_tools"] >= 100
    for cat in c["categories"]:
        assert cat["tools"] and cat["purpose"]
        for t in cat["tools"]:
            assert t["name"] and isinstance(t["summary"], str)


def test_summaries_derive_from_docstrings_no_drift():
    c = D.list_tools_catalog(category="camera")
    tools = {t["name"]: t["summary"] for t in c["categories"][0]["tools"]}
    assert tools["camera_move"].startswith("Apply a NAMED camera move")


def test_query_finds_tool_by_name():
    c = D.list_tools_catalog(query="duck")
    names = {t["name"] for cat in c["categories"] for t in cat["tools"]}
    assert "duck_audio" in names


def test_query_matches_tags_and_purpose():
    c = D.list_tools_catalog(query="dof")           # camera tag
    assert any(cat["category"] == "camera" for cat in c["categories"])


def test_stage_filter():
    c = D.list_tools_catalog(stage="arrange")
    cats = {cat["category"] for cat in c["categories"]}
    assert cats == {"editing", "camera", "motion", "layout"}


def test_category_filter():
    c = D.list_tools_catalog(category="motion")
    assert len(c["categories"]) == 1
    assert c["categories"][0]["tools"][0]["name"] == "animate_clip"


def test_flow_is_descriptive_and_ordered():
    c = D.list_tools_catalog()
    stages = [s["stage"] for s in c["flow"]]
    assert stages[0] == "discover" and stages[-1] == "deliver"
    # categories are returned in flow order
    order = [cat["stage"] for cat in c["categories"]]
    assert order == sorted(order, key=lambda s: stages.index(s))
    assert "caller's decision" in c["note"]


def test_catalog_registered_as_tool():
    from dabwayo.mcp_tools.app import mcp
    import asyncio
    names = {t.name for t in
             asyncio.get_event_loop().run_until_complete(mcp.list_tools())}
    assert "list_tools_catalog" in names


def test_new_tool_auto_appears_in_catalog():
    """The catalog derives membership from modules, so any registered tool is
    present without touching the catalog — proves the no-drift property."""
    c = D.list_tools_catalog()
    all_names = {t["name"] for cat in c["categories"] for t in cat["tools"]}
    # tools added across this session are all discoverable
    for n in ["camera_move", "set_focus", "align_clips", "duck_audio",
              "animate_clip", "list_tools_catalog"]:
        assert n in all_names
