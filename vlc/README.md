# VLC Companion Bridge

This folder contains the VLC-side integration for the movie companion CLI.

## What it does

`companion_bridge.lua` is a minimal VLC Lua extension that opens a local TCP socket on `127.0.0.1:42142` and returns the current playback state as JSON.

It is intended for a local CLI process running on the same machine.

## Install

```bash
mkdir -p ~/.local/share/vlc/lua/extensions
cp vlc/companion_bridge.lua ~/.local/share/vlc/lua/extensions/
```

Then launch VLC and enable the extension from:

- `View -> Companion Bridge`

## Wire protocol

Connect to `127.0.0.1:42142` and send a single line:

```text
GET_STATE
```

If no line is sent, the extension treats the connection as `GET_STATE`.

### Response JSON

```json
{
  "active": true,
  "playing": true,
  "paused": false,
  "state": "playing",
  "title": "Movie Title",
  "uri": "file:///path/to/movie.mp4",
  "position": 0.42,
  "length": 7265,
  "timestamp": 3041,
  "rate": 1.0,
  "volume": 256,
  "error": null
}
```

### Contract notes

- `timestamp` and `length` are in **seconds**.
- `position` is a `0..1` fraction when available.
- `state` is normalized to `playing`, `paused`, or `stopped` when possible.
- The socket is bound to localhost only.
- v0 is **poll-based** from the CLI side; the extension returns a snapshot per request.
- Large seeks are naturally handled because each request returns the current VLC timestamp.

## Manual test

With VLC playing media and the extension enabled:

```bash
printf 'GET_STATE\n' | nc 127.0.0.1 42142
```

## Known limitations

- Depends on VLC's Lua extension runtime and LuaSocket availability in the VLC build.
- This v0 contract exposes state snapshots, not push events.
- The extension does not authenticate clients because it only binds to `127.0.0.1`.
