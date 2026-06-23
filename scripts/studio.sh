#!/usr/bin/env bash
# Manage the Dabwayo Studio server with one short command.
#
#   scripts/studio.sh start      # start if not already running
#   scripts/studio.sh stop       # stop it
#   scripts/studio.sh restart    # stop + start (use after the server CODE changes)
#   scripts/studio.sh status     # is it up? which routes? which store?
#
# You only need `restart` when the server's own code changed (e.g. a new API
# route). Publishing new videos does NOT need a restart.
#
# Config via env (sensible defaults shown):
#   DABWAYO_STUDIO_KEY=abce
#   DABWAYO_PORT=8090
#   DABWAYO_STORE=<repo>/.vf_store
#   DABWAYO_OUTPUT=<repo>/.vf_output
#   DABWAYO_STUDIO_LOG=~/studio.log
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${DABWAYO_PORT:-8090}"
KEY="${DABWAYO_STUDIO_KEY:-abce}"
STORE="${DABWAYO_STORE:-$REPO/.vf_store}"
OUTPUT="${DABWAYO_OUTPUT:-$REPO/.vf_output}"
LOG="${DABWAYO_STUDIO_LOG:-$HOME/studio.log}"
PATTERN="dabwayo.studio.server"
URL="http://127.0.0.1:$PORT"

is_running() { pgrep -f "$PATTERN" >/dev/null 2>&1; }

http() { curl -s -o /dev/null -w "%{http_code}" -m 5 "$@" 2>/dev/null || echo 000; }

start() {
  if is_running; then echo "already running (pid $(pgrep -f "$PATTERN" | tr '\n' ' '))"; return 0; fi
  cd "$REPO"
  DABWAYO_STUDIO_KEY="$KEY" DABWAYO_STORE="$STORE" DABWAYO_OUTPUT="$OUTPUT" \
    DABWAYO_PORT="$PORT" PYTHONPATH="$REPO" \
    nohup python3 -m "$PATTERN" >"$LOG" 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ "$(http "$URL/api/index")" = "200" ] && break; sleep 0.5
  done
  status
}

stop() {
  if ! is_running; then echo "not running"; return 0; fi
  pkill -f "$PATTERN"; sleep 1
  is_running && { echo "still running — forcing"; pkill -9 -f "$PATTERN"; sleep 1; }
  echo "stopped"
}

status() {
  if is_running; then
    echo "UP    pid $(pgrep -f "$PATTERN" | tr '\n' ' ')  port $PORT"
  else
    echo "DOWN  (no $PATTERN process)"; return 0
  fi
  echo "  store : $STORE"
  echo "  output: $OUTPUT"
  echo "  log   : $LOG"
  echo "  GET  /api/index   -> $(http "$URL/api/index")  (200 = ok)"
  # upload route present? 401/400 = route exists (auth/body checked); 404 = stale build
  local up; up="$(http -X POST -d '{}' "$URL/api/upload")"
  case "$up" in
    401|400) echo "  POST /api/upload  -> $up  (route present, ok)";;
    404)     echo "  POST /api/upload  -> 404 (STALE build — run: $0 restart)";;
    *)       echo "  POST /api/upload  -> $up";;
  esac
}

case "${1:-status}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  *) echo "usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
