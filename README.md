# WatchCompanion

Watch a movie in **VLC** while a companion CLI drops timed comments like a funny friend sitting next to you.

It can use:
- local subtitles (`.srt`, `.vtt`)
- embedded subtitles from the video file
- best-effort online transcript context
- optional OpenSubtitles lookup

Then it precomputes timestamped commentary and reveals it live as VLC plays, pauses, and seeks.

## What it does

- syncs commentary to the movie timestamp
- follows rewinds / seeks
- caches commentary per movie
- supports `dummy`, `openai`, and `anthropic` providers
- supports local library search + title resolution
- can show companion text in a **second terminal window**
- can blend **subtitle timing + transcript context**
- supports a **local style profile** so commentary can sound more human/personal

## Current best setup

### Windows + WSL

The most reliable setup right now is:
- **Windows VLC** for playback/audio
- WSL/Linux for the Python companion
- the included **Windows VLC RC bridge**

Use:

```bash
cd /root/projects/companion
scripts/run_windows_vlc_with_companion.sh "/path/to/Movie.mp4"
```

That helper:
- launches Windows VLC
- starts a local bridge on `127.0.0.1:42142`
- opens a second terminal tailing the companion log
- starts the companion loop

### Linux / snap VLC

There is also a Linux-first path using the bundled VLC Lua extension:

```bash
python3 -m pip install -e .
mkdir -p ~/.local/share/vlc/lua/extensions
cp vlc/companion_bridge.lua ~/.local/share/vlc/lua/extensions/
```

Then in VLC:
- `View -> Companion Bridge`

And run:

```bash
movie-companion /path/to/Movie.mkv --provider dummy
```

Or:

```bash
scripts/run_movie_with_companion.sh /path/to/Movie.mkv
```

## Install

```bash
python3 -m pip install -e .
```

## Quick start

Precompute only:

```bash
movie-companion /path/to/Movie.mkv --provider dummy --precompute-only
```

Watch live:

```bash
movie-companion /path/to/Movie.mkv --provider dummy
```

Use a title + local library:

```bash
movie-companion --title "Arrival (2016)" --library-dir ~/Movies --provider dummy
```

## CLI examples

```bash
movie-companion /movies/Arrival.mkv --provider dummy
movie-companion --title "Arrival (2016)" --provider anthropic
movie-companion /movies/Spirited.Away.mkv --persona "funny, warm, close-friend movie banter" --voice nova
movie-companion --title "Alien (1979)" --library-dir /movies --provider dummy --precompute-only
movie-companion search "Interstellar"
movie-companion library ~/Movies --query "Interstellar (2014)"
```

## Subtitle / transcript ingestion order

The ingestor tries, roughly, in this order:

1. local sidecar subtitles
2. embedded subtitles
3. OpenSubtitles
4. online transcript/script fallback

If subtitles are available, they are used for timing.
If transcript text is also available, it is kept as extra context.

## OpenSubtitles

Set:

```bash
export OPENSUBTITLES_API_KEY=...
```

Then the app can try OpenSubtitles automatically when no good local subtitle file is present.

## Style profiles

You can point the app at a local JSON style profile:

```bash
export MOVIE_COMPANION_STYLE_PROFILE=/absolute/path/to/profile.json
```

The default config also checks for a local profile at:

```text
profiles/danial_whatsapp_style.json
```

Style profiles are intended to stay **local/private** and are gitignored.

## Environment variables

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENSUBTITLES_API_KEY`
- `MOVIE_COMPANION_CACHE_DIR`
- `MOVIE_COMPANION_STYLE_PROFILE`
- `MOVIE_COMPANION_VLC_HOST`
- `MOVIE_COMPANION_VLC_PORT`
- `MOVIE_COMPANION_VLC_TIMEOUT`
- `MOVIE_COMPANION_VOICE`
- `MOVIE_COMPANION_PERSONA`

## Logs / second window

The second terminal window usually tails:

```text
/tmp/stayalive_companion.log
```

You can open that manually with:

```bash
bash scripts/open_companion_tail.sh /tmp/stayalive_companion.log "Movie Companion"
```

## Self-test

If VLC is unavailable, run:

```bash
python3 scripts/self_test_loop.py /path/to/Movie.mkv
```

Or:

```bash
movie-companion demo /path/to/Movie.mkv --provider dummy --comment-limit 5
```

## Notes

- `dummy` provider is deterministic and works offline.
- local subtitles are much more reliable than transcript-only timing.
- TTS is still a placeholder boundary.
- the live socket contract for the Lua bridge is documented in [`vlc/README.md`](vlc/README.md).
- this repo gitignores local media, subtitles, logs, env files, and local/private style profiles.
