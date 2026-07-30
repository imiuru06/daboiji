"""Discovery tools: what the engine supports, how to author, and — as the tool
count grows — a structured, searchable catalog of the tools themselves.

The catalog is *descriptive* metadata (category, one-line purpose, tags, where
a category sits in the authoring flow). It exists to make the calling agent's
tool retrieval land on the right tool faster; it deliberately does NOT plan or
sequence calls — that intelligence stays with the agent (scope: ADR-0003)."""
from __future__ import annotations

import re
from typing import Optional

from .. import capabilities as engine_capabilities
from .app import mcp, _HELP

__all__ = ["get_capabilities", "get_help", "list_tools_catalog"]


# Per-category descriptors — the only hand-maintained layer. Category membership
# and each tool's summary are derived from the modules at call time (no drift).
_CATEGORY_META = {
    "discovery":  ("Learn what exists before authoring.", ["capabilities", "help", "catalog"]),
    "projects":   ("Create / update the project container + canvas.", ["project", "canvas", "lifecycle"]),
    "clips":      ("Place content on tracks: text, media, background, callouts, effects, camera, audio.", ["author", "place", "add"]),
    "editing":    ("Reshape existing clips: trim, split, move, duplicate, ripple.", ["trim", "split", "timeline", "rearrange"]),
    "camera":     ("Named camera moves + depth-of-field / focus pulls.", ["camera", "push_in", "focus", "dof"]),
    "motion":     ("Per-clip motion presets: float, pulse, pop, shake, spin.", ["transform", "keyframe", "idle", "emphasis"]),
    "layout":     ("Align / distribute / grid several clips at once.", ["align", "distribute", "grid", "position"]),
    "audio":      ("Mix: auto-duck music under narration.", ["duck", "mix", "music", "vo"]),
    "captions":   ("Captions, lower-thirds and word-level subtitles.", ["subtitle", "srt", "lower_third"]),
    "transcribe": ("Speech-to-text (ASR), provider-pluggable.", ["asr", "transcript", "whisper"]),
    "voiceover":  ("Text-to-speech narration onto the soundtrack.", ["tts", "narration", "voice"]),
    "storyboard": ("Legacy per-project shot list (embedded in a project).", ["shots", "legacy"]),
    "storyboards": ("First-class reusable storyboard store: scenes, shots, cast, assemble.", ["plan", "scenes", "cast", "assemble"]),
    "reference":  ("Character / environment / prop bibles + shot resolution.", ["bible", "character", "consistency"]),
    "generation": ("Generate video / frames via a provider.", ["t2v", "i2v", "provider"]),
    "watermark":  ("Remove watermarks / inpaint regions.", ["delogo", "inpaint", "cleanup"]),
    "music":      ("Search / fetch royalty-free music.", ["music", "jamendo", "freesound"]),
    "assets":     ("Register / list tracked media assets.", ["asset", "index", "media"]),
    "storage":    ("Pluggable storage backends (local / s3 / gcs).", ["storage", "backend", "url"]),
    "dashboard":  ("Studio publish / status / activity log.", ["studio", "publish", "status"]),
    "inspection": ("Preview frames, filmstrip, estimate, list clips.", ["preview", "inspect", "estimate"]),
    "render":     ("Render a project / range / spec to video.", ["render", "export", "mp4"]),
    "comments":   ("Review comments on a project.", ["review", "comment", "feedback"]),
    "templates":  ("Create / batch from reusable templates.", ["template", "batch", "reuse"]),
}

# Descriptive authoring pipeline: which stage each category typically belongs to.
# A map for orientation, NOT a required call order.
_FLOW = [
    ("discover", ["discovery"]),
    ("plan",     ["reference", "storyboards", "storyboard", "templates"]),
    ("source",   ["generation", "music", "assets", "storage"]),
    ("author",   ["projects", "clips"]),
    ("arrange",  ["editing", "camera", "motion", "layout"]),
    ("sound",    ["voiceover", "audio", "transcribe", "captions"]),
    ("polish",   ["watermark"]),
    ("review",   ["inspection", "comments", "dashboard"]),
    ("deliver",  ["render"]),
]
_STAGE_OF = {cat: stage for stage, cats in _FLOW for cat in cats}


# Per-tool search aliases — BILINGUAL (English + 한국어), because callers query
# in either language and a tool's English name rarely contains the word a user
# actually types ("배경 흐리게" / "blur background" -> set_focus). Curated for
# the high-traffic / high-divergence tools; the long tail falls back to matching
# name + summary + category tags. ``use_when`` is a short "reach for this when…".
_TOOL_META = {
    # --- intent-level creative tools (name diverges most from intent) --------
    "camera_move": {"use_when": "move the whole camera / 카메라 전체를 움직일 때",
        "aliases": ["camera", "push in", "zoom in", "dolly", "pan", "tilt",
                    "ken burns", "whip pan", "move camera", "카메라", "줌인",
                    "줌", "밀어", "밀고 들어가", "패닝", "팬", "틸트",
                    "카메라 무빙", "무빙", "켄번즈"]},
    "set_focus": {"use_when": "subject sharp, background soft / 피사체 선명·배경 흐리게",
        "aliases": ["focus", "depth of field", "dof", "blur background", "bokeh",
                    "rack focus", "sharp subject", "초점", "심도", "아웃포커싱",
                    "배경 흐림", "배경 흐리게", "흐리", "흐릿", "흐림", "블러",
                    "보케", "포커스", "포커스 이동"]},
    "animate_clip": {"use_when": "give one clip idle/emphasis motion / 클립 하나에 움직임",
        "aliases": ["animate", "motion", "bounce", "float", "pulse", "pop",
                    "shake", "wiggle", "spin", "breathe", "jitter", "움직임",
                    "모션", "애니메이션", "통통", "튀게", "튀는", "떠다니",
                    "흔들", "흔들리", "진동", "회전", "돌리", "팝", "펄스"]},
    "align_clips": {"use_when": "arrange several clips at once / 여러 클립 정렬",
        "aliases": ["align", "distribute", "grid", "arrange", "center", "layout",
                    "evenly space", "정렬", "배치", "분배", "그리드", "가운데",
                    "균등", "레이아웃", "나란히"]},
    "duck_audio": {"use_when": "dip music under narration / 내레이션에서 음악 줄이기",
        "aliases": ["duck", "ducking", "lower music", "music under voice",
                    "sidechain", "mix", "dim music", "덕킹", "음악 줄여",
                    "음악 낮춰", "내레이션 밑", "배경음 줄이", "볼륨 낮추", "믹싱"]},
    # --- authoring ----------------------------------------------------------
    "add_text": {"use_when": "put words on screen / 화면에 글자",
        "aliases": ["text", "title", "headline", "word", "텍스트", "제목",
                    "타이틀", "글자", "문구", "자막 텍스트"]},
    "add_media": {"use_when": "add an image or video file / 이미지·영상 파일",
        "aliases": ["image", "video", "photo", "footage", "picture", "clip",
                    "이미지", "영상", "사진", "그림", "미디어", "동영상"]},
    "add_background": {"use_when": "full-frame background / 전체 배경",
        "aliases": ["background", "backdrop", "solid", "gradient", "color fill",
                    "배경", "백그라운드", "단색", "그라디언트", "배경색"]},
    "add_callout": {"use_when": "speech-bubble annotation overlay / 말풍선 주석",
        "aliases": ["callout", "speech bubble", "annotation", "pointer", "label",
                    "말풍선", "콜아웃", "주석", "설명 풍선", "라벨"]},
    "add_effect": {"use_when": "attach a visual effect / 시각 효과",
        "aliases": ["effect", "glow", "grade", "vignette", "filter", "look",
                    "효과", "이펙트", "글로우", "필터", "색보정", "룩"]},
    "add_audio": {"use_when": "place audio on the soundtrack / 오디오 배치",
        "aliases": ["audio", "music", "sound", "sfx", "soundtrack", "song",
                    "오디오", "음악", "소리", "효과음", "사운드", "배경음악"]},
    "add_captions": {"use_when": "subtitles from cues / 자막",
        "aliases": ["captions", "subtitles", "srt", "vtt", "자막", "캡션"]},
    "add_voiceover": {"use_when": "TTS narration onto the soundtrack / 내레이션",
        "aliases": ["voiceover", "narration", "tts", "voice", "speak", "dub",
                    "내레이션", "성우", "보이스오버", "음성", "더빙", "읽어"]},
    "synthesize_voice": {"use_when": "text-to-speech a line / 음성 합성",
        "aliases": ["tts", "text to speech", "voice", "narration", "음성 합성",
                    "성우", "읽어", "더빙"]},
    "transcribe": {"use_when": "speech to text / 받아쓰기",
        "aliases": ["transcribe", "speech to text", "asr", "subtitles from audio",
                    "전사", "받아쓰기", "음성 인식", "자막 추출"]},
    "generate_video": {"use_when": "AI-generate a clip / 영상 생성",
        "aliases": ["generate", "ai video", "text to video", "t2v", "i2v",
                    "create clip", "생성", "영상 생성", "만들어", "제너레이트"]},
    "remove_watermark": {"use_when": "erase a watermark/logo / 워터마크 제거",
        "aliases": ["watermark", "logo", "delogo", "remove logo", "inpaint",
                    "워터마크", "로고 제거", "지워", "인페인트"]},
    "fetch_music": {"use_when": "download royalty-free music / 음원 받기",
        "aliases": ["music", "royalty free", "background music", "song", "track",
                    "음원", "배경음악", "무료 음악", "노래"]},
    "search_music": {"use_when": "find music candidates / 음원 검색",
        "aliases": ["music", "search song", "find music", "음원 검색", "노래 찾"]},
    "render_project": {"use_when": "export the finished video / 영상 내보내기",
        "aliases": ["render", "export", "output", "mp4", "produce video",
                    "렌더", "렌더링", "내보내", "출력", "완성"]},
    "render_range": {"use_when": "preview-render a section / 구간 렌더",
        "aliases": ["render range", "preview render", "구간 렌더", "부분 렌더"]},
    "trim_clip": {"use_when": "shorten a clip's edges / 클립 다듬기",
        "aliases": ["trim", "cut edges", "shorten", "트림", "다듬", "잘라 다듬"]},
    "split_clip": {"use_when": "cut a clip in two / 클립 나누기",
        "aliases": ["split", "cut", "divide", "분할", "나누", "컷", "잘라"]},
    "move_clip": {"use_when": "retime / move a clip / 클립 이동",
        "aliases": ["move", "retime", "reposition", "이동", "옮기", "시간 이동"]},
    "create_project": {"use_when": "start a new project / 새 프로젝트",
        "aliases": ["new project", "create", "start", "canvas", "새 프로젝트",
                    "생성", "시작", "만들"]},
    "create_storyboard": {"use_when": "author a reusable storyboard / 스토리보드",
        "aliases": ["storyboard", "shots", "plan", "scenes", "스토리보드",
                    "콘티", "장면", "샷 리스트"]},
    "create_reference": {"use_when": "make a character/prop bible / 레퍼런스 바이블",
        "aliases": ["character", "reference", "bible", "consistency", "sheet",
                    "prop", "environment", "캐릭터", "레퍼런스", "바이블",
                    "시트", "일관성", "소품", "배경 시트"]},
}


def _tokens(s: str):
    return [t for t in re.split(r"[^0-9a-z가-힣]+", s.lower()) if len(t) >= 2]


def _score(query: str, name: str, summary: str, cat: str, tags) -> float:
    """Relevance of a tool to ``query`` (0 = no match). Weights name > aliases
    > use_when > summary > tags/category. Token-level with bidirectional
    substring so light KO inflection / EN plurals still hit."""
    meta = _TOOL_META.get(name, {})
    aliases = [a.lower() for a in meta.get("aliases", [])]
    use_when = meta.get("use_when", "").lower()
    name_l, sum_l, cat_l = name.lower(), summary.lower(), cat.lower()
    tags_l = [t.lower() for t in tags]
    q = query.lower().strip()
    toks = _tokens(q) or ([q] if q else [])
    if not toks:
        return 0.0

    def hit(tok, term):
        return tok in term or (len(tok) >= 3 and term in tok)

    score = 0.0
    if q and q in name_l:
        score += 3.0                                   # whole-query phrase bonus
    for tok in toks:
        if tok in name_l:
            score += 5.0
        elif any(hit(tok, a) for a in aliases):
            score += 4.0
        elif tok in use_when:
            score += 3.0
        elif tok in sum_l:
            score += 2.0
        elif tok in cat_l or any(hit(tok, t) for t in tags_l):
            score += 1.0
    return score


def _summary(func) -> str:
    """First non-empty line of a tool's docstring."""
    for line in (func.__doc__ or "").strip().splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _catalog():
    """Build {category: {purpose, tags, stage, tools:[{name, summary}]}} by
    introspecting the registered category modules — so it never drifts from the
    actual tool set."""
    import dabwayo.mcp_tools as pkg
    out = {}
    for mod in getattr(pkg, "_MODULES", []):
        cat = mod.__name__.rsplit(".", 1)[-1]
        purpose, tags = _CATEGORY_META.get(cat, ("", []))
        tools = [{"name": name, "summary": _summary(getattr(mod, name))}
                 for name in getattr(mod, "__all__", [])]
        if not tools:
            continue
        out[cat] = {"purpose": purpose, "tags": tags,
                    "stage": _STAGE_OF.get(cat, ""), "tools": tools}
    return out


@mcp.tool()
def get_capabilities() -> dict:
    """List everything the engine supports: element types, effects,
    transitions, blend modes, easings, anchors, and the named camera_moves /
    motion_presets / layout_modes vocabularies. Call this first to learn which
    values are valid for the other tools."""
    return engine_capabilities()


@mcp.tool()
def get_help() -> str:
    """Return a concise authoring guide: coordinate system, the spec model,
    how keyframes/transitions/effects work, and a minimal example."""
    return _HELP


@mcp.tool()
def list_tools_catalog(category: Optional[str] = None,
                       query: Optional[str] = None,
                       stage: Optional[str] = None) -> dict:
    """Browse the tool catalog — every tool grouped by category, with a
    one-line purpose, tags, and where it sits in the authoring flow.

    As the tool count grows this is the map for finding the right one:
      - ``query`` — natural-language lookup ("which tool does X?"), matched
        against each tool's name, BILINGUAL aliases (EN + 한국어), one-line
        "use when", summary and tags. Results are RANKED by relevance and each
        carries a ``score``. Complements the client's own tool search.
      - ``category`` — restrict to one category (e.g. "camera", "motion").
      - ``stage`` — restrict to a flow stage: discover, plan, source, author,
        arrange, sound, polish, review, deliver.

    Returns the matching categories (each with its tools + ``use_when``), plus
    ``flow`` (the descriptive stage→categories pipeline) and totals. When
    ``query`` is set, categories and tools are ordered best-match first;
    otherwise they follow the authoring flow. Orientation only — it does not
    decide call order; that is the caller's judgment."""
    cat = _catalog()
    q = (query or "").strip()
    result = []
    total = 0
    flow_order = [s for s, _ in _FLOW]
    for name, info in cat.items():
        if category and name != category:
            continue
        if stage and info["stage"] != stage:
            continue
        tools = []
        for t in info["tools"]:
            entry = {**t, "use_when": _TOOL_META.get(t["name"], {}).get("use_when", "")}
            if q:
                sc = _score(q, t["name"], t["summary"], name, info["tags"])
                if sc <= 0:
                    continue
                entry["score"] = round(sc, 1)
            tools.append(entry)
        if q and not tools:
            continue
        if q:
            tools.sort(key=lambda t: t["score"], reverse=True)
        total += len(tools)
        best = max((t.get("score", 0) for t in tools), default=0)
        result.append({"category": name, "purpose": info["purpose"],
                       "tags": info["tags"], "stage": info["stage"],
                       "tool_count": len(tools), "_best": best, "tools": tools})
    if q:
        result.sort(key=lambda c: c["_best"], reverse=True)
    else:
        result.sort(key=lambda c: flow_order.index(c["stage"])
                    if c["stage"] in flow_order else 99)
    for c in result:
        c.pop("_best", None)
    return {
        "total_tools": total,
        "categories": result,
        "flow": [{"stage": s, "categories": cs} for s, cs in _FLOW],
        "note": "Descriptive map for tool retrieval; call order is the "
                "caller's decision, not implied by the flow.",
    }
