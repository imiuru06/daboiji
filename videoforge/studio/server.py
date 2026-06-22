"""VideoForge Studio server.

A small, dependency-free HTTP server that serves the Studio web UI and a REST
API. The API is a thin wrapper over the *same* functions the MCP server
exposes (``videoforge.mcp_server``), and both share the on-disk project store
(``videoforge.service.STORE``). So a human in the browser and an agent such as
Claude Code (over MCP) edit the same projects and see each other's changes.

Run:  python -m videoforge.studio.server   [--port 8080]
Point Claude Code's MCP server at the same VIDEOFORGE_STORE to collaborate.
"""
from __future__ import annotations

import json
import os
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import capabilities as engine_capabilities
from .. import mcp_server as M
from ..service import OUTPUT_DIR, STORE

HERE = os.path.dirname(os.path.abspath(__file__))


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
    return 200, M.update_project(m.group(1), body["spec"]), None


@route("GET", r"/api/projects/([0-9a-f]+)/clips")
def _clips(h, m, body):
    return 200, M.list_clips(m.group(1)), None


@route("POST", r"/api/projects/([0-9a-f]+)/text")
def _text(h, m, body):
    return 200, M.add_text(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/background")
def _bg(h, m, body):
    return 200, M.add_background(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/callout")
def _callout(h, m, body):
    return 200, M.add_callout(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/media")
def _media(h, m, body):
    return 200, M.add_media(m.group(1), **body), None


@route("POST", r"/api/projects/([0-9a-f]+)/effect")
def _effect(h, m, body):
    return 200, M.add_effect(m.group(1), effect=body["effect"],
                             track=body.get("track"), clip_index=body.get("clip_index")), None


@route("POST", r"/api/projects/([0-9a-f]+)/camera")
def _camera(h, m, body):
    return 200, M.set_camera(m.group(1), **body), None


@route("PATCH", r"/api/projects/([0-9a-f]+)/clips/([^/]+)/(-?\d+)")
def _update_clip(h, m, body):
    return 200, M.update_clip(m.group(1), m.group(2), int(m.group(3)), body["patch"]), None


@route("DELETE", r"/api/projects/([0-9a-f]+)/clips/([^/]+)/(-?\d+)")
def _remove_clip(h, m, body):
    return 200, M.remove_clip(m.group(1), m.group(2), int(m.group(3))), None


@route("GET", r"/api/projects/([0-9a-f]+)/preview")
def _preview(h, m, body):
    q = parse_qs(urlparse(h.path).query)
    t = float(q.get("t", [0])[0])
    out = os.path.join(OUTPUT_DIR, f"_preview_{m.group(1)}.png")
    M.preview_frame(m.group(1), time=t, out_path=out)
    with open(out, "rb") as f:
        return 200, f.read(), "image/png"


@route("GET", r"/api/chat/status")
def _chat_status(h, m, body):
    from . import chat
    return 200, {"available": chat.available()}, None


@route("POST", r"/api/projects/([0-9a-f]+)/chat")
def _chat(h, m, body):
    from . import chat
    if not chat.available():
        return 200, {"available": False, "reply":
                     "AI 채팅은 ANTHROPIC_API_KEY 가 설정되어야 동작합니다 (anthropic SDK 포함). "
                     "키를 설정하고 스튜디오를 재시작하세요."}, None
    result = chat.run_chat(m.group(1), body["message"])
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
        if path.startswith("/files/"):
            name = os.path.basename(path[len("/files/"):])
            fp = os.path.join(OUTPUT_DIR, name)
            if os.path.isfile(fp):
                ctype = ("video/mp4" if name.endswith(".mp4")
                         else "image/png" if name.endswith(".png") else "application/octet-stream")
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), ctype)
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
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    return self._send(400, {"error": str(e)})
        return self._send(404, {"error": f"no route for {self.command} {path}"})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _dispatch


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("VIDEOFORGE_PORT", 8080)))
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"VideoForge Studio on http://{args.host}:{args.port}")
    print(f"  store : {STORE.root}")
    print(f"  output: {OUTPUT_DIR}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
