"""Dabwayo MCP server.

Exposes the rendering engine as MCP tools so other agents can author and
render video declaratively. Two complementary styles are supported:

* Stateful authoring — ``create_project`` then ``add_*`` tools mutate a
  server-held project, finishing with ``render_project``.
* Stateless — ``render_from_spec`` renders a complete JSON project in one
  call (ideal when an agent assembles the whole spec itself).

Run:  python -m dabwayo.mcp_server         (stdio transport)
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from . import capabilities as engine_capabilities
from .builder import Project
from .render.engine import render, render_thumbnail
from .core.timeline import Timeline
from .service import OUTPUT_DIR as _OUTPUT_DIR, STORE as _PROJECTS

mcp = FastMCP("dabwayo")


def _proj(project_id: str) -> dict:
    if project_id not in _PROJECTS:
        raise ValueError(f"Unknown project_id {project_id!r}. Call create_project first.")
    return _PROJECTS[project_id]


def _commit(project_id: str, spec: dict) -> None:
    """Persist a mutated spec back to the shared store."""
    _PROJECTS[project_id] = spec


def _video_track(spec: dict, track_name: Optional[str]) -> dict:
    tracks = spec["tracks"]
    if track_name:
        for tr in tracks:
            if tr.get("name") == track_name and tr.get("kind", "video") == "video":
                return tr
        tr = {"kind": "video", "name": track_name, "clips": []}
        tracks.append(tr)
        return tr
    for tr in tracks:
        if tr.get("kind", "video") == "video":
            return tr
    tr = {"kind": "video", "name": "video", "clips": []}
    tracks.append(tr)
    return tr


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
@mcp.tool()
def get_capabilities() -> dict:
    """List everything the engine supports: element types, effects,
    transitions, blend modes, easings and anchors. Call this first to learn
    which values are valid for the other tools."""
    return engine_capabilities()


@mcp.tool()
def get_help() -> str:
    """Return a concise authoring guide: coordinate system, the spec model,
    how keyframes/transitions/effects work, and a minimal example."""
    return _HELP


# --------------------------------------------------------------------------
# Project lifecycle
# --------------------------------------------------------------------------
@mcp.tool()
def create_project(width: int = 1920, height: int = 1080, fps: float = 30.0,
                   background: str = "#0b0e16", name: str = "untitled",
                   duration: Optional[float] = None) -> dict:
    """Create a new video project and return its ``project_id``.

    width/height: output resolution in pixels (e.g. 1920x1080, 1080x1920 for
    vertical, 1080x1080 for square). background: hex/named color shown behind
    all tracks. duration: optional fixed length in seconds; if omitted it is
    derived from the latest clip end."""
    pid = uuid.uuid4().hex[:12]
    p = Project(width, height, fps, background, duration, name)
    _PROJECTS[pid] = p.spec
    return {"project_id": pid, "spec": p.spec}


@mcp.tool()
def add_track(project_id: str, name: str, kind: str = "video") -> dict:
    """Add a named track. kind='video' tracks composite bottom-to-top in the
    order created; kind='audio' tracks are mixed into the soundtrack. Use the
    track ``name`` when adding clips to target a specific layer."""
    spec = _proj(project_id)
    spec["tracks"].append({"kind": kind, "name": name, "clips": []})
    _commit(project_id, spec)
    return {"ok": True, "tracks": [t.get("name") for t in spec["tracks"]]}


# --------------------------------------------------------------------------
# Clip authoring
# --------------------------------------------------------------------------
@mcp.tool()
def add_clip(project_id: str, element: dict, start: float = 0.0,
             duration: float = 5.0, track: Optional[str] = None,
             transform: Optional[dict] = None, effects: Optional[List[dict]] = None,
             blend_mode: str = "normal", transition_in: Optional[dict] = None,
             transition_out: Optional[dict] = None, depth: float = 1.0,
             name: str = "") -> dict:
    """Add a clip to a video track. ``element`` is an element spec dict (see
    get_capabilities / add_text/add_background helpers). ``transform`` may set
    position [x,y], scale (number or [sx,sy]), rotation (deg), opacity (0..1),
    anchor; any of these may be a keyframed property
    ({"keyframes":[{"time":t,"value":v,"easing":e}]}). Returns the clip index."""
    spec = _proj(project_id)
    tr = _video_track(spec, track)
    clip: Dict[str, Any] = {"element": element, "start": start, "duration": duration}
    if transform:
        clip["transform"] = transform
    if effects:
        clip["effects"] = effects
    if blend_mode != "normal":
        clip["blend_mode"] = blend_mode
    if transition_in:
        clip["transition_in"] = transition_in
    if transition_out:
        clip["transition_out"] = transition_out
    if depth != 1.0:
        clip["depth"] = depth
    if name:
        clip["name"] = name
    tr["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "track": tr.get("name"), "clip_index": len(tr["clips"]) - 1}


@mcp.tool()
def add_text(project_id: str, text: str, start: float = 0.0, duration: float = 5.0,
             size: int = 96, font: str = "sans", color: str = "#ffffff",
             align: str = "center", position: Optional[List[float]] = None,
             track: Optional[str] = None, shadow: Optional[dict] = None,
             stroke: Optional[str] = None, stroke_width: int = 0,
             max_width: Optional[int] = None, transition_in: Optional[dict] = None,
             transition_out: Optional[dict] = None,
             effects: Optional[List[dict]] = None) -> dict:
    """Convenience: add a text clip. ``font`` accepts aliases
    (sans, sans-bold, display, serif, mono) or a bundled font name. ``shadow``
    e.g. {"color":"#000000aa","offset":[0,6],"blur":10}. ``position`` defaults
    to canvas center when omitted."""
    element = {"type": "text", "text": text, "size": size, "font": font,
               "color": color, "align": align}
    if max_width:
        element["max_width"] = max_width
    if shadow:
        element["shadow"] = shadow
    if stroke:
        element["stroke"] = stroke
        element["stroke_width"] = stroke_width
    transform = {"position": position} if position else None
    return add_clip(project_id, element, start, duration, track, transform,
                    effects, "normal", transition_in, transition_out)


@mcp.tool()
def add_callout(project_id: str, text: str, position: List[float], start: float = 0.0,
                duration: float = 4.0, tail_side: str = "bottom", fill: str = "#ffffff",
                color: str = "#0b0e16", font: str = "kr-bold", font_size: int = 34,
                max_width: int = 520, stroke: Optional[str] = None,
                track: Optional[str] = None, transition_in: Optional[dict] = None,
                transition_out: Optional[dict] = None) -> dict:
    """Add a speech-bubble callout for explainer/product overlays. ``position``
    [x,y] places the bubble; ``tail_side`` (bottom/top/left/right) points the
    pointer toward the feature you are annotating. Pair with a `pop`/`slide`
    transition_in for a lively reveal."""
    element = {"type": "callout", "text": text, "tail_side": tail_side,
               "fill": fill, "color": color, "font": font, "font_size": font_size,
               "max_width": max_width}
    if stroke:
        element["stroke"] = stroke
        element["stroke_width"] = 2
    transform = {"position": position, "anchor": "center"}
    return add_clip(project_id, element, start, duration, track, transform,
                    None, "normal", transition_in, transition_out)


@mcp.tool()
def add_background(project_id: str, color: str = "#0b0e16", start: float = 0.0,
                   duration: float = 5.0, gradient: Optional[dict] = None,
                   track: Optional[str] = None) -> dict:
    """Add a full-frame solid or gradient background clip. For a gradient pass
    e.g. {"stops":[[0,"#12203a"],[1,"#0b0e16"]], "kind":"radial", "angle":90}."""
    if gradient:
        element = {"type": "gradient", **gradient}
    else:
        element = {"type": "solid", "color": color}
    return add_clip(project_id, element, start, duration, track)


@mcp.tool()
def add_media(project_id: str, path: str, kind: str = "image", start: float = 0.0,
              duration: float = 5.0, fit: str = "cover", size: Optional[List[int]] = None,
              track: Optional[str] = None, transform: Optional[dict] = None,
              effects: Optional[List[dict]] = None,
              transition_in: Optional[dict] = None,
              transition_out: Optional[dict] = None,
              speed: float = 1.0, loop: bool = False, source_start: float = 0.0,
              crop: Optional[List[float]] = None) -> dict:
    """Add an image or video file clip. kind='image' or 'video'. fit controls
    scaling to ``size`` (or canvas): contain|cover|stretch|none.

    Video editing controls (video clips): ``speed`` retimes playback
    (0.5 = half-speed/slow-mo, 2 = double-speed); ``loop`` repeats the source
    if the clip outlasts it; ``source_start`` trims in from this many seconds
    into the source. ``crop`` = [x, y, w, h] as fractions (0..1) of the source
    frame, applied before fit (works for image and video)."""
    element: Dict[str, Any] = {"type": kind, "path": path, "fit": fit}
    if size:
        element["size"] = size
    if crop:
        element["crop"] = crop
    if kind == "video":
        if speed != 1.0:
            element["speed"] = speed
        if loop:
            element["loop"] = True
        if source_start:
            element["start"] = source_start
    return add_clip(project_id, element, start, duration, track, transform,
                    effects, "normal", transition_in, transition_out)


@mcp.tool()
def list_video_providers() -> dict:
    """List generative-video backends and whether each is ready (which API key
    / Colab URL is needed). The 'active' one is what generate_video will use."""
    from .generation.registry import list_providers
    return list_providers()


@mcp.tool()
def generate_video(project_id: str, prompt: str, mode: str = "t2v",
                   image: Optional[str] = None, duration: float = 4.0,
                   fps: float = 24.0, width: int = 768, height: int = 432,
                   seed: Optional[int] = None, steps: int = 30,
                   guidance: float = 3.0, provider: Optional[str] = None,
                   add_to_timeline: bool = True, start: float = 0.0,
                   track: Optional[str] = None, fit: str = "cover",
                   transform: Optional[dict] = None,
                   effects: Optional[List[dict]] = None,
                   transition_in: Optional[dict] = None,
                   transition_out: Optional[dict] = None) -> dict:
    """Generate a video clip with a generative model and (by default) drop it
    onto the timeline as a ``video`` clip — so AI-generated footage composites
    with text/effects/camera/audio like anything else.

    mode='t2v' generates from ``prompt``; mode='i2v' animates ``image`` (a path)
    guided by ``prompt``. The backend is chosen by list_video_providers()'s
    'active' entry unless ``provider`` is given (local|remote|replicate|fal|
    huggingface). 'local' needs no GPU/key (abstract, not photoreal); 'remote'
    targets a Google Colab GPU server (set DABWAYO_VIDEOGEN_URL). If
    ``add_to_timeline`` is false, only the asset is produced.
    """
    from .generation import generate_video as _gen
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(_OUTPUT_DIR, f"gen_{uuid.uuid4().hex[:8]}.mp4")
    t0 = time.time()
    res = _gen(prompt, out_path, mode=mode, image=image, duration=duration,
               fps=fps, width=width, height=height, seed=seed, steps=steps,
               guidance=guidance, provider=provider)
    info = res.as_dict()
    info["ok"] = True
    info["generate_seconds"] = round(time.time() - t0, 2)
    # register as an asset (provenance) + timeline log
    from . import assets as _assets
    ast = _assets.register(res.path, kind="video", role="raw",
                           source={"action": "generate", "provider": res.provider,
                                   "prompt": prompt, "params": {"mode": mode,
                                   "duration": duration, "seed": seed, "steps": steps}},
                           projects=[project_id] if add_to_timeline else [])
    info["asset_id"] = ast["id"]
    _log_activity_safe("generate", f"{res.provider} {mode} 생성",
                       [f"prompt: {prompt[:60]}"], [ast["id"]])
    if add_to_timeline:
        clip = add_media(project_id, res.path, "video", start,
                         res.frames / float(res.fps), fit, None, track,
                         transform, effects, transition_in, transition_out)
        info["track"] = clip.get("track")
        info["clip_index"] = clip.get("clip_index")
    return info


# --------------------------------------------------------------------------
# Watermark removal (remote LaMa server)
# --------------------------------------------------------------------------
@mcp.tool()
def lama_health() -> dict:
    """Check the remote LaMa watermark-removal server (DABWAYO_LAMA_URL).

    The heavy ML inpainter runs off-box on a Colab GPU server
    (colab/dabwayo_lama_server.ipynb). Returns its /health payload, or
    ``{"ok": false, "detail": ...}`` if it is not configured/reachable."""
    from .dewatermark import health, DewatermarkError
    try:
        return {"ok": True, **health()}
    except DewatermarkError as e:
        return {"ok": False, "detail": str(e)}


@mcp.tool()
def remove_watermark(input_path: str, regions: List[List[int]],
                     out_path: Optional[str] = None, pad: int = 48,
                     feather: int = 4, dilate: int = 9) -> dict:
    """Erase a static watermark/logo from a video via the remote LaMa server.

    ``input_path`` is a local video file. ``regions`` is one or more boxes
    ``[[x, y, w, h], ...]`` (pixels, in the video's own resolution) covering the
    watermark — e.g. the Gemini/Veo ✦ sparkle (bottom-right) or a ModelScope
    'shutterstock' band. The server inpaints every frame on a padded ROI with
    LaMa (deep inpainting — far cleaner than classical fills on detailed,
    moving backgrounds) and muxes the original audio back, so sound is kept.

    Requires DABWAYO_LAMA_URL (run colab/dabwayo_lama_server.ipynb). ``pad``
    is the ROI padding, ``feather`` the blend softness, ``dilate`` grows the
    mask so edges are fully covered. Returns the cleaned ``out_path``."""
    from .dewatermark import remove_watermark as _dewm
    from . import assets as _assets
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"clean_{uuid.uuid4().hex[:8]}.mp4")
    t0 = time.time()
    _dewm(input_path, out_path, regions, pad=pad, feather=feather, dilate=dilate)
    parent = _assets.find_by_path(input_path)        # link provenance if known
    ast = _assets.register(out_path, kind="video", role="dewatermarked",
                           source={"action": "dewatermark", "provider": "lama",
                                   "parent": parent["id"] if parent else None,
                                   "params": {"regions": regions}})
    _log_activity_safe("dewatermark", "워터마크 제거(LaMa)",
                       [parent["id"] if parent else input_path], [ast["id"]])
    return {"ok": True, "path": out_path, "asset_id": ast["id"],
            "parent": parent["id"] if parent else None,
            "seconds": round(time.time() - t0, 2), "regions": regions}


# --------------------------------------------------------------------------
# Music fetch (royalty-free / CC providers) — see dabwayo/music.py
# --------------------------------------------------------------------------
_MUSIC_DIR = os.environ.get("DABWAYO_MUSIC_DIR", "assets/audio")


@mcp.tool()
def list_music_sources() -> dict:
    """List the available music providers and which API key each needs.

    Run the MCP server somewhere with open internet (e.g. your VM); these call
    provider APIs directly. Keys: JAMENDO_CLIENT_ID, FREESOUND_API_KEY."""
    return {
        "sources": [
            {"name": "jamendo", "needs": "JAMENDO_CLIENT_ID",
             "set": bool(os.environ.get("JAMENDO_CLIENT_ID")),
             "good_for": "full background-music tracks, mood/genre/tag search",
             "signup": "https://devportal.jamendo.com"},
            {"name": "freesound", "needs": "FREESOUND_API_KEY",
             "set": bool(os.environ.get("FREESOUND_API_KEY")),
             "good_for": "ambience / SFX / texture layers (HQ previews)",
             "signup": "https://freesound.org/apiv2/apply"},
        ],
        "note": "licences vary per track; every result returns license_url + "
                "an attribution string. Verify terms before publishing.",
    }


@mcp.tool()
def search_music(query: str, source: str = "jamendo", limit: int = 6,
                 instrumental: bool = True, min_duration: int = 0,
                 max_duration: int = 0, tags: str = "") -> dict:
    """Search a music provider and return candidates WITHOUT downloading.

    ``query`` is a mood/keyword (e.g. 'hopeful emotional piano'); ``tags`` adds
    a comma-list of Jamendo fuzzy tags (e.g. 'piano,calm,cinematic'). Each
    result has title/artist/duration/license_url/attribution/download_url so a
    caller can pick before calling ``fetch_music``."""
    from . import music as _music
    items = _music.search(query, source=source, limit=limit,
                          instrumental=instrumental, min_duration=min_duration,
                          max_duration=max_duration, tags=tags)
    return {"ok": True, "source": source, "count": len(items), "results": items}


@mcp.tool()
def fetch_music(query: str, source: str = "jamendo", pick: int = 0,
                limit: int = 6, instrumental: bool = True,
                min_duration: int = 0, max_duration: int = 0, tags: str = "",
                out_path: Optional[str] = None) -> dict:
    """Search, download one track, and register it as a tracked audio asset.

    Searches ``source`` for ``query``, downloads result index ``pick`` (0 =
    top) into DABWAYO_MUSIC_DIR (default assets/audio), and registers it with
    provenance (so it flows into compose/render/publish). Returns the local
    path, asset id, the chosen track's metadata (incl. licence + attribution),
    and the full candidate list. Requires the provider's API key and open
    internet on the host running this server."""
    from . import music as _music
    from . import assets as _assets
    t0 = time.time()
    items = _music.search(query, source=source, limit=limit,
                          instrumental=instrumental, min_duration=min_duration,
                          max_duration=max_duration, tags=tags)
    if not items:
        return {"ok": False, "error": "no results", "source": source, "query": query}
    if pick < 0 or pick >= len(items):
        return {"ok": False, "error": f"pick {pick} out of range (0..{len(items)-1})",
                "results": items}
    chosen = items[pick]
    os.makedirs(_MUSIC_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in chosen.get("title", "track"))[:40] or "track"
    out_path = out_path or os.path.join(_MUSIC_DIR, f"{source}_{chosen['id']}_{safe}.mp3")
    _music.download(chosen, out_path)
    ast = _assets.register(out_path, kind="audio", role="music",
                           source={"action": "fetch_music", "provider": source,
                                   "params": {"query": query, "track_id": chosen["id"],
                                              "license_url": chosen.get("license_url"),
                                              "attribution": chosen.get("attribution")}})
    _log_activity_safe("fetch_music", f"음원 다운로드({source}): {chosen.get('title','')}",
                       [query], [ast["id"]])
    return {"ok": True, "path": out_path, "asset_id": ast["id"],
            "chosen": chosen, "candidates": items,
            "seconds": round(time.time() - t0, 2)}


# --------------------------------------------------------------------------
# Asset registry (JSON management: media + provenance) — see STORE.md
# --------------------------------------------------------------------------
@mcp.tool()
def register_asset(path: str, kind: str = "video", role: str = "other",
                   action: str = "upload", provider: str = "",
                   prompt: str = "", parent: Optional[str] = None,
                   tags: Optional[List[str]] = None) -> dict:
    """Register a media file as a tracked asset with provenance.

    Stores a record under <STORE>/assets/<id>.json (see STORE.md). ``role``:
    raw|dewatermarked|edited|broll|final|upload|other. ``parent`` links to the
    asset this was derived from — that link forms the provenance graph that
    connects multiple media (raw -> dewatermarked -> edited -> final)."""
    from . import assets as _assets
    src = {"action": action, "provider": provider, "prompt": prompt}
    if parent:
        src["parent"] = parent
    return _assets.register(path, kind=kind, role=role, source=src, tags=tags)


@mcp.tool()
def list_assets() -> dict:
    """List all registered assets (id, kind, role, media, source, projects)."""
    from . import assets as _assets
    return {"assets": _assets.list_assets()}


@mcp.tool()
def get_asset(asset_id: str, with_lineage: bool = True) -> dict:
    """Get one asset record; with_lineage walks source.parent back to the root
    so you can see how the media was built up from other media."""
    from . import assets as _assets
    rec = _assets.get(asset_id)
    if with_lineage:
        rec = {**rec, "lineage": [a["id"] for a in _assets.lineage(asset_id)]}
    return rec


@mcp.tool()
def store_index() -> dict:
    """Whole-store manifest: project + asset summaries with counts (see STORE.md)."""
    from . import assets as _assets
    return _assets.build_index()


@mcp.tool()
def organize_store() -> dict:
    """Housekeeping: drop asset records whose files are gone, then return the
    refreshed manifest. Use to tidy the store after deleting media."""
    from . import assets as _assets
    pruned = _assets.prune()
    return {"ok": True, "pruned": pruned, "index": _assets.build_index()}


@mcp.tool()
def publish_to_studio(path: str, role: str = "final", kind: str = "video",
                      action: str = "render", provider: str = "engine",
                      prompt: str = "", parent: Optional[str] = None,
                      project: Optional[str] = None) -> dict:
    """Upload a finished file to the durable VM Studio (DABWAYO_STUDIO_URL).

    The Claude Code sandbox is ephemeral, so call this to persist a result on
    the VM: it is saved to the VM's OUTPUT_DIR, registered as an asset (with
    provenance), and appears in the gallery/dashboard — surviving disconnects.
    Returns the created asset record + its /files URL."""
    from .publish import publish
    return publish(path, role=role, kind=kind, action=action, provider=provider,
                   prompt=prompt, parent=parent, project=project)


@mcp.tool()
def compose_sequence(asset_ids: List[str], project_id: Optional[str] = None,
                     transition: str = "fade", transition_duration: float = 0.5,
                     title: Optional[str] = None, name: str = "sequence",
                     width: Optional[int] = None, height: Optional[int] = None,
                     fps: float = 24.0) -> dict:
    """Auto-place multiple assets onto one timeline as a connected video.

    Lays the given ``asset_ids`` back-to-back in order, takes each clip's length
    from its media metadata, joins them with soft ``transition`` (default fade),
    and adds an optional ``title`` intro + a light cinematic grade. Creates (or
    updates ``project_id``) a project, links every source asset to it (keeping
    provenance), and returns the project — ready for render_project. width/height
    default to the first asset's resolution."""
    from . import assets as _assets, compose
    if not asset_ids:
        raise ValueError("compose_sequence: asset_ids is empty")
    recs = [_assets.get(a) for a in asset_ids]
    clips = [{"path": r["path"], "duration": (r.get("media") or {}).get("duration")}
             for r in recs]
    m0 = recs[0].get("media") or {}
    w = width or m0.get("width") or 1280
    h = height or m0.get("height") or 720
    spec = compose.build_sequence_spec(
        clips, width=int(w), height=int(h), fps=fps, transition=transition,
        transition_duration=transition_duration, title=title, name=name)
    pid = project_id or uuid.uuid4().hex[:12]
    _PROJECTS[pid] = spec
    for a in asset_ids:
        try:
            _assets.link_project(a, pid)
        except Exception:  # noqa: BLE001
            pass
    _log_activity_safe("compose", f"{len(asset_ids)}개 클립 시퀀스 구성",
                       asset_ids, [f"project:{pid}"])
    return {"ok": True, "project_id": pid, "clips": len(asset_ids),
            "duration": spec.get("duration"), "resolution": [int(w), int(h)]}


# --------------------------------------------------------------------------
# Operator dashboard (Studio): activity log + consolidated status
# --------------------------------------------------------------------------
def _log_activity_safe(action, summary, inputs=None, outputs=None, notes=""):
    """Append to the activity log without ever breaking the caller."""
    try:
        from .studio.guide import append_activity
        append_activity({"action": action, "summary": summary,
                         "inputs": inputs or [], "outputs": outputs or [],
                         "notes": notes})
    except Exception:  # noqa: BLE001
        pass


@mcp.tool()
def log_activity(action: str, summary: str, inputs: Optional[List[str]] = None,
                 outputs: Optional[List[str]] = None, notes: str = "") -> dict:
    """Record one pipeline step to the shared activity log shown on the Studio
    dashboard (the ② timeline). Call this after each meaningful step so a human
    can see what was done and the before -> after at a glance.

    action: short verb (e.g. 'generate', 'dewatermark', 'render', 'compose').
    summary: one-line description. inputs/outputs: file paths or short refs
    that form the before -> after. notes: optional extra context."""
    from .studio.guide import append_activity
    ev = append_activity({"action": action, "summary": summary,
                          "inputs": inputs or [], "outputs": outputs or [],
                          "notes": notes})
    return {"ok": True, "event": ev}


@mcp.tool()
def studio_status() -> dict:
    """Consolidated operator view (same data the Studio dashboard shows):
    high-level actions the pipeline can do, the prompt cookbook (incl. linking
    multiple media into one video), the engine primitives, and the activity
    timeline. Use this to answer 'what can I do / what was done / which prompts
    to use' in one shot."""
    from .studio.guide import dashboard_data
    return dashboard_data()


@mcp.tool()
def add_effect(project_id: str, effect: dict, track: Optional[str] = None,
               clip_index: Optional[int] = None) -> dict:
    """Attach an effect to a specific clip (track+clip_index) or, if both are
    omitted, to the timeline master chain (applied to the final frame).
    ``effect`` e.g. {"type":"glow","intensity":0.6} or
    {"type":"color_grade","contrast":1.1,"saturation":1.2}."""
    spec = _proj(project_id)
    if clip_index is None and track is None:
        spec["effects"].append(effect)
        _commit(project_id, spec)
        return {"ok": True, "scope": "master", "count": len(spec["effects"])}
    tr = _video_track(spec, track)
    if clip_index is None:
        clip_index = len(tr["clips"]) - 1
    tr["clips"][clip_index].setdefault("effects", []).append(effect)
    _commit(project_id, spec)
    return {"ok": True, "scope": "clip", "track": tr.get("name"), "clip_index": clip_index}


@mcp.tool()
def set_camera(project_id: str, pan: Optional[List] = None,
               zoom: Optional[object] = None, rotation: Optional[object] = None,
               focus: Optional[List[float]] = None) -> dict:
    """Set a keyframeable virtual camera over the whole composition.

    pan: [x,y] px offset (or a keyframed property). zoom: scale (1=neutral).
    rotation: degrees. focus: [x,y] focal point (default canvas center).
    Give clips a ``depth`` (1=foreground, 0=locked backdrop) for parallax.
    Enables push-ins, pans, dolly, whip-pans and dutch tilts."""
    spec = _proj(project_id)
    cam: Dict[str, Any] = {}
    if pan is not None:
        cam["pan"] = pan
    if zoom is not None:
        cam["zoom"] = zoom
    if rotation is not None:
        cam["rotation"] = rotation
    if focus is not None:
        cam["focus"] = focus
    spec["camera"] = cam
    _commit(project_id, spec)
    return {"ok": True, "camera": cam}


@mcp.tool()
def add_audio(project_id: str, path: str, start: float = 0.0,
              duration: Optional[float] = None, gain_db: float = 0.0,
              fade_in: float = 0.0, fade_out: float = 0.0,
              in_point: float = 0.0) -> dict:
    """Add an audio clip to the soundtrack (music, VO, SFX). Multiple audio
    clips are mixed. gain_db adjusts level; fade_in/out in seconds."""
    spec = _proj(project_id)
    track = None
    for tr in spec["tracks"]:
        if tr.get("kind") == "audio":
            track = tr
            break
    if track is None:
        track = {"kind": "audio", "name": "audio", "clips": []}
        spec["tracks"].append(track)
    track["clips"].append({"path": path, "start": start, "duration": duration,
                           "gain_db": gain_db, "fade_in": fade_in,
                           "fade_out": fade_out, "in_point": in_point})
    _commit(project_id, spec)
    return {"ok": True, "audio_clips": len(track["clips"])}


# --------------------------------------------------------------------------
# Inspection / serialization
# --------------------------------------------------------------------------
@mcp.tool()
def get_project(project_id: str) -> dict:
    """Return the full project spec (JSON-able) for inspection or editing."""
    return _proj(project_id)


@mcp.tool()
def update_project(project_id: str, spec: dict) -> dict:
    """Replace the stored spec for a project (e.g. after external editing)."""
    _PROJECTS[project_id] = spec
    return {"ok": True}


def _deep_merge(base: dict, patch: dict) -> dict:
    """Recursively merge ``patch`` into ``base`` (lists are replaced)."""
    for k, v in patch.items():
        if v is None:
            base.pop(k, None)
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _find_track(spec: dict, track: Optional[str], kind: str = "video") -> dict:
    for tr in spec["tracks"]:
        if tr.get("kind", "video") == kind and (track is None or tr.get("name") == track):
            return tr
    raise ValueError(f"Track {track!r} not found")


def _clip_summary(clip: dict, idx: int) -> dict:
    el = clip.get("element", {})
    preview = el.get("text") or el.get("path") or el.get("color") or el.get("type", "")
    return {"index": idx, "name": clip.get("name", ""), "type": el.get("type"),
            "start": clip.get("start"), "duration": clip.get("duration"),
            "preview": str(preview)[:48]}


@mcp.tool()
def list_clips(project_id: str) -> dict:
    """List every clip (with its track, index, type, timing and a content
    preview) so you can target one for editing. This is how you find the
    ``track`` + ``clip_index`` the edit tools take."""
    spec = _proj(project_id)
    out = []
    for tr in spec["tracks"]:
        clips = [_clip_summary(c, i) if tr.get("kind", "video") == "video"
                 else {"index": i, "type": "audio", "start": c.get("start"),
                       "preview": c.get("path", "")[:48]}
                 for i, c in enumerate(tr.get("clips", []))]
        out.append({"track": tr.get("name"), "kind": tr.get("kind", "video"),
                    "clips": clips})
    return {"tracks": out}


@mcp.tool()
def update_clip(project_id: str, track: str, clip_index: int, patch: dict) -> dict:
    """Edit ONE clip in place by deep-merging ``patch`` into it — change only
    what you pass, everything else is preserved. Examples:
      patch={"start": 4.0, "duration": 3.0}                  # retime
      patch={"transform": {"position": [800, 300]}}          # move
      patch={"element": {"text": "new text", "color": "#f00"}}  # edit content
      patch={"effects": [{"type": "glow", "intensity": 0.5}]} # replace effects
    Lists (e.g. effects) are replaced; nested dicts are merged. Pass a key with
    null to delete it."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    clips = tr.get("clips", [])
    if not -len(clips) <= clip_index < len(clips):
        raise ValueError(f"clip_index {clip_index} out of range (0..{len(clips)-1})")
    _deep_merge(clips[clip_index], patch)
    _commit(project_id, spec)
    return {"ok": True, "clip": clips[clip_index]}


@mcp.tool()
def remove_clip(project_id: str, track: str, clip_index: int) -> dict:
    """Delete one clip from a track. Other clips are untouched."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    removed = tr["clips"].pop(clip_index)
    _commit(project_id, spec)
    return {"ok": True, "removed": _clip_summary(removed, clip_index),
            "remaining": len(tr["clips"])}


@mcp.tool()
def move_clip(project_id: str, track: str, clip_index: int,
              start: Optional[float] = None, duration: Optional[float] = None,
              to_track: Optional[str] = None) -> dict:
    """Retime a clip (set start/duration) and/or move it to another video
    track, without altering its content."""
    spec = _proj(project_id)
    tr = _find_track(spec, track)
    clip = tr["clips"][clip_index]
    if start is not None:
        clip["start"] = start
    if duration is not None:
        clip["duration"] = duration
    if to_track is not None and to_track != track:
        tr["clips"].pop(clip_index)
        _find_track(spec, to_track)["clips"].append(clip)
    _commit(project_id, spec)
    return {"ok": True, "clip": _clip_summary(clip, clip_index)}


@mcp.tool()
def estimate(project_id: str) -> dict:
    """Report computed duration and frame count without rendering."""
    tl = Timeline.from_spec(_proj(project_id))
    return {"duration": tl.computed_duration(), "frames": tl.total_frames,
            "fps": tl.fps, "resolution": [tl.width, tl.height]}


@mcp.tool()
def preview_frame(project_id: str, time: float = 0.0,
                  out_path: Optional[str] = None) -> dict:
    """Render a single PNG frame at ``time`` seconds for quick visual review."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"preview_{project_id}_{int(time*1000)}.png")
    tl = Timeline.from_spec(_proj(project_id))
    render_thumbnail(tl, out_path, time)
    return {"ok": True, "path": out_path}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
@mcp.tool()
def render_project(project_id: str, out_path: Optional[str] = None,
                   crf: int = 18, preset: str = "medium") -> dict:
    """Render the project to an MP4 (H.264). Lower crf = higher quality/larger
    (18 is visually lossless-ish). preset trades speed for size
    (ultrafast..veryslow). Returns the output path and metadata."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"{project_id}.mp4")
    tl = Timeline.from_spec(_proj(project_id))
    t0 = time.time()
    res = render(tl, out_path, crf=crf, preset=preset)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "duration": res.duration, "resolution": [res.width, res.height],
            "fps": res.fps, "render_seconds": round(time.time() - t0, 2),
            "bytes": os.path.getsize(out_path)}


@mcp.tool()
def render_range(project_id: str, start: float, end: float,
                 out_path: Optional[str] = None, crf: int = 20,
                 preset: str = "veryfast") -> dict:
    """Render ONLY the time window [start, end] seconds — a fast preview of a
    section you just edited, so you don't re-render the whole video. (Video
    only; use render_project for the final with audio.)"""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(
        _OUTPUT_DIR, f"{project_id}_{int(start*1000)}-{int(end*1000)}.mp4")
    tl = Timeline.from_spec(_proj(project_id))
    t0 = time.time()
    res = render(tl, out_path, crf=crf, preset=preset, t_start=start, t_end=end)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "window": [start, end], "render_seconds": round(time.time() - t0, 2),
            "bytes": os.path.getsize(out_path)}


@mcp.tool()
def render_from_spec(spec: dict, out_path: Optional[str] = None,
                     crf: int = 18, preset: str = "medium") -> dict:
    """Render a complete project spec in one stateless call. ``spec`` is the
    same JSON structure returned by get_project. Best when the calling agent
    assembles the entire timeline itself."""
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    out_path = out_path or os.path.join(_OUTPUT_DIR, f"spec_{uuid.uuid4().hex[:8]}.mp4")
    tl = Timeline.from_spec(spec)
    res = render(tl, out_path, crf=crf, preset=preset)
    return {"ok": True, "path": res.path, "frames": res.frames,
            "duration": res.duration, "resolution": [res.width, res.height],
            "bytes": os.path.getsize(out_path)}


_HELP = """Dabwayo authoring guide
==========================
Coordinate system: pixels, origin top-left, +x right, +y down.
A project = tracks (composited bottom->top) of clips placed at absolute
times. Each clip has an element (the content), a transform, effects, and
optional in/out transitions.

Transform fields (any may be a keyframed property):
  position [x,y]  scale (n or [sx,sy])  rotation (deg)  opacity (0..1)
  anchor (center/top_left/.../bottom_right)
Keyframed property:
  {"keyframes":[{"time":0,"value":[0,540],"easing":"ease_out_cubic"},
                {"time":1.0,"value":[960,540]}]}

Typical flow:
  1. create_project(1920,1080,fps=30)
  2. add_background(..., gradient={...})
  3. add_text(..., transition_in={"type":"zoom","duration":0.6})
  4. add_effect(..., effect={"type":"glow"})  # clip or master
  5. add_audio(...) optional
  6. render_project(...)

Use get_capabilities() for the full list of element/effect/transition names.
"""


def main():
    """Run the MCP server.

    Default transport is stdio (local clients spawn this via .mcp.json).
    Set DABWAYO_MCP_TRANSPORT=http to expose it over Streamable HTTP so a
    *remote* client (e.g. a cloud session) can reach this host's open internet
    — bind/port come from FASTMCP_HOST / FASTMCP_PORT (default 127.0.0.1:8000;
    use 0.0.0.0 to listen on all interfaces). 'sse' is also accepted.
    """
    transport = os.environ.get("DABWAYO_MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
