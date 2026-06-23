#!/usr/bin/env python3
"""End-to-end verification for Dabwayo Studio upload publishing.

Run this *on the VM* (where the Studio server and its store live). It proves the
full durable-publish chain without needing any off-box sandbox to reach the VM:

    upload (Bearer auth) -> saved to OUTPUT_DIR + asset registered
                         -> shows up in /api/index  (gallery)
                         -> shows up in /api/dashboard activity (dashboard)

Usage:
    # direct to the Studio process (recommended on the VM):
    python3 scripts/verify_upload.py

    # through nginx / the public host:
    DABWAYO_STUDIO_URL=https://noahrun.duckdns.org/dabwayo \
    DABWAYO_STUDIO_KEY=abce python3 scripts/verify_upload.py

    # upload a specific file instead of the synthesized test clip:
    python3 scripts/verify_upload.py --file ~/projects/daboiji/.vf_output/SUNSET_DRIVE.mp4

Exit code is 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

# --- config (env-overridable) --------------------------------------------
BASE = os.environ.get("DABWAYO_STUDIO_URL", "http://127.0.0.1:8090").rstrip("/")
KEY = os.environ.get("DABWAYO_STUDIO_KEY", "abce")
OUTPUT_DIR = os.environ.get("DABWAYO_OUTPUT", os.path.abspath(".vf_output"))

GREEN, RED, DIM, RST = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
_fails = 0


def ok(msg: str) -> None:
    print(f"{GREEN}  PASS{RST} {msg}")


def fail(msg: str) -> None:
    global _fails
    _fails += 1
    print(f"{RED}  FAIL{RST} {msg}")


def step(msg: str) -> None:
    print(f"\n{DIM}->{RST} {msg}")


def _req(method: str, path: str, body: dict | None = None, auth: bool = False):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if auth and KEY:
        req.add_header("Authorization", f"Bearer {KEY}")
    def _decode(raw: bytes):
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001 — binary (e.g. /files/*.mp4) or non-JSON
            return {"_bytes": len(raw)}
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, _decode(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _decode(e.read())


def _payload() -> tuple[str, bytes, str]:
    """Return (filename, raw_bytes, label). Prefer a real rendered clip; else a
    tiny valid-ish mp4 stub so the run is fully self-contained."""
    if ARGS.file:
        p = os.path.expanduser(ARGS.file)
        with open(p, "rb") as f:
            return os.path.basename(p), f.read(), f"file {p}"
    vids = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.mp4")),
                  key=os.path.getmtime, reverse=True)
    if vids:
        with open(vids[0], "rb") as f:
            return os.path.basename(vids[0]), f.read(), f"newest clip {vids[0]}"
    # minimal mp4 'ftyp' box — enough to register + serve for the smoke test
    stub = (b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
            + b"\x00\x00\x00\x08free")
    return f"verify_{int(time.time())}.mp4", stub, "synthesized stub clip"


def main() -> int:
    print(f"Dabwayo upload verification\n  base : {BASE}\n  key  : "
          f"{'set' if KEY else '(none)'}\n  store: {OUTPUT_DIR}")

    step("1. Studio reachable (GET /api/dashboard)")
    s, dash = _req("GET", "/api/dashboard")
    if s == 200 and "activity" in dash:
        ok(f"dashboard responded ({len(dash['activity'])} activity rows, "
           f"sample={dash.get('activity_is_sample')})")
    else:
        fail(f"dashboard not reachable: HTTP {s} {dash}")
        return _finish()
    base_activity = 0 if dash.get("activity_is_sample") else len(dash["activity"])

    step("2. Baseline asset index (GET /api/index)")
    s, idx0 = _req("GET", "/api/index")
    if s != 200:
        fail(f"index not reachable: HTTP {s} {idx0}")
        return _finish()
    before_ids = {a["id"] for a in idx0.get("assets", [])}
    ok(f"index responded ({idx0['counts']['assets']} assets, "
       f"{idx0['counts']['projects']} projects)")

    if KEY:
        step("3. Auth is enforced (POST /api/upload without Bearer -> 401)")
        s, _ = _req("POST", "/api/upload", {"b64": ""}, auth=False)
        ok("rejected unauthenticated upload (401)") if s == 401 else \
            fail(f"expected 401, got HTTP {s}")

    fname, raw, label = _payload()
    step(f"4. Upload ({label}, {len(raw)} bytes) (POST /api/upload + Bearer)")
    s, up = _req("POST", "/api/upload", {
        "b64": base64.b64encode(raw).decode(),
        "filename": fname, "kind": "video", "role": "upload",
        "provider": "verify-script", "action": "upload",
        "prompt": "upload verification", "tags": ["verify"],
    }, auth=True)
    if s == 200 and up.get("ok") and up.get("asset", {}).get("id"):
        aid = up["asset"]["id"]
        ok(f"uploaded -> asset {aid}, url {up.get('url')}, {up.get('bytes')} bytes")
    else:
        fail(f"upload failed: HTTP {s} {up}")
        return _finish()

    step("5. Asset shows in gallery feed (GET /api/index)")
    s, idx1 = _req("GET", "/api/index")
    after_ids = {a["id"] for a in idx1.get("assets", [])}
    if aid in after_ids and aid not in before_ids:
        rec = next(a for a in idx1["assets"] if a["id"] == aid)
        ok(f"new asset present (role={rec.get('role')}, kind={rec.get('kind')}, "
           f"provider={rec.get('provider')})")
    else:
        fail(f"asset {aid} not found in /api/index assets")
    if idx1["counts"]["assets"] == idx0["counts"]["assets"] + 1:
        ok(f"asset count incremented {idx0['counts']['assets']} -> "
           f"{idx1['counts']['assets']}")
    else:
        fail(f"asset count not +1: {idx0['counts']['assets']} -> "
             f"{idx1['counts']['assets']}")

    step("6. Publish event shows in dashboard activity (GET /api/dashboard)")
    s, dash1 = _req("GET", "/api/dashboard")
    acts = dash1.get("activity", [])
    hit = [e for e in acts if e.get("action") == "publish" and aid in
           (e.get("outputs") or [])]
    if hit and not dash1.get("activity_is_sample"):
        ok(f"publish activity recorded: \"{hit[-1].get('summary')}\"")
    else:
        fail("no real publish activity referencing the new asset")
    if len(acts) >= base_activity + 1 and not dash1.get("activity_is_sample"):
        ok(f"activity grew {base_activity} -> {len(acts)}")

    step("7. Uploaded file is served back (GET /files/...)")
    file_path = up.get("url", "")
    s, _ = _req("GET", file_path) if file_path else (0, {})
    ok(f"file served at {BASE}{file_path} (HTTP 200)") if s == 200 else \
        fail(f"file not served: HTTP {s} at {file_path}")

    return _finish()


def _finish() -> int:
    print()
    if _fails == 0:
        print(f"{GREEN}ALL CHECKS PASSED{RST} — upload publishing works end to end.")
        return 0
    print(f"{RED}{_fails} CHECK(S) FAILED{RST} — see above.")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="media file to upload (default: newest "
                    "*.mp4 in DABWAYO_OUTPUT, else a synthesized stub)")
    ARGS = ap.parse_args()
    sys.exit(main())
