#!/usr/bin/env bash
set -euo pipefail

MOVIE_PATH=${1:?usage: scripts/run_windows_vlc_with_companion.sh /path/to/movie.mp4}
WINDOWS_VLC_EXE=${WINDOWS_VLC_EXE:-C:\\Program Files\\VideoLAN\\VLC\\vlc.exe}
RC_PORT=${RC_PORT:-42150}
RELAY_PORT=${RELAY_PORT:-42150}
BRIDGE_PORT=${BRIDGE_PORT:-42142}
LOG_FILE=${LOG_FILE:-/tmp/stayalive_companion.log}
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

cleanup() {
  jobs -pr | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

WINDOWS_MOVIE_PATH=$(wslpath -w "$MOVIE_PATH")

python3 - <<'PY'
import os
import signal
import socket
from pathlib import Path

root = Path("/root/projects/companion")
candidates = []
for pid_dir in Path("/proc").iterdir():
    if not pid_dir.name.isdigit():
        continue
    try:
        cmdline = (pid_dir / "cmdline").read_bytes().decode("utf-8", "ignore").replace("\x00", " ")
    except Exception:
        continue
    if any(marker in cmdline for marker in ["scripts/vlc_http_bridge.py", "scripts/windows_vlc_rc_bridge.py", "movie-companion", "python3 -u -m companion"]):
        candidates.append(int(pid_dir.name))
for pid in candidates:
    if pid == os.getpid():
        continue
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
PY

rm -f "$LOG_FILE" /tmp/stayalive_bridge.log

WINDOWS_MOVIE_PATH="$WINDOWS_MOVIE_PATH" WINDOWS_VLC_EXE="$WINDOWS_VLC_EXE" RC_PORT="$RC_PORT" RELAY_PORT="$RELAY_PORT" python3 - <<'PY'
import os
import subprocess

movie = os.environ["WINDOWS_MOVIE_PATH"]
vlc = os.environ["WINDOWS_VLC_EXE"]
rc_port = int(os.environ["RC_PORT"])
relay_port = int(os.environ["RELAY_PORT"])
ps = f"""
$dir = 'C:\\Temp'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$relay = Join-Path $dir 'watchcompanion-vlc-rc-relay.js'
@'
const net = require('net');
const listenHost = '172.20.64.1';
const listenPort = {relay_port};
const targetHost = 'localhost';
const targetPort = {rc_port};
const server = net.createServer((client) => {{
  const remote = net.connect(targetPort, targetHost);
  client.pipe(remote);
  remote.pipe(client);
  const close = () => {{
    try {{ client.destroy(); }} catch {{}}
    try {{ remote.destroy(); }} catch {{}}
  }};
  client.on('error', close);
  remote.on('error', close);
  client.on('close', close);
  remote.on('close', close);
}});
server.listen(listenPort, listenHost, () => {{
  console.log('relay ' + listenHost + ':' + listenPort + ' -> ' + targetHost + ':' + targetPort);
}});
'@ | Set-Content -Path $relay -Encoding UTF8
Get-CimInstance Win32_Process | Where-Object {{ ($_.Name -eq 'node.exe' -and $_.CommandLine -like '*watchcompanion-vlc-rc-relay.js*') -or ($_.Name -eq 'vlc.exe' -and $_.CommandLine -like '*--rc-host=127.0.0.1:{rc_port}*') }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
Start-Process -FilePath 'C:\\nvm4w\\nodejs\\node.exe' -ArgumentList $relay -WindowStyle Hidden
Start-Sleep -Seconds 1
Start-Process -FilePath '{vlc}' -ArgumentList @('--extraintf=rc','--rc-host=127.0.0.1:{rc_port}','--no-video-title-show','{movie}')
"""
res = subprocess.run(['powershell.exe','-NoProfile','-Command',ps], text=True, capture_output=True)
if res.returncode != 0:
    raise SystemExit(res.stderr or res.stdout or "failed to start Windows VLC")
print("started windows vlc + relay")
PY

cd "$ROOT_DIR"

if command -v x-terminal-emulator >/dev/null 2>&1; then
  x-terminal-emulator -T "Movie Companion" -e bash -lc "printf 'Movie Companion log: %s\n\n' '$LOG_FILE'; tail -n 40 -F '$LOG_FILE'" >/dev/null 2>&1 &
fi

setsid -f bash -lc "cd '$ROOT_DIR' && exec python3 -u scripts/windows_vlc_rc_bridge.py '$BRIDGE_PORT' '172.20.64.1' '$RELAY_PORT' '$MOVIE_PATH' >/tmp/stayalive_bridge.log 2>&1"
python3 - "$BRIDGE_PORT" <<'PY'
import socket
import sys
import time

port = int(sys.argv[1])
deadline = time.time() + 10
while time.time() < deadline:
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(("127.0.0.1", port))
        print("local bridge ready")
        raise SystemExit(0)
    except OSError:
        time.sleep(0.25)
    finally:
        sock.close()
raise SystemExit("bridge failed to start")
PY

echo "Windows VLC launched with RC relay."
echo "Companion log: $LOG_FILE"
PYTHONUNBUFFERED=1 MOVIE_COMPANION_VLC_PORT="$BRIDGE_PORT" PYTHONPATH=src python3 -u -m companion "$MOVIE_PATH" --provider dummy | tee -a "$LOG_FILE"
