# Movie Companion

A Linux-first Python CLI that syncs playful, timestamp-aware commentary to **VLC** while a movie is playing.

## v0 features

- `movie-companion` CLI with one main entrypoint
- VLC integration through the bundled **Lua Companion Bridge** extension
- Provider-agnostic generation: `dummy`, `openai`, `anthropic`
- Local subtitle/transcript discovery with best-effort web fallback
- Optional movie facts enrichment from a local file or Wikipedia summary
- Precomputed timed commentary cached per movie/persona
- Live playback following, including pause/seek-aware re-anchoring
- Placeholder TTS adapter boundary for future speech output

## Install

```bash
python3 -m pip install -e .
mkdir -p ~/.local/share/vlc/lua/extensions
cp vlc/companion_bridge.lua ~/.local/share/vlc/lua/extensions/
```

Open VLC, then enable the extension from **View -> Companion Bridge**.

## Quick start

```bash
movie-companion /path/to/Movie.mkv --provider dummy --precompute-only
movie-companion /path/to/Movie.mkv --provider dummy
```

If you want a simple two-window movie-night setup, use:

```bash
scripts/run_movie_with_companion.sh /path/to/Movie.mkv
```

That helper:
- starts the local HTTP bridge
- opens a second terminal that tails companion messages
- launches snap VLC with a PulseAudio-friendly env for WSLg/Linux desktops

The CLI talks to the VLC extension over:

```text
127.0.0.1:42142
```

You can override that with `--vlc-host` and `--vlc-port`.

## CLI examples

```bash
movie-companion /movies/Arrival.mkv --provider dummy
movie-companion --title "Arrival (2016)" --provider anthropic
movie-companion /movies/Spirited.Away.mkv --persona "soft, witty, slightly flirty movie-night banter" --voice nova
movie-companion --title "Alien (1979)" --library-dir /movies --provider dummy --precompute-only
```


## Local movie search and library helpers

Borrowing the safe, non-debrid discovery ideas from the sibling `realdebrid` repo, this CLI now also supports:

- `movie-companion search "Interstellar"` for metadata/title lookup via Cinemeta
- `movie-companion library /movies` to scan a local movie folder
- `movie-companion --title "Interstellar (2014)" --library-dir /movies --precompute-only` to resolve a local file automatically before generating commentary

Examples:

```bash
movie-companion search "Arrival"
movie-companion library ~/Movies --query "Arrival (2016)"
movie-companion --title "Arrival (2016)" --library-dir ~/Movies --provider dummy --precompute-only
```

## Environment variables

- `OPENAI_API_KEY` for `--provider openai`
- `ANTHROPIC_API_KEY` for `--provider anthropic`
- `MOVIE_COMPANION_CACHE_DIR` to override the cache directory
- `MOVIE_COMPANION_VLC_HOST` / `MOVIE_COMPANION_VLC_PORT` to override the bridge socket


## Self-test loop

If VLC is unavailable, you can still run an end-to-end self-test with a fake local bridge:

```bash
python3 scripts/self_test_loop.py /path/to/Movie.mkv
```

That command precomputes commentary, starts a temporary localhost bridge, and replays the first few timed comments through the normal watch loop.

## Notes

- If no API key is present, use `--provider dummy` for deterministic local commentary.
- Web transcript lookup is best-effort. A local `.srt` or `.vtt` file is much more reliable.
- The CLI will re-anchor after large rewinds/seeks so comments match the new playback position.
- TTS is currently a placeholder interface that prints what it would speak.
- The VLC bridge contract is documented in [`vlc/README.md`](vlc/README.md).
- For snap VLC on WSLg, `scripts/launch_vlc_snap.sh` adds the PulseAudio library path needed for working audio output.
