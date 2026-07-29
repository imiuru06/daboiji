"""Creative reference tools: character & environment bibles (ADR-0001, phase 1).

The calling agent builds reusable references — characters (with outfit/pose/
expression variants) and environments (time/lighting/mood/focus variants), each
with reference-image assets — then binds storyboard shots to them.
``resolve_shot`` deterministically composes a shot's generation request (prompt
+ reference-image list) from those bindings; the actual generation/consistency
is the provider's job. No ML here."""
from __future__ import annotations

from typing import Optional

from .app import mcp, _proj, _commit

__all__ = ["create_reference", "list_references", "get_reference",
           "update_reference", "remove_reference", "add_reference_variant",
           "attach_reference_asset", "bind_shot", "resolve_shot", "generate_shot"]


@mcp.tool()
def create_reference(entity_type: str, name: str, description: str = "") -> dict:
    """Create a reusable creative reference. ``entity_type`` is 'character' or
    'environment'. Returns the record with its id (add variants + reference
    images next)."""
    from .. import reference as _ref
    return {"ok": True, "reference": _ref.create(entity_type, name, description)}


@mcp.tool()
def list_references(entity_type: str) -> dict:
    """List all characters or environments (id, name, #variants, #refs)."""
    from .. import reference as _ref
    items = _ref.list_all(entity_type)
    return {"ok": True, "count": len(items),
            "references": [{"id": r["id"], "name": r.get("name"),
                            "variants": len(r.get("variants", [])),
                            "base_refs": len(r.get("base_refs", []))} for r in items]}


@mcp.tool()
def get_reference(entity_type: str, reference_id: str) -> dict:
    """Return one character/environment's full record (variants + refs)."""
    from .. import reference as _ref
    return {"ok": True, "reference": _ref.get(entity_type, reference_id)}


@mcp.tool()
def update_reference(entity_type: str, reference_id: str, patch: dict) -> dict:
    """Edit an entity's top-level fields (name/description). Variants and refs
    have their own tools; id/kind are immutable."""
    from .. import reference as _ref
    return {"ok": True, "reference": _ref.update(entity_type, reference_id, patch)}


@mcp.tool()
def remove_reference(entity_type: str, reference_id: str) -> dict:
    """Delete a character/environment from the library."""
    from .. import reference as _ref
    return {"ok": _ref.remove(entity_type, reference_id)}


@mcp.tool()
def add_reference_variant(entity_type: str, reference_id: str, label: str,
                          prompt_fragment: str = "", attributes: Optional[dict] = None,
                          refs: Optional[list] = None) -> dict:
    """Add a variant to a character/environment. ``prompt_fragment`` is text that
    describes this variant for generation. ``attributes`` carries kind-specific
    fields — character e.g. {"kind":"outfit"}; environment e.g.
    {"time_of_day":"dawn","lighting":"cool low sun","mood":"quiet","focus":"shallow"}.
    ``refs`` are reference-image asset ids for this variant."""
    from .. import reference as _ref
    v = _ref.add_variant(entity_type, reference_id, label,
                         prompt_fragment=prompt_fragment, refs=refs, attributes=attributes)
    return {"ok": True, "variant": v}


@mcp.tool()
def attach_reference_asset(entity_type: str, reference_id: str, asset_id: str,
                           variant_id: Optional[str] = None) -> dict:
    """Link a reference-image asset (register it first) to a character/
    environment's base_refs, or to a specific variant when ``variant_id`` is set."""
    from .. import reference as _ref
    rec = _ref.attach_ref(entity_type, reference_id, asset_id, variant_id)
    return {"ok": True, "reference": rec}


@mcp.tool()
def bind_shot(project_id: str, shot_id: str, character_id: Optional[str] = None,
              character_variants: Optional[list] = None,
              environment_id: Optional[str] = None,
              environment_variant: Optional[str] = None,
              camera: Optional[dict] = None) -> dict:
    """Bind a storyboard shot to references: which ``character_id`` (and which
    ``character_variants`` — a list of variant ids, e.g. an outfit + a pose) in
    which ``environment_id`` (``environment_variant``), plus a ``camera`` dict
    (e.g. {"angle":"medium front","focus":"shallow"}). These bindings drive
    resolve_shot. Pass only what you want to set."""
    spec = _proj(project_id)
    shot = next((s for s in spec.get("storyboard", []) if s.get("id") == shot_id), None)
    if shot is None:
        raise ValueError(f"shot_id {shot_id!r} not found (add_shot first)")
    if character_id is not None:
        shot["character"] = {"id": character_id, "variant": character_variants or []}
    if environment_id is not None:
        shot["environment"] = {"id": environment_id, "variant": environment_variant}
    if camera is not None:
        shot["camera"] = camera
    _commit(project_id, spec)
    return {"ok": True, "shot": shot}


@mcp.tool()
def resolve_shot(project_id: str, shot_id: str) -> dict:
    """Deterministically compose a bound shot's generation request from its
    references — NO generation, NO ML. Returns the composed ``prompt`` and the
    ordered ``reference_images`` (asset ids: character base + variant refs +
    environment base) plus ``mode``. Hand this to generate_video (or your
    provider) to actually produce the shot. This is the bridge from the
    reference model to generation."""
    from .. import reference as _ref
    spec = _proj(project_id)
    shot = next((s for s in spec.get("storyboard", []) if s.get("id") == shot_id), None)
    if shot is None:
        raise ValueError(f"shot_id {shot_id!r} not found")
    parts, refs = [], []
    cb = shot.get("character")
    if cb and cb.get("id"):
        c = _ref.get("character", cb["id"])
        if c.get("description"):
            parts.append(c["description"])
        refs += list(c.get("base_refs", []))
        vids = cb.get("variant") or []
        vids = vids if isinstance(vids, list) else [vids]
        for v in c.get("variants", []):
            if v.get("id") in vids:
                if v.get("prompt_fragment"):
                    parts.append(v["prompt_fragment"])
                refs += list(v.get("refs", []))
    eb = shot.get("environment")
    if eb and eb.get("id"):
        e = _ref.get("environment", eb["id"])
        if e.get("description"):
            parts.append(e["description"])
        refs += list(e.get("base_refs", []))
        for v in e.get("variants", []):
            if v.get("id") == eb.get("variant"):
                bits = [v.get("prompt_fragment")] + [
                    f"{k}: {v[k]}" for k in ("time_of_day", "lighting", "mood", "focus") if v.get(k)]
                parts += [b for b in bits if b]
                refs += list(v.get("refs", []))
    cam = shot.get("camera") or {}
    if cam:
        parts.append(", ".join(f"{k} {v}" for k, v in cam.items()))
    if shot.get("prompt"):
        parts.append(shot["prompt"])
    return {"ok": True, "shot_id": shot_id,
            "prompt": ", ".join(p for p in parts if p),
            "reference_images": refs,
            "mode": shot.get("mode", "t2v"),
            "duration": shot.get("duration")}


@mcp.tool()
def generate_shot(project_id: str, shot_id: str, provider: Optional[str] = None,
                  add_to_timeline: bool = False, start: float = 0.0,
                  track: str = "video") -> dict:
    """Resolve a bound shot and generate its clip through the active video
    provider, binding the result back onto the shot (``shot.media``).

    Reference-aware: it composes the prompt via resolve_shot and, for i2v, uses
    the first resolvable reference image as the ``image`` input (the provider —
    not dabwayo — does the actual character/style consistency; multi-image
    conditioning depends on the provider). The generated clip is registered as
    an asset. This is the bridge from the reference/storyboard model to real
    footage (ADR-0001 phase 2). Returns the media path + provider + the prompt
    used."""
    r = resolve_shot(project_id, shot_id)
    prompt, mode = r["prompt"], r["mode"]
    dur = r.get("duration") or 4.0
    image = None
    if mode == "i2v" and r["reference_images"]:
        from .. import assets as _assets
        for aid in r["reference_images"]:
            try:
                image = _assets.get(aid).get("path")
                if image:
                    break
            except Exception:  # noqa: BLE001  (unregistered ref id — skip)
                continue
    from .generation import generate_video as _gv
    res = _gv(project_id, prompt, mode=mode, image=image, duration=dur,
              provider=provider, add_to_timeline=add_to_timeline,
              start=start, track=track)
    spec = _proj(project_id)
    shot = next((s for s in spec.get("storyboard", []) if s.get("id") == shot_id), None)
    if shot is not None and res.get("path"):
        shot["media"] = res["path"]
        _commit(project_id, spec)
    return {"ok": True, "shot_id": shot_id, "path": res.get("path"),
            "asset_id": res.get("asset_id"), "provider": res.get("provider"),
            "prompt": prompt, "mode": mode, "used_image": image}
