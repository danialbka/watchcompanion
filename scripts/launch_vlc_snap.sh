#!/usr/bin/env bash
set -euo pipefail

MOVIE_PATH=${1:?usage: scripts/launch_vlc_snap.sh /path/to/movie.mp4 [extra vlc args...]}
shift || true

SNAP_DIR=${SNAP_DIR:-/snap/vlc/current}
if [[ ! -x "$SNAP_DIR/usr/bin/vlc" ]]; then
  echo "snap VLC binary not found at $SNAP_DIR/usr/bin/vlc" >&2
  exit 1
fi

ARCH=${SNAP_ARCH:-$(dpkg --print-architecture 2>/dev/null || echo amd64)}
export SNAP="$SNAP_DIR"
export SNAP_ARCH="$ARCH"
export SNAP_USER_COMMON="${SNAP_USER_COMMON:-$HOME/snap/vlc/common}"
mkdir -p "$SNAP_USER_COMMON"

export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

export LD_LIBRARY_PATH="$SNAP/usr/lib/vlc:$SNAP/usr/lib:$SNAP/lib/x86_64-linux-gnu:$SNAP/usr/lib/x86_64-linux-gnu:$SNAP/usr/lib/x86_64-linux-gnu/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH="$SNAP/usr/lib/x86_64-linux-gnu/qt5/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$SNAP/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms"
export FONTCONFIG_PATH="$SNAP/etc/fonts"
export FONTCONFIG_FILE="$SNAP/etc/fonts/fonts.conf"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export QT_XCB_GL_INTEGRATION="${QT_XCB_GL_INTEGRATION:-none}"

exec "$SNAP/usr/bin/vlc" \
  --no-dbus \
  --extraintf luahttp \
  --http-password "${HTTP_PASSWORD:-codexpass}" \
  --http-host "127.0.0.1" \
  --aout pulse \
  --no-video-title-show \
  "$MOVIE_PATH" \
  "$@"
