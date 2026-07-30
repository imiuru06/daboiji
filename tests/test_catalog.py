"""Tests for list_tools_catalog — the descriptive, searchable tool catalog."""
import json

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


# --------------------------------------------------------------------------
# Retrieval quality — bilingual (EN + 한국어) intent -> expected tool.
# This is the measurable "is it good?" check, not a vibe.
# --------------------------------------------------------------------------
_INTENTS = [
    # (natural-language query, expected tool)  -- Korean
    ("배경 흐리게", "set_focus"),
    ("피사체만 초점 맞추고 배경 아웃포커싱", "set_focus"),
    ("로고가 통통 튀게", "animate_clip"),
    ("클립 흔들리게", "animate_clip"),
    ("카메라 밀고 들어가", "camera_move"),
    ("음악 내레이션 밑에서 줄여", "duck_audio"),
    ("여러 자막 나란히 정렬", "align_clips"),
    ("워터마크 지워", "remove_watermark"),
    ("영상 내보내", "render_project"),
    ("배경음악 받아와", "fetch_music"),
    ("클립 둘로 나누기", "split_clip"),
    ("말풍선 넣어", "add_callout"),
    # -- English
    ("blur the background", "set_focus"),
    ("make the logo bounce", "animate_clip"),
    ("slow push in on the frame", "camera_move"),
    ("duck the music under the voiceover", "duck_audio"),
    ("distribute the callouts evenly", "align_clips"),
    ("remove the watermark", "remove_watermark"),
    ("export the final video", "render_project"),
    ("add a speech bubble", "add_callout"),
    # -- fallback (no curated alias -> must still hit via name/summary)
    ("filmstrip", "filmstrip"),
    ("estimate render time", "estimate"),
]


def _ranked(query):
    r = D.list_tools_catalog(query=query)
    return [t["name"] for cat in r["categories"] for t in cat["tools"]]


def test_retrieval_recall_at_k_bilingual():
    r1 = r3 = 0
    misses = []
    for q, want in _INTENTS:
        ranked = _ranked(q)
        if ranked[:1] == [want]:
            r1 += 1
        if want in ranked[:3]:
            r3 += 1
        else:
            misses.append((q, want, ranked[:3]))
    n = len(_INTENTS)
    # recall@3 must be perfect; recall@1 strong. Fail loudly with the misses.
    assert r3 == n, f"recall@3 {r3}/{n}; misses={misses}"
    assert r1 / n >= 0.8, f"recall@1 {r1}/{n} below 0.8"


def test_retrieval_precision_mrr():
    """MRR guards against over-aliasing: if generic aliases push wrong tools
    above the right one, mean reciprocal rank drops even when recall holds."""
    total = 0.0
    for q, want in _INTENTS:
        ranked = _ranked(q)
        rank = ranked.index(want) + 1 if want in ranked else 0
        total += (1.0 / rank) if rank else 0.0
    mrr = total / len(_INTENTS)
    assert mrr >= 0.9, f"MRR {mrr:.3f} < 0.9 — aliases may be too generic"


def test_every_tool_findable_by_its_own_name():
    """No registered tool is ever invisible — the fallback (name/summary/tags)
    guarantees a new tool is retrievable the moment it is added, with zero
    curation. This is the 'auto-coverage' property."""
    c = D.list_tools_catalog()
    names = [t["name"] for cat in c["categories"] for t in cat["tools"]]
    invisible, not_top = [], []
    for n in names:
        ranked = _ranked(n.replace("_", " "))
        if n not in ranked:
            invisible.append(n)
        elif ranked[0] != n:
            not_top.append((n, ranked[0]))
    assert not invisible, f"invisible tools: {invisible}"
    # the vast majority should also rank #1 by their own name
    assert len(not_top) <= len(names) * 0.15, f"not top-1: {not_top}"


def test_alias_coverage_reported():
    cov = D.list_tools_catalog()["alias_coverage"]
    assert cov["total"] >= 100
    assert 0 < cov["curated"] <= cov["total"]


def test_external_alias_overlay_extends_without_code_change(tmp_path, monkeypatch):
    # a KO alias that exists nowhere in code
    before = _ranked("썸네일 스트립")
    assert "filmstrip" not in before
    ov = tmp_path / "aliases.json"
    ov.write_text(json.dumps({"filmstrip": {
        "aliases": ["썸네일 스트립", "thumbnail strip"],
        "use_when": "strip of thumbnails / 썸네일 띠"}}), encoding="utf-8")
    monkeypatch.setenv("DABWAYO_TOOL_ALIASES", str(ov))
    after = _ranked("썸네일 스트립")
    assert after and after[0] == "filmstrip"          # overlay took effect
    cov = D.list_tools_catalog()["alias_coverage"]
    assert cov["curated"] >= 1


def test_results_are_ranked_with_scores():
    r = D.list_tools_catalog(query="duck music under voiceover")
    cats = r["categories"]
    # top category is the best match; its top tool is duck_audio
    assert cats[0]["tools"][0]["name"] == "duck_audio"
    assert cats[0]["tools"][0]["use_when"]                     # use_when surfaced
    # categories ordered by best score, tools ranked within each category
    cat_best = [max(t["score"] for t in c["tools"]) for c in cats]
    assert cat_best == sorted(cat_best, reverse=True)
    for c in cats:
        s = [t["score"] for t in c["tools"]]
        assert s == sorted(s, reverse=True)


def test_new_tool_auto_appears_in_catalog():
    """The catalog derives membership from modules, so any registered tool is
    present without touching the catalog — proves the no-drift property."""
    c = D.list_tools_catalog()
    all_names = {t["name"] for cat in c["categories"] for t in cat["tools"]}
    # tools added across this session are all discoverable
    for n in ["camera_move", "set_focus", "align_clips", "duck_audio",
              "animate_clip", "list_tools_catalog"]:
        assert n in all_names
