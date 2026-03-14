#!/usr/bin/env bash
set -euo pipefail

MOVIE_PATH=${1:?usage: scripts/run_movie_with_companion.sh /path/to/movie.mp4}
HTTP_PASSWORD=${HTTP_PASSWORD:-codexpass}
HTTP_PORT=${HTTP_PORT:-8080}
BRIDGE_PORT=${BRIDGE_PORT:-42142}
LOG_FILE=${LOG_FILE:-/tmp/movie_companion.log}
WINDOW_TITLE=${WINDOW_TITLE:-Movie Companion}
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
STATUS_URL="http://127.0.0.1:${HTTP_PORT}/requests/status.json"

cleanup() {
  jobs -pr | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

python3 scripts/vlc_http_bridge.py "$BRIDGE_PORT" "http://127.0.0.1:${HTTP_PORT}/requests/status.json" "$HTTP_PASSWORD" &
BRIDGE_PID=$!

echo "Started HTTP bridge on port ${BRIDGE_PORT} (pid ${BRIDGE_PID})"
echo "Companion log: ${LOG_FILE}"

if command -v x-terminal-emulator >/dev/null 2>&1; then
  x-terminal-emulator -T "$WINDOW_TITLE" -e bash -lc "printf 'Movie Companion log: %s\n\n' '$LOG_FILE'; tail -n 40 -F '$LOG_FILE'" >/dev/null 2>&1 &
  echo "Opened tail window in a second terminal."
else
  echo "No terminal emulator found. Tail manually with:"
  echo "  tail -n 40 -F '$LOG_FILE'"
fi

if [[ -x scripts/launch_vlc_snap.sh ]]; then
  echo "Launching snap VLC with PulseAudio + HTTP bridge..."
  HTTP_PASSWORD="$HTTP_PASSWORD" scripts/launch_vlc_snap.sh "$MOVIE_PATH" >/tmp/movie_companion_vlc.log 2>&1 &
  VLC_PID=$!
  echo "Started VLC (pid ${VLC_PID})."
else
  echo "Launch VLC separately with HTTP enabled, for example:"
  echo "  vlc --extraintf luahttp --http-password ${HTTP_PASSWORD} --http-host 127.0.0.1 '${MOVIE_PATH}'"
fi

echo "Waiting for VLC HTTP status..."
python3 - "$STATUS_URL" "$HTTP_PASSWORD" <<'PY'
import sys
import time

import requests

url, password = sys.argv[1], sys.argv[2]
deadline = time.time() + 30
last_error = "unknown"
while time.time() < deadline:
    try:
        response = requests.get(url, auth=("", password), timeout=2)
        response.raise_for_status()
        print("VLC HTTP bridge is ready.")
        raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
        time.sleep(1)
print(f"Timed out waiting for VLC HTTP status: {last_error}", file=sys.stderr)
raise SystemExit(1)
PY

echo "Starting companion..."
PYTHONUNBUFFERED=1 MOVIE_COMPANION_VLC_PORT="$BRIDGE_PORT" movie-companion "$MOVIE_PATH" --provider dummy | tee -a "$LOG_FILE"
