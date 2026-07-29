# ADR-0001 — Creative asset & reference-sheet architecture

**Status:** accepted — dabwayo owns model + index + resolution (bytes & ML
delegated). Phase 1 (reference model + CRUD + shot binding + `resolve_shot`)
shipped; phases 2–4 pending.
**Context:** Beyond raw media files, dabwayo needs to manage *structured creative
references* for consistent AI video: **character sheets** (with outfits, poses,
expressions, multi-angle views), **environment/background sheets** (time of day,
lighting, mood, focus), and how these compose into **storyboard shots**. The
question: how much of this does dabwayo own vs delegate?

## Guiding principle (from the project's definition)
dabwayo is the **tool layer other agents drive over MCP**. Intelligence
(creative choices, ML) lives *outside*; dabwayo does **deterministic glue** that
is tightly coupled to editing/render. Every concern is sorted by which of these
it is:

- **(S) structured state** the agent authors + dabwayo resolves deterministically
- **(B) bytes** — actual files
- **(M) ML / creative intelligence** — running models, making creative decisions
- **(U) UI** — human-facing display/editing

## The verdict, per concern

| Concern | Type | Home | Why |
|---|---|---|---|
| Character / environment **bible** (entities + variants + attributes) | **S** | ✅ **dabwayo owns** | Same shape as the storyboard "plan as state" already built; referenced by shots; serializable; deterministic to resolve |
| **Reference images** for each sheet/variant (bytes) | **B** | ⚠️ **index in dabwayo, bytes delegated** | Asset registry keeps the *pointer* + provenance; a pluggable storage backend keeps the *bytes* (never a full DAM) |
| **Consistency generation** (keep a face/outfit stable across angles/shots) | **M** | ✅ **provider (external)** | This is a *model* capability (i2v + reference / IP-adapter / model-native). dabwayo passes references through and collects outputs; it does not do the ML |
| **Composing** a shot's request from character+env+camera | **S** | ✅ **dabwayo owns** | Deterministic: pick variants → build prompt + reference-image list for the provider |
| **Editing / displaying** sheets | **U** | ✅ **dabwayo (Studio), incremental** | MCP CRUD tools now; Studio panels later. Real product surface |

**One-line rule:** dabwayo owns the **reference *model* + *index* + deterministic
*resolution*+ *assembly***; it delegates **bytes** (pluggable storage) and the
**ML consistency/generation** (providers). No autonomous creative planning, no
full DAM.

## Proposed data model

A shared **library** in the store (reused across projects — a real "bible"):

```jsonc
// <STORE>/characters/<id>.json
{
  "id": "char_ab12", "name": "Mina", "description": "late-20s, dark bob, calm",
  "base_refs": ["ast_...", "ast_..."],        // canonical multi-angle identity refs
  "variants": [
    { "id": "v_out1", "kind": "outfit",     "label": "grey knit",
      "prompt_fragment": "in an oversized grey knit sweater", "refs": ["ast_..."] },
    { "id": "v_pose1", "kind": "pose",       "label": "walking",
      "prompt_fragment": "walking, mid-stride", "refs": [] },
    { "id": "v_exp1",  "kind": "expression", "label": "hopeful smile",
      "prompt_fragment": "a soft, hopeful smile", "refs": [] }
  ]
}

// <STORE>/environments/<id>.json
{
  "id": "env_c3", "name": "City apartment", "description": "high-rise, big windows",
  "base_refs": ["ast_..."],
  "variants": [
    { "id": "v_dawn", "label": "dawn", "time_of_day": "dawn",
      "lighting": "cool low sun", "mood": "quiet", "focus": "shallow",
      "prompt_fragment": "at dawn, cool light through tall windows", "refs": [] }
  ]
}
```

A **shot** (extends the storyboard shot already implemented) *binds* references:

```jsonc
{
  "id": "shot_...", "duration": 4, "mode": "i2v",
  "character": { "id": "char_ab12", "variant": ["v_out1", "v_pose1", "v_exp1"] },
  "environment": { "id": "env_c3", "variant": "v_dawn" },
  "camera": { "angle": "medium front", "focus": "shallow" },
  "prompt": "she pauses and looks toward the light",   // shot-specific action
  "media": null                                          // filled after generation
}
```

**Deterministic resolution** (dabwayo, no ML): compose the final generation
request —
`prompt = character.description + Σ variant.prompt_fragment + environment(+variant) + camera + shot.prompt`,
`reference_images = character.base_refs + variant.refs + environment.base_refs`.
That request goes to the **provider** (which does the actual consistency), and
the returned clip is registered + bound back onto the shot.

## What stays external
- **Bytes**: a `StorageProvider` (local / vm / s3 / gcs) — see the pending
  storage-abstraction refactor. Assets carry `{uri, backend}`, not a hard path.
- **ML**: character consistency, generation — the video/image providers.
- **Creative planning**: which character wears what in which shot — the calling
  agent decides; dabwayo only records + resolves.

## Phasing (proposed)
1. **Reference model + CRUD tools** — characters/environments/variants in the
   store; MCP tools to create/edit/attach refs; bind shots to references.
2. **Resolution + assembly** — compose prompt + reference list per shot; feed the
   provider; register/bind outputs. (Builds on `assemble_storyboard`.)
3. **Storage abstraction** — decouple the asset registry from local paths.
4. **Studio UI** — sheet panels (character/environment/storyboard) to view/edit.

## Decision needed
Confirm dabwayo should own layers **S + index + resolution** (this ADR), with
bytes and ML delegated — i.e. dabwayo grows from "compositor" into a
**structured creative-reference production tool**, still driven by external
agents. Then pick the first phase.
