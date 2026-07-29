"""Dabwayo Studio server.

A small, dependency-free HTTP server that serves the Studio web UI and a REST
API. The API is a thin wrapper over the *same* functions the MCP server
exposes (``dabwayo.mcp_server``), and both share the on-disk project store
(``dabwayo.service.STORE``). So a human in the browser and an agent such as
Claude Code (over MCP) edit the same projects and see each other's changes.

Run:  python -m dabwayo.studio.server   [--port 8080]
Point Claude Code's MCP server at the same DABWAYO_STORE to collaborate.
"""
from __future__ import annotations

import base64
import json
import os
import re
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import capabilities as engine_capabilities
from .. import mcp_server as M
from ..service import OUTPUT_DIR, STORE
from . import guide

HERE = os.path.dirname(os.path.abspath(__file__))

# Per-project undo stack of prior spec states (capped). Studio-only, in-memory.
_UNDO: dict = {}
_UNDO_MAX = 25


def _snapshot(pid: str) -> None:
    if pid in STORE:
        stack = _UNDO.setdefault(pid, [])
        stack.append(json.dumps(STORE[pid]))
        del stack[:-_UNDO_MAX]


def _undo(pid: str) -> bool:
    stack = _UNDO.get(pid)
    if not stack:
        return False
    STORE[pid] = json.loads(stack.pop())
    return True


# (method, regex) -> handler(handler, match, body) returning (status, obj_or_bytes, ctype)
ROUTES = []


def route(method, pattern):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


@route("GET", r"/api/capabilities")
def _caps(h, m, body):
    return 200, engine_capabilities(), None


# -- Operator dashboard: actions, activity timeline, prompt cookbook --------
@route("GET", r"/api/dashboard")
def _dashboard(h, m, body):
    return 200, guide.dashboard_data(), None


@route("GET", r"/api/activity")
def _activity_get(h, m, body):
    return 200, {"activity": guide.read_activity()}, None


@route("POST", r"/api/activity")
def _activity_post(h, m, body):
    return 200, guide.append_activity(body), None


# -- Asset registry / store manifest (see STORE.md) -------------------------
@route("GET", r"/api/index")
def _store_index(h, m, body):
    from .. import assets
    return 200, assets.build_index(), None


@route("GET", r"/api/assets")
def _assets_list(h, m, body):
    from .. import assets
    return 200, {"assets": assets.list_assets()}, None


@route("GET", r"/api/assets/(ast_[0-9a-f]+)")
def _asset_get(h, m, body):
    from .. import assets
    rec = assets.get(m.group(1))
    return 200, {**rec, "lineage": [a["id"] for a in assets.lineage(m.group(1))]}, None


# -- Timestamped review comments (shared viewer <-> agent) ------------------
@route("GET", r"/api/assets/(ast_[0-9a-f]+)/comments")
def _comments_get(h, m, body):
    from .. import comments
    return 200, {"comments": comments.list_comments(m.group(1))}, None


@route("POST", r"/api/assets/(ast_[0-9a-f]+)/comments")
def _comments_post(h, m, body):
    from .. import comments
    rec = comments.add_comment(m.group(1), body.get("t", 0),
                               body.get("text", ""), body.get("author", ""))
    return 200, {"ok": True, "comment": rec}, None


# -- Creative reference bibles (character / environment) + storyboard --------
@route("GET", r"/api/references/(character|environment)")
def _refs_list(h, m, body):
    return 200, M.list_references(m.group(1)), None


@route("POST", r"/api/references/(character|environment)")
def _refs_create(h, m, body):
    return 200, M.create_reference(m.group(1), body.get("name", "Untitled"),
                                   body.get("description", "")), None


@route("GET", r"/api/references/(character|environment)/([A-Za-z0-9_]+)")
def _refs_get(h, m, body):
    return 200, M.get_reference(m.group(1), m.group(2)), None


@route("POST", r"/api/references/(character|environment)/([A-Za-z0-9_]+)/variant")
def _refs_add_variant(h, m, body):
    return 200, M.add_reference_variant(
        m.group(1), m.group(2), body.get("label", "variant"),
        prompt_fragment=body.get("prompt_fragment", ""),
        attributes=body.get("attributes"), refs=body.get("refs")), None


@route("GET", r"/api/projects/([0-9a-f]+)/storyboard")
def _sb_list(h, m, body):
    return 200, M.list_shots(m.group(1)), None


@route("POST", r"/api/projects/([0-9a-f]+)/storyboard")
def _sb_add(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_shot(m.group(1), prompt=body.get("prompt", ""),
                           duration=body.get("duration", 4),
                           mode=body.get("mode", "t2v"),
                           caption=body.get("caption", "")), None


@route("GET", r"/api/projects/([0-9a-f]+)/storyboard/([A-Za-z0-9_]+)/resolve")
def _sb_resolve(h, m, body):
    return 200, M.resolve_shot(m.group(1), m.group(2)), None


@route("POST", r"/api/references/(character|environment)/([A-Za-z0-9_]+)/attach")
def _refs_attach(h, m, body):
    return 200, M.attach_reference_asset(m.group(1), m.group(2), body["asset_id"],
                                         variant_id=body.get("variant_id")), None


@route("POST", r"/api/references/character/([A-Za-z0-9_]+)/sheet")
def _char_sheet(h, m, body):
    return 200, M.generate_character_sheet(m.group(1), angles=body.get("angles"),
                                           provider=body.get("provider")), None


@route("POST", r"/api/projects/([0-9a-f]+)/storyboard/([A-Za-z0-9_]+)/bind")
def _sb_bind(h, m, body):
    _snapshot(m.group(1))
    return 200, M.bind_shot(m.group(1), m.group(2),
                            character_id=body.get("character_id"),
                            character_variants=body.get("character_variants"),
                            environment_id=body.get("environment_id"),
                            environment_variant=body.get("environment_variant"),
                            camera=body.get("camera")), None


@route("GET", r"/api/assets/(ast_[0-9a-f]+)/file")
def _asset_file(h, m, body):
    """Serve an asset's bytes by id (backend-aware) so the UI can show thumbnails
    regardless of where the file lives."""
    from ..storage import localize_asset
    fp = localize_asset(m.group(1))
    if not os.path.isfile(fp):
        return 404, {"error": "no bytes"}, None
    ext = os.path.splitext(fp)[1].lower()
    ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp", ".mp4": "video/mp4",
             ".mp3": "audio/mpeg", ".wav": "audio/wav"}.get(ext, "application/octet-stream")
    with open(fp, "rb") as f:
        return 200, f.read(), ctype


@route("POST", r"/api/upload")
def _upload(h, m, body):
    """Durable publish: an off-box agent uploads a media file (base64) which is
    saved to OUTPUT_DIR and registered as an asset (with provenance). This is
    how work survives an ephemeral Claude Code sandbox — it lands on the VM."""
    from .. import assets
    key = os.environ.get("DABWAYO_STUDIO_KEY", "")
    if key:                                     # optional bearer auth
        auth = h.headers.get("Authorization", "")
        if auth != f"Bearer {key}":
            return 401, {"error": "unauthorized"}, None
    if not body.get("b64"):
        return 400, {"error": "missing b64 payload"}, None
    try:
        data = base64.b64decode(body["b64"])
    except Exception:  # noqa: BLE001
        return 400, {"error": "invalid base64"}, None
    raw = os.path.basename(body.get("filename") or "upload.bin")
    safe = f"{uuid.uuid4().hex[:8]}_{raw}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dest = os.path.join(OUTPUT_DIR, safe)
    with open(dest, "wb") as f:
        f.write(data)
    src = {"action": body.get("action", "upload"),
           "provider": body.get("provider", ""), "prompt": body.get("prompt", "")}
    if body.get("parent"):
        src["parent"] = body["parent"]
    rec = assets.register(dest, kind=body.get("kind", "video"),
                          role=body.get("role", "upload"), source=src,
                          projects=[body["project"]] if body.get("project") else [],
                          tags=body.get("tags") or [])
    guide.append_activity({"action": "publish", "summary": f"VM에 업로드: {raw}",
                           "inputs": [body.get("parent") or raw],
                           "outputs": [rec["id"]], "notes": f"{len(data)} bytes"})
    return 200, {"ok": True, "asset": rec, "url": "/files/" + safe,
                 "watch": "/watch/" + rec["id"], "bytes": len(data)}, None


@route("GET", r"/api/projects")
def _list(h, m, body):
    out = []
    for pid in STORE.ids():
        if pid.startswith("_"):
            continue
        try:
            spec = STORE[pid]
            out.append({"id": pid, "name": spec.get("name", pid),
                        "resolution": [spec.get("width"), spec.get("height")]})
        except Exception:
            pass
    return 200, {"projects": out}, None


@route("POST", r"/api/projects")
def _create(h, m, body):
    r = M.create_project(width=body.get("width", 1280), height=body.get("height", 720),
                         fps=body.get("fps", 24), background=body.get("background", "#0b0e16"),
                         name=body.get("name", "untitled"), duration=body.get("duration"))
    return 200, r, None


@route("GET", r"/api/projects/([0-9a-f]+)")
def _get(h, m, body):
    return 200, M.get_project(m.group(1)), None


@route("PUT", r"/api/projects/([0-9a-f]+)")
def _put(h, m, body):
    _snapshot(m.group(1))
    return 200, M.update_project(m.group(1), body["spec"]), None


@route("POST", r"/api/projects/([0-9a-f]+)/rename")
def _rename_project(h, m, body):
    pid = m.group(1)
    spec = STORE[pid]
    spec["name"] = (body.get("name") or spec.get("name") or "untitled").strip()
    STORE[pid] = spec
    return 200, {"ok": True, "name": spec["name"]}, None


@route("POST", r"/api/projects/([0-9a-f]+)/duplicate")
def _duplicate_project(h, m, body):
    spec = json.loads(json.dumps(STORE[m.group(1)]))   # deep copy
    spec["name"] = (spec.get("name") or "untitled") + " 사본"
    new_pid = uuid.uuid4().hex[:12]
    STORE[new_pid] = spec
    return 200, {"ok": True, "project_id": new_pid, "spec": spec}, None


@route("DELETE", r"/api/projects/([0-9a-f]+)")
def _delete_project(h, m, body):
    pid = m.group(1)
    STORE.delete(pid)
    _UNDO.pop(pid, None)
    return 200, {"ok": True}, None


@route("POST", r"/api/projects/([0-9a-f]+)/undo")
def _undo_route(h, m, body):
    ok = _undo(m.group(1))
    return 200, {"ok": ok, "remaining": len(_UNDO.get(m.group(1), []))}, None


@route("GET", r"/api/projects/([0-9a-f]+)/clips")
def _clips(h, m, body):
    return 200, M.list_clips(m.group(1)), None


@route("POST", r"/api/projects/([0-9a-f]+)/text")
def _text(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_text(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/background")
def _bg(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_background(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/callout")
def _callout(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_callout(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/media")
def _media(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_media(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/effect")
def _effect(h, m, body):
    _snapshot(m.group(1))
    return 200, M.add_effect(m.group(1), effect=body["effect"],
                             track=body.get("track"), clip_index=body.get("clip_index")), None


@route("POST", r"/api/projects/([0-9a-f]+)/camera")
def _camera(h, m, body):
    _snapshot(m.group(1))
    return 200, M.set_camera(m.group(1), **body), None


@route("PATCH", r"/api/projects/([0-9a-f]+)/clips/([^/]+)/(-?\d+)")
def _update_clip(h, m, body):
    _snapshot(m.group(1))
    return 200, M.update_clip(m.group(1), m.group(2), int(m.group(3)), body["patch"]), None


@route("DELETE", r"/api/projects/([0-9a-f]+)/clips/([^/]+)/(-?\d+)")
def _remove_clip(h, m, body):
    _snapshot(m.group(1))
    return 200, M.remove_clip(m.group(1), m.group(2), int(m.group(3))), None


@route("GET", r"/api/projects/([0-9a-f]+)/preview")
def _preview(h, m, body):
    q = parse_qs(urlparse(h.path).query)
    t = float(q.get("t", [0])[0])
    out = os.path.join(OUTPUT_DIR, f"_preview_{m.group(1)}.png")
    M.preview_frame(m.group(1), time=t, out_path=out)
    with open(out, "rb") as f:
        return 200, f.read(), "image/png"


@route("GET", r"/api/projects/([0-9a-f]+)/filmstrip")
def _filmstrip(h, m, body):
    """Prebuilt evenly-spaced frames so the web can scrub instantly from cache
    instead of rendering one frame per pointer move."""
    q = parse_qs(urlparse(h.path).query)
    count = int(q.get("count", [12])[0])
    r = M.filmstrip(m.group(1), count=count)
    r["frames"] = [{"t": f["t"], "url": "/files/" + os.path.basename(f["path"])}
                   for f in r["frames"]]
    return 200, r, None


@route("GET", r"/api/chat/status")
def _chat_status(h, m, body):
    from . import chat
    return 200, chat.status(), None


@route("POST", r"/api/projects/([0-9a-f]+)/chat")
def _chat(h, m, body):
    from . import chat
    st = chat.status()
    if not st.get("available"):
        return 200, {"available": False, "reply":
                     "AI 채팅을 켜려면 LLM 프로바이더를 설정하세요. " + st.get("hint", "")}, None
    pid = m.group(1)
    _snapshot(pid)                       # enable undo of the agent's edits
    result = chat.run_chat(pid, body["message"])
    result["available"] = True
    return 200, result, None


@route("POST", r"/api/projects/([0-9a-f]+)/render")
def _render(h, m, body):
    r = M.render_project(m.group(1), crf=body.get("crf", 20), preset=body.get("preset", "veryfast"))
    r["url"] = "/files/" + os.path.basename(r["path"])
    return 200, r, None


@route("POST", r"/api/projects/([0-9a-f]+)/render_range")
def _render_range(h, m, body):
    r = M.render_range(m.group(1), body["start"], body["end"])
    r["url"] = "/files/" + os.path.basename(r["path"])
    return 200, r, None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, payload, ctype=None):
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        elif isinstance(payload, bytes):
            data = payload
            ctype = ctype or "application/octet-stream"
        else:
            data = str(payload).encode("utf-8")
            ctype = ctype or "text/plain; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"")

    def _serve_static(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/dashboard", "/dashboard.html"):
            with open(os.path.join(HERE, "dashboard.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/gallery", "/gallery.html"):
            with open(os.path.join(HERE, "gallery.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/watch" or path.startswith("/watch/"):
            # read-only public player; the page resolves the asset id (path tail
            # or ?v=) client-side against /api/assets + /files.
            with open(os.path.join(HERE, "viewer.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/sheets", "/sheets.html"):
            with open(os.path.join(HERE, "sheets.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path.startswith("/files/"):
            name = os.path.basename(path[len("/files/"):])
            fp = os.path.join(OUTPUT_DIR, name)
            if os.path.isfile(fp):
                ctype = ("video/mp4" if name.endswith(".mp4")
                         else "image/png" if name.endswith(".png") else "application/octet-stream")
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), ctype)
        if path.endswith((".css", ".js")):       # static UI assets next to the HTML
            fp = os.path.join(HERE, os.path.basename(path))
            if os.path.isfile(fp):
                ctype = "text/css" if path.endswith(".css") else "application/javascript"
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), ctype + "; charset=utf-8")
        return self._send(404, {"error": "not found"})

    def _dispatch(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._serve_static()
        body = {}
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
        for method, rx, fn in ROUTES:
            if method != self.command:
                continue
            mt = rx.match(path)
            if mt:
                try:
                    status, payload, ctype = fn(self, mt, body)
                    return self._send(status, payload, ctype)
                except (KeyError, FileNotFoundError) as e:
                    return self._send(404, {"error": f"not found: {e}"})
                except ValueError as e:
                    # benign "unknown project_id" etc. — clean 404, no log spam
                    if "Unknown project_id" in str(e):
                        return self._send(404, {"error": str(e)})
                    traceback.print_exc()
                    return self._send(400, {"error": str(e)})
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    return self._send(400, {"error": str(e)})
        return self._send(404, {"error": f"no route for {self.command} {path}"})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _dispatch


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("DABWAYO_PORT", 8080)))
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dabwayo Studio on http://{args.host}:{args.port}")
    print(f"  store : {STORE.root}")
    print(f"  output: {OUTPUT_DIR}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
