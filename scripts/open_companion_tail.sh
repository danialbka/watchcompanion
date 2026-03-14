#!/usr/bin/env bash
set -euo pipefail

LOG_FILE=${1:-/tmp/stayalive_companion.log}
WINDOW_TITLE=${2:-Movie Companion}

TAIL_CMD="printf 'Movie Companion log: %s\n\n' '$LOG_FILE'; tail -n 40 -F '$LOG_FILE'"

if command -v x-terminal-emulator >/dev/null 2>&1; then
  exec x-terminal-emulator -T "$WINDOW_TITLE" -e bash -lc "$TAIL_CMD"
fi

echo "No terminal emulator found."
echo "Run this manually:"
echo "  bash -lc \"$TAIL_CMD\""
