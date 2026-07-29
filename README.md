# 다봐요 (Dabwayo)

A modular, scriptable **video rendering engine** with a first-class **MCP
interface** so AI agents can author and render high-quality video from plain
JSON. Think "a tiny, programmable motion-graphics compositor" — timelines,
tracks, clips, keyframed transforms, cinematic lighting, effects, transitions
and audio — all serializable and driven by tools.

```
                 ┌────────────────────────────────────────────┐
   agent ──MCP──▶│  dabwayo.mcp_server  (FastMCP, 45 tools) │
                 └───────────────┬────────────────────────────┘
                                 ▼
        Project (JSON spec) ─▶ Timeline ─▶ Render engine ─▶ H.264 MP4
                                 │
   elements · effects · transitions · lighting · keyframes · audio
```

## Why it's built this way
- **Declarative & serializable** — a project is a plain JSON `dict` (the
  *spec*). Agents can build it incrementally or hand over a whole timeline;
  it round-trips to disk and is trivially diff-able.
- **Modular registries** — elements, effects and transitions self-register,
  so adding a new capability is a single decorated class. Nothing else changes.
- **Quality first** — float RGBA compositing, anti-aliased affine placement,
  Lanczos scaling, alpha-correct blend modes, x264 CRF 18 output.
- **Self-contained** — bundled fonts and a static `ffmpeg` (via
  `imageio-ffmpeg`); no system installs required.

## Install
```bash
pip install -r requirements.txt      # numpy, Pillow, imageio[-ffmpeg], mcp
# or:  pip install -e .
```

> **Primary interface: the MCP tools.** Authoring, editing and rendering are
> driven through the MCP server (below) — that is where all editing logic
> lives, so agents, the Studio web and scripts share one implementation. The
> Python `Project` builder shown further down is the **low-level engine** those
> tools drive; reach for it only for advanced/embedded use.

## Run as an MCP server
```bash
python -m dabwayo.mcp_server          # stdio transport
# or the installed entry point:
dabwayo-mcp
```

Register it with any MCP client (e.g. Claude):
```json
{
  "mcpServers": {
    "dabwayo": { "command": "python", "args": ["-m", "dabwayo.mcp_server"] }
  }
}
```

### MCP tools
| Tool | Purpose |
|------|---------|
| `get_capabilities` / `get_help` | Discover element/effect/transition names + authoring guide |
| `create_project` | Start a project, returns `project_id` |
| `add_track` | Add a named video/audio track |
| `add_clip` | Add any element clip with transform/effects/transitions |
| `add_text` · `add_background` · `add_media` | Ergonomic clip helpers |
| `add_effect` | Attach an effect to a clip or the master chain |
| `add_audio` | Add a mixed audio clip (music/VO/SFX) |
| `add_callout` | Add a speech-bubble callout for explainer overlays |
| `set_camera` | Keyframeable pan/zoom/rotation (+ per-clip `depth` parallax) |
| `get_project` · `update_project` · `estimate` | Inspect / replace / measure |
| `list_clips` · `update_clip` · `remove_clip` · `move_clip` | Edit one clip in place — target by stable `clip_id` (survives reordering) or legacy `track`+`clip_index` |
| `split_clip` · `trim_clip` | Split a clip in two at a time, or trim its head/tail — media source stays frame-synced |
| `duplicate_clip` · `ripple_delete` | Copy a clip (new id), or delete + close the gap; `ripple` keeps later clips adjacent |
| `add_captions` · `add_word_captions` · `add_lower_third` | SRT/WebVTT subtitles, word-timed pop-on captions (Reels/Opus-Clip style), or a lower-third title |
| `list_asr_providers` · `transcribe` · `auto_captions` | Speech-to-text with word timestamps (pluggable, optional); transcribe + caption in one call |
| `list_tts_providers` · `synthesize_voice` · `add_voiceover` | Text-to-speech narration (pluggable: local/remote/OpenAI/ElevenLabs, optional); synth + add to the mix |
| `list_comments` · `add_comment` | Read/write timestamped review comments — the shared viewer's feedback, readable by the agent |
| `list_templates` · `get_template` · `create_from_template` · `batch_from_template` | Fill a `{{placeholder}}` template (text, colours **and media slots**) from data → one project, or one per data row for bulk branded video |
| `preview_frame` · `filmstrip` · `render_range` | One frame, N evenly-spaced frames (contact sheet / scrub cache), or a time window |
| `render_project` · `render_from_spec` | Render to MP4 (stateful or stateless) |
| `generate_video` · `list_video_providers` | Generate a clip from a prompt/image and drop it on the timeline |
| `add_shot` · `list_shots` · `update_shot` · `remove_shot` · `assemble_storyboard` | Hold a shot-list plan on a project and assemble it into a timeline (the *calling agent* plans; dabwayo assembles) |
| `create_reference` · `add_reference_variant` · `attach_reference_asset` · `bind_shot` · `resolve_shot` · `generate_shot` | Character/environment **bibles** (outfits/poses; time/lighting/mood/focus) bound to shots; `resolve_shot` composes the request, `generate_shot` runs it through the provider (ADR-0001) |
| `list_music_sources` · `search_music` · `fetch_music` | Pull royalty-free / CC music straight from provider APIs (Jamendo, Freesound) |

## Royalty-free music (`fetch_music`)
Score a clip without leaving the toolchain. `search_music` returns candidates
(title / artist / duration / licence / attribution) and `fetch_music`
downloads one into `DABWAYO_MUSIC_DIR` (default `assets/audio`) and registers
it as a tracked `music` asset, so it flows into compose / render / publish.

These call provider APIs **directly**, so run the server where it has open
internet (e.g. your VM), and set the relevant key:

```bash
export JAMENDO_CLIENT_ID=...     # https://devportal.jamendo.com  (primary: full tracks)
export FREESOUND_API_KEY=...     # https://freesound.org/apiv2/apply  (ambience / SFX layers)
```

```text
search_music("hopeful emotional piano", tags="piano,calm,cinematic", max_duration=90)
fetch_music("hopeful emotional piano", pick=0)     # downloads + registers the top hit
```

> Licences vary per track. Every result carries `license_url` and an
> `attribution` string — verify terms (attribution / commercial use) before
> publishing. Pixabay music is intentionally **not** wired up: it has no
> official music REST API, so programmatic use would mean scraping.

## Speech-to-text captions (`auto_captions`)
ASR is **pluggable and optional**, mirroring the video-gen providers. Configure
one and captions can be generated straight from audio; skip it and author
word-timed captions from your own list with `add_word_captions`.

| Provider | Needs | Notes |
|----------|-------|-------|
| `local` | `pip install faster-whisper` (or openai-whisper) | On-box, no network; model via `DABWAYO_ASR_MODEL` |
| `remote` | `DABWAYO_ASR_URL` | Your own Whisper HTTP server (`POST /transcribe` → words) |
| `openai` | `OPENAI_API_KEY` | Hosted Whisper with word timestamps |

Selection is automatic (`DABWAYO_ASR_URL` → remote; else an `OPENAI_API_KEY`;
else local if installed), or force it with `DABWAYO_ASR_PROVIDER` / `provider=`.
`auto_captions(project_id, audio_path)` transcribes and lays word-timed pop-on
captions in one call; `transcribe(audio_path)` returns `{text, language, words}`.

## Generative video (text→video / image→video)
`generate_video` turns a prompt (t2v) or a still image (i2v) into a short MP4
that composites onto the timeline like any other `video` clip — so AI footage
sits under your text, effects, camera moves and audio.

The backend is pluggable (`list_video_providers` shows what's ready):

| Provider | Needs | Notes |
|----------|-------|-------|
| `local` | nothing | Procedural fallback — abstract, **not** photoreal, but always works offline |
| `remote` | `DABWAYO_VIDEOGEN_URL` | A **Google Colab free-GPU** server (or any HTTP/GPU box) running LTX-Video |
| `replicate` | `REPLICATE_API_TOKEN` | Hosted open models, pay-per-use |
| `fal` | `FAL_KEY` | Hosted, pay-per-use |
| `huggingface` | `HF_TOKEN` | Free tier, t2v, modest quality |

Selection is automatic (`DABWAYO_VIDEOGEN_URL` → `remote`; else a hosted key;
else `local`), or force it with `DABWAYO_VIDEOGEN_PROVIDER` / `provider=`.

```python
from dabwayo import generate_video
shot = generate_video("a slow drone shot over a misty forest at dawn",
                      duration=4, out_path="output/shot.mp4")   # -> GenResult(path=...)
```

### Free photoreal via Google Colab
1. Open **`colab/dabwayo_gpu_server.ipynb`** in Colab, set Runtime → **GPU (T4)**, Run all.
2. It loads a video model and prints a public URL.
3. Point Dabwayo at it and generate real footage with the same tool:
```bash
export DABWAYO_VIDEOGEN_URL='https://xxxx.trycloudflare.com'
export DABWAYO_VIDEOGEN_PROVIDER=remote
```
The Colab server speaks a tiny contract (`GET /health`, `POST /generate` →
`video/mp4`), so any GPU box implementing it works as a drop-in backend.

**Free-T4 reality:** the wall is **system RAM (~12.7 GB)**, not VRAM — and a
RAM OOM during model load *kills the kernel* (uncatchable). So the notebook
**defaults to `MODEL='light'`** (Zeroscope, t2v) which loads reliably on the
free tier. `MODEL='ltx'` (photoreal **t2v+i2v**, fp16 + 8-bit text encoder +
sequential offload + VAE tiling) needs **Colab Pro / High-RAM**. For photoreal
**i2v on the free tier**, use a paid key instead (`FAL_KEY` /
`REPLICATE_API_TOKEN`) — the `fal` / `replicate` providers need no Colab.

### Editing only part of a project
Because the project is a JSON tree, you edit a single clip without touching
the rest. Find it with `list_clips`, then patch it — only the keys you pass
change (nested dicts merge, lists replace):
```python
update_clip(pid, track="callouts", clip_index=0,
            patch={"element": {"text": "new copy", "color": "#ff0"},
                   "start": 4.0})                       # retime + re-word one callout
render_range(pid, 3.5, 7.0)   # fast preview of just the edited section
```
The same applies in Python — a `Project` exposes its spec dict (`p.spec`),
and `Project.load(path)` / `p.save(path)` round-trip it for external edits.

## Studio UI + Claude Code (shared backend)
A human in a browser and an agent (Claude Code over MCP) can drive the **same
projects at the same time**. Both front-ends call the same operations and
share one on-disk store (`dabwayo.service.STORE`), so each sees the
other's edits.

```
  human ─▶ Studio web UI ─▶ HTTP ─┐
                                  ├─▶ same ops ─▶ shared JSON store (.vf_projects) ─▶ render
  Claude Code ─▶ MCP (stdio) ─────┘
```

```bash
# 1) start the Studio (serves UI + REST on :8080)
DABWAYO_STORE=.vf_projects python -m dabwayo.studio.server
# open http://localhost:8080
```
The repo ships a `.mcp.json` pointing Claude Code's `dabwayo` MCP server at
the **same** `DABWAYO_STORE`, so anything the agent creates/edits over MCP
shows up live in the UI (it polls every few seconds) and vice-versa. The UI
lets you create projects, add backgrounds/text/callouts/effects, scrub a
live preview frame, edit or delete a selected clip, edit the raw JSON spec,
and render — all backed by the exact MCP tools.

**Instant scrubbing.** The web prebuilds a filmstrip (`/api/projects/<id>/
filmstrip`, backed by the `filmstrip` tool) and shows the nearest cached frame
the moment you drag, fetching the exact frame only once the scrub settles — so
scrubbing feels instant instead of one server render per pointer move. The
cache refreshes in the background whenever the spec changes.

**Share a result (read-only viewer).** Every rendered/published asset has a
clean public player at **`/watch/<asset_id>`** — a responsive, read-only page
that resolves the asset and streams it from `/files`, showing title,
resolution/duration and any licence attribution. `publish_to_studio` /
`/api/upload` returns the `watch` path so you can hand an audience a link
without giving them the editor.

**Timestamped comments.** On the viewer, anyone can pin a note to the current
moment; clicking a comment's timecode seeks there. The agent reads that feedback
back with the `list_comments` tool and edits accordingly — a closed review loop
(audience comments → agent fixes) without the editor being exposed.

#### Use it from other agents (Copilot, opencode, Cline, …)
The MCP server is **provider-neutral** — any MCP client drives the same tools
on the same shared store. Drop-in config templates live in
[`examples/mcp-clients/`](examples/mcp-clients/): GitHub Copilot (VS Code agent
mode, `.vscode/mcp.json`), opencode (`opencode.json`), Cline/Cursor/Windsurf
(`mcpServers`). Point every client at the same `DABWAYO_STORE` and they
collaborate with the Studio UI and Claude Code on one project.

#### In-app AI editing (chat → edit → preview) — itself an MCP client
The Studio's chat panel is **not** a bespoke function-caller: it connects to
the Dabwayo MCP server as a client (exactly like the agents above),
discovers the tools via `list_tools`, and executes them via `call_tool`. The
LLM is only the brain that picks tools; the single source of truth is the MCP
server, so any tool added there appears in the chat automatically and edits go
through the same shared store. The LLM brain is pluggable:
```bash
# Claude
pip install '.[ai]'        && export ANTHROPIC_API_KEY=sk-ant-...
# or any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, opencode, …)
pip install '.[ai-openai]' && export OPENAI_API_KEY=...  \
    OPENAI_BASE_URL=https://api.openai.com/v1  DABWAYO_LLM_MODEL=gpt-4o
python -m dabwayo.studio.server     # chip shows the active provider/model
```
Provider is chosen by `DABWAYO_LLM_PROVIDER` (else auto-detected from the
key present). The chat tools are thin wrappers over the same MCP functions, so
the agent's edits interoperate with everything above. The UI also has **undo**
(↶) — edits and chat turns are snapshotted server-side.

## Low-level engine API (advanced)
The MCP tools above are the supported way to author. If you are embedding the
engine directly, the same JSON spec is reachable through the Python builder —
treat it as internal (import from `dabwayo.builder`, not as a stable public API):

```python
from dabwayo.builder import Project, keyframes as K

p = Project(1920, 1080, fps=30, background="#0b0e16")
title = p.track("video", "title")
(title.add(Project.text("Hello, agents.", size=120, font="display"), 0.3, 3.4)
      .scale(K((0.3, 1.1), (1.1, 1.0, "ease_out_cubic")))
      .effect("glow", intensity=0.4)
      .transition_in("fade", 0.5))
p.master_effect("color_grade", contrast=1.05, saturation=1.1)
p.render("output/hello.mp4")

# or render a complete spec directly:
import json
from dabwayo import Timeline, render
render(Timeline.from_spec(json.load(open("examples/quickstart_spec.json"))),
       "output/quickstart.mp4")
```

## The spec model
A `Timeline` owns ordered **tracks**; video tracks composite **bottom → top**.
Each **clip** places an **element** at an absolute `start`/`duration` and has:
- a **transform** — `position [x,y]`, `scale`, `rotation`, `opacity`, `anchor`
  (every field may be a **keyframed property** with per-keyframe easing);
- a **blend mode** (`normal, add, screen, multiply, overlay, soft_light, …`);
- a list of **effects**; and optional **in/out transitions**.

**Keyframed property**
```json
{"keyframes": [
  {"time": 0.0, "value": [0, 540], "easing": "ease_out_cubic"},
  {"time": 1.0, "value": [960, 540]}
]}
```

### Built-in capabilities
- **Elements**: `solid`, `gradient` (linear/radial), `text` (wrapping, shadow,
  stroke, letter-spacing), `image`, `video`, `shape` (rect/rounded/ellipse/line).
- **Effects**: `color_grade`, `lift_gamma_gain`, `blur`, `sharpen`, `glow`,
  `vignette`, `grain`, `chromatic_aberration`.
- **Lighting**: `light` (radial point light), `ambient`, `light_leak`.
- **Atmosphere / keying / censor**: `fog`, `chroma_key` (green-screen),
  `mask` (region/image matte), `mosaic` (region pixelation),
  `inpaint` (classical content-aware removal via OpenCV),
  `lama_inpaint` (deep ML removal via LaMa — optional, `pip install '.[ml]'`).
- **Transitions**: `fade`, `fade_color`, `slide`, `zoom`, `blur_in`, `wipe`.
- **Easings**: linear, quad/cubic/quart, expo, back, elastic, bounce, sine …

### Camera & parallax
A keyframeable virtual camera (`project.camera(pan=…, zoom=…, rotation=…)`)
applies to the whole composition — push-ins, pans, dolly, whip-pans, dutch
tilts. Give each clip a `depth` (`1`=foreground … `0`=locked backdrop) for
2.5D parallax. Region-targeted effects (mosaic/inpaint/mask) take a region
spec: `{"shape":"rect|ellipse|polygon", "rect":[x,y,w,h], "feather":px}`.

> **Removal backends.** `inpaint` is classical (OpenCV) — fast, great for
> small watermarks over fairly flat backgrounds. `lama_inpaint` is a deep
> LaMa model that hallucinates plausible texture, handling detailed/non-flat
> backgrounds far better; it runs only on a padded ROI around the mask so it
> stays fast even on CPU (`pip install '.[ml]'`). Both share the identical
> region interface, so you can swap backends per shot. Only remove watermarks
> from content you own.

## Layout
```
dabwayo/
  core/        types, color, easing, keyframes, transform, timeline
  elements/    backgrounds, text, media (image/video), shapes  (+registry)
  effects/     color grade, stylize (glow/blur/grain/…), lighting (+registry)
  transitions/ fade/slide/zoom/wipe/blur (+registry)
  render/      compositor (blend modes), rasterizer (affine), encoder, engine
  audio/       ffmpeg-based mixer
  builder.py   fluent Project API over the JSON spec
  mcp_server.py
assets/fonts/  bundled OFL fonts
examples/      generate_assets.py, demo_showcase.py, *_spec.json
tests/         test_engine.py
```

## Extending
Add an effect in ~10 lines — it auto-registers and is immediately available
to the builder, the JSON spec and the MCP tools:
```python
from dabwayo.effects.base import Effect, register

@register("invert")
class Invert(Effect):
    def apply(self, img, ctx, t):
        out = img.copy(); out[..., :3] = 1.0 - out[..., :3]; return out
```

## Demo
```bash
python examples/generate_assets.py     # procedural logo, texture, ambient audio
PYTHONPATH=. python examples/demo_showcase.py   # -> output/showcase.mp4
```
