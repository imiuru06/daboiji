#!/usr/bin/env python3
"""Publish rendered clips to Dabwayo Studio — many at once, idempotently.

The real VM workflow (pattern B): the sandbox renders clips and commits them
under ``samples/``; the VM pulls and runs this to push *all the new ones* to
the Studio so they land in the gallery and dashboard.

Default behaviour is "upload every clip we haven't published yet". Each file is
keyed by its SHA-256 in a small local ledger, so re-running is safe (already
published files are skipped) and dropping in one new clip publishes only that
one — no duplicate assets.

    # publish everything new in samples/ (newest VM flow):
    cd ~/projects/daboiji && git pull
    DABWAYO_STUDIO_KEY=abce python3 scripts/publish_clips.py

    # through nginx / the public host instead of localhost:
    DABWAYO_STUDIO_URL=https://noahrun.duckdns.org/dabwayo \
    DABWAYO_STUDIO_KEY=abce python3 scripts/publish_clips.py

    --dry-run   show what would be uploaded, change nothing
    --force     re-upload everything, ignoring the ledger
    --dir PATH  add another directory to scan (repeatable)

Exit code is 0 only if every attempted upload succeeded.
"""
from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("DABWAYO_STUDIO_URL", "http://127.0.0.1:8090").rstrip("/")
KEY = os.environ.get("DABWAYO_STUDIO_KEY", "abce")
OUTPUT_DIR = os.environ.get("DABWAYO_OUTPUT", os.path.abspath(".vf_output"))
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.environ.get("DABWAYO_PUBLISH_LEDGER",
                        os.path.join(OUTPUT_DIR, ".published.json"))
EXTS = (".mp4", ".mov", ".webm", ".mkv")

GREEN, RED, YEL, DIM, RST = ("\033[32m", "\033[31m", "\033[33m",
                             "\033[2m", "\033[0m")


def _req(method: str, path: str, body: dict | None = None, auth: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if auth and KEY:
        req.add_header("Authorization", f"Bearer {KEY}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return e.code, {"raw": raw.decode("utf-8", "replace")}
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_ledger() -> dict:
    if os.path.isfile(LEDGER):
        try:
            with open(LEDGER, encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_ledger(led: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER) or ".", exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=1)


def _candidates(extra_dirs: list[str]) -> list[str]:
    # Source clips live in samples/ (committed by the sandbox). We deliberately
    # do NOT scan OUTPUT_DIR — that is where uploads *land*, so scanning it would
    # rediscover our own published copies (and --force would duplicate them).
    dirs = [d for d in ([os.environ.get("DABWAYO_UPLOAD_DIR")]
                        + [os.path.join(_REPO, "samples")]
                        + extra_dirs) if d]
    seen, out = set(), []
    for d in dirs:
        for ext in EXTS:
            for p in glob.glob(os.path.join(d, "*" + ext)):
                ap = os.path.abspath(p)
                if ap not in seen and os.path.isfile(ap):
                    seen.add(ap)
                    out.append(ap)
    out.sort(key=os.path.getmtime)            # oldest first → stable order
    return out


def _upload(path: str) -> tuple[bool, str]:
    with open(path, "rb") as f:
        raw = f.read()
    s, r = _req("POST", "/api/upload", {
        "b64": base64.b64encode(raw).decode(),
        "filename": os.path.basename(path), "kind": "video", "role": "upload",
        "provider": "publish_clips", "action": "upload",
        "prompt": f"published {os.path.basename(path)}", "tags": ["publish"],
    }, auth=True)
    if s == 200 and r.get("ok") and r.get("asset", {}).get("id"):
        return True, r["asset"]["id"]
    return False, f"HTTP {s} {r}"


def main() -> int:
    print(f"Dabwayo publish\n  base  : {BASE}\n  key   : "
          f"{'set' if KEY else '(none)'}\n  ledger: {LEDGER}")

    # fail fast if the Studio isn't reachable
    s, _ = _req("GET", "/api/index")
    if s != 200:
        print(f"{RED}Studio not reachable at {BASE} (HTTP {s}){RST}")
        return 2

    led = {} if ARGS.force else _load_ledger()
    files = _candidates(ARGS.dir or [])
    if not files:
        print(f"{YEL}No clips found to publish.{RST}")
        return 0

    uploaded = skipped = failed = 0
    for path in files:
        h = _sha256(path)
        name = os.path.basename(path)
        if h in led and not ARGS.force:
            print(f"{DIM}  skip{RST} {name}  (already published -> "
                  f"{led[h].get('asset')})")
            skipped += 1
            continue
        if ARGS.dry_run:
            print(f"{YEL}  would upload{RST} {name}")
            uploaded += 1
            continue
        good, info = _upload(path)
        if good:
            print(f"{GREEN}  ok  {RST} {name} -> {info}")
            led[h] = {"asset": info, "filename": name}
            _save_ledger(led)                 # persist after each success
            uploaded += 1
        else:
            print(f"{RED}  fail{RST} {name}: {info}")
            failed += 1

    verb = "would upload" if ARGS.dry_run else "uploaded"
    print(f"\n{verb} {uploaded} · skipped {skipped} · failed {failed}")
    if failed:
        print(f"{RED}some uploads failed{RST}")
        return 1
    if not ARGS.dry_run and uploaded:
        print(f"{GREEN}done — check the gallery / dashboard{RST}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="re-upload every clip, ignoring the ledger")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be uploaded, change nothing")
    ap.add_argument("--dir", action="append",
                    help="extra directory to scan (repeatable)")
    ARGS = ap.parse_args()
    sys.exit(main())
