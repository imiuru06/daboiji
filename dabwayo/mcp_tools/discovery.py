"""Discovery tools: what the engine supports, how to author, and — as the tool
count grows — a structured, searchable catalog of the tools themselves.

The catalog is *descriptive* metadata (category, one-line purpose, tags, where
a category sits in the authoring flow). It exists to make the calling agent's
tool retrieval land on the right tool faster; it deliberately does NOT plan or
sequence calls — that intelligence stays with the agent (scope: ADR-0003)."""
from __future__ import annotations

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
      - ``query`` — substring match over tool name / summary / tags / category
        (a quick "which tool does X?" lookup; complements client-side search).
      - ``category`` — restrict to one category (e.g. "camera", "motion").
      - ``stage`` — restrict to a flow stage: discover, plan, source, author,
        arrange, sound, polish, review, deliver.

    Returns the matching categories (each with its tools), plus ``flow`` (the
    descriptive stage→categories pipeline) and totals. This is orientation
    only — it does not decide call order; that is the caller's judgment."""
    cat = _catalog()
    q = (query or "").strip().lower()
    result = []
    total = 0
    for name, info in cat.items():
        if category and name != category:
            continue
        if stage and info["stage"] != stage:
            continue
        tools = info["tools"]
        if q:
            hay_cat = q in name or q in info["purpose"].lower() or \
                any(q in t for t in info["tags"])
            tools = [t for t in tools
                     if hay_cat or q in t["name"].lower() or q in t["summary"].lower()]
            if not tools:
                continue
        total += len(tools)
        result.append({"category": name, "purpose": info["purpose"],
                       "tags": info["tags"], "stage": info["stage"],
                       "tool_count": len(tools), "tools": tools})
    result.sort(key=lambda c: [s for s, _ in _FLOW].index(c["stage"])
                if c["stage"] in [s for s, _ in _FLOW] else 99)
    return {
        "total_tools": total,
        "categories": result,
        "flow": [{"stage": s, "categories": cs} for s, cs in _FLOW],
        "note": "Descriptive map for tool retrieval; call order is the "
                "caller's decision, not implied by the flow.",
    }
