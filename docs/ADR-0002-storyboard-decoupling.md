# ADR-0002 — Decouple the storyboard from render projects

**Status:** accepted — full decoupling signed off. Phase 1 (storyboard store
entity + scenes + shots with multi-cast/environment/props bindings + resolve +
assemble-into-project, plus a `prop` reference kind) shipped. UI + deeper
prop-bible generation pending.

## Problem
ADR-0001 gave first-class, reusable **character** and **environment** bibles.
But the **storyboard** lived inside a render project's spec (`spec["storyboard"]`,
one flat shot list per project). That bundled the *creative plan* with the
*assembled timeline* and had real limits:

1. Not reusable/shareable/versionable — locked to one project, one per project.
2. A shot bound a **single** character — no multi-character (dialogue) shots.
3. No **props/objects** bible (only character + environment).
4. No **scene/sequence** grouping — a flat shot list.
5. Loosely-typed variants; no per-project cast list.

## Decision
Promote the storyboard to a **first-class store entity**, decoupled from render
projects — the plan is authored once and *assembled* into any number of render
projects (the output). Scope unchanged: dabwayo owns the structured model +
index + deterministic resolution; bytes and ML stay external.

```jsonc
// <STORE>/storyboards/<id>.json  — reusable across projects
{
  "id": "sb_ab12", "name": "Ep1", "width": 1920, "height": 1080, "fps": 24,
  "scenes": [ { "id": "sc_1", "name": "opening", "shots": [
    { "id": "shot_x", "prompt": "they talk over coffee", "duration": 4, "mode": "t2v",
      "cast": [ {"character_id":"char_a","variant":["v_out1"]},
                {"character_id":"char_b"} ],          // MULTIPLE characters
      "environment": {"id":"env_c","variant":"v_dawn"},
      "props": [ {"prop_id":"prop_cup"} ],            // props bible (new kind)
      "camera": {"angle":"two-shot"}, "media": null } ] } ]
}
```

- **Reusable**: `assemble_storyboard_project(storyboard_id)` builds a render
  project from the plan; the storyboard stays in the store for reuse/versioning.
- **Multi-cast**: a shot's `cast` is a list of characters (+ per-member variants).
- **Props**: a third reference kind (`prop`) reuses the ADR-0001 bible model.
- **Scenes**: shots are grouped into named scenes.
- `resolve_storyboard_shot` composes prompt + reference images from ALL bindings
  (every cast member, environment, props, camera, action) — deterministic, no ML.

Backward compatible: the old per-project storyboard tools (`add_shot`,
`assemble_storyboard`, `bind_shot`, …) keep working unchanged.

## Phasing
1. **Store entity + CRUD + scenes + shots (multi-cast/env/props) + resolve +
   assemble-into-project + `prop` kind.** ✅ shipped
2. Prop-bible generation (`generate_prop_sheet`), cast list (`storyboard_cast`),
   scene + shot reordering (`move_scene`, `move_storyboard_shot`). ✅ shipped
3. Studio UI for the storyboard library — `/board`: storyboard list, scenes
   board, per-shot multi-cast + environment pickers, live `resolve`, cast/
   locations/props breakdown, and assemble-to-project. ✅ shipped. ADR complete.

## Scope check
All of this is structured plan/state the calling agent authors and dabwayo
resolves deterministically — squarely inside dabwayo's tool-layer role. No LLM
planner, no full DAM. Consistent with ADR-0001.
