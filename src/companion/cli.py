from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import CinemetaClient
from .config import StartRequest, load_config
from .demo import ScriptedBridge, build_demo_states, ensure_demo_transcript
from .library import find_best_local_match, scan_library
from .session import SessionRunner


def build_watch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch movies with a timed AI companion for VLC.")
    parser.add_argument("movie_path", nargs="?", help="Path to the movie file currently loaded in VLC.")
    parser.add_argument("--title", help="Movie title if you are not starting from a local file path.")
    parser.add_argument("--provider", default=None, help="LLM provider: dummy, openai, anthropic.")
    parser.add_argument("--persona", default=None, help="Persona prompt override.")
    parser.add_argument("--voice", default=None, help="Optional TTS voice id. Placeholder for v0.")
    parser.add_argument("--library-dir", action="append", default=[], help="Local movie library directory to search when only --title is given.")
    parser.add_argument("--precompute-only", action="store_true", help="Generate/cache commentary and exit without live watching.")
    parser.add_argument("--once", action="store_true", help="Poll VLC once, emit due comments, then exit.")
    return parser


def build_subcommand_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="movie-companion", description="Movie companion utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search movie metadata catalogs.")
    search.add_argument("query", help="Movie title query.")
    search.add_argument("--limit", type=int, default=10, help="Max results to print.")

    library = subparsers.add_parser("library", help="Scan a local movie folder.")
    library.add_argument("path", help="Directory to scan.")
    library.add_argument("--query", help="Optional title to fuzzy-match within the library.")
    library.add_argument("--limit", type=int, default=20, help="Max results to print.")

    demo = subparsers.add_parser("demo", help="Run a scripted self-test without VLC.")
    demo.add_argument("movie_path", help="Local movie file to demo.")
    demo.add_argument("--title", help="Optional override title.")
    demo.add_argument("--provider", default=None, help="LLM provider: dummy, openai, anthropic.")
    demo.add_argument("--persona", default=None, help="Persona prompt override.")
    demo.add_argument("--voice", default=None, help="Optional TTS voice id. Placeholder for v0.")
    demo.add_argument("--comment-limit", type=int, default=5, help="How many generated comments to simulate.")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in {"search", "library", "demo"}:
        return _run_subcommand(argv)
    return _run_watch(argv)


def _run_watch(argv: list[str]) -> int:
    parser = build_watch_parser()
    args = parser.parse_args(argv)
    movie_path = args.movie_path
    if not movie_path and not args.title:
        parser.error("either movie_path or --title is required")
    if not movie_path and args.title and args.library_dir:
        match = find_best_local_match(args.title, args.library_dir)
        if match:
            movie_path = str(match.path)
            print(f"Resolved local movie: {match.title} -> {match.path}")
    return _run_session(movie_path=movie_path, title=args.title, provider=args.provider, persona=args.persona, voice=args.voice, precompute_only=args.precompute_only, once=args.once)


def _run_session(*, movie_path: str | None, title: str | None, provider: str | None, persona: str | None, voice: str | None, precompute_only: bool, once: bool, bridge=None) -> int:
    config = load_config(provider=provider, persona=persona, voice=voice)
    runner = SessionRunner(config=config, bridge=bridge)
    request = StartRequest(
        movie_path=movie_path,
        title=title,
        provider=config.provider,
        persona=config.persona,
        voice=config.voice,
        once=once,
    )
    try:
        artifacts = runner.prepare(request)
        print(
            f"Prepared commentary for {artifacts.commentary.movie.title} "
            f"({'cache hit' if artifacts.cached else 'generated'}, {len(artifacts.commentary.comments)} comments)."
        )
        if precompute_only:
            return 0
        runner.watch(artifacts.commentary, once=once)
        return 0
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_subcommand(argv: list[str]) -> int:
    parser = build_subcommand_parser()
    args = parser.parse_args(argv)
    if args.command == "search":
        client = CinemetaClient()
        try:
            results = client.discover_movies(search=args.query)[: args.limit]
        finally:
            client.session.close()
        for index, item in enumerate(results, start=1):
            year = f" ({item.year})" if item.year else ""
            print(f"{index:>2}. {item.title}{year} [{item.imdb_id}]")
        return 0
    if args.command == "library":
        path = Path(args.path)
        if args.query:
            match = find_best_local_match(args.query, [path])
            if not match:
                print("No matching local movie found.", file=sys.stderr)
                return 1
            year = f" ({match.year})" if match.year else ""
            print(f"{match.title}{year}\n{match.path}")
            return 0
        results = scan_library([path])[: args.limit]
        for index, item in enumerate(results, start=1):
            year = f" ({item.year})" if item.year else ""
            print(f"{index:>2}. {item.title}{year} -> {item.path}")
        return 0
    if args.command == "demo":
        config = load_config(provider=args.provider, persona=args.persona, voice=args.voice)
        runner = SessionRunner(config=config)
        request = StartRequest(
            movie_path=args.movie_path,
            title=args.title,
            provider=config.provider,
            persona=config.persona,
            voice=config.voice,
            once=False,
        )
        try:
            artifacts = runner.prepare(request)
        except Exception:
            ensure_demo_transcript(args.movie_path)
            artifacts = runner.prepare(request)
        bridge = ScriptedBridge(build_demo_states(artifacts.commentary, args.movie_path, comment_limit=args.comment_limit))
        demo_runner = SessionRunner(config=config, bridge=bridge)
        print(f"Demo bridge prepared for {artifacts.commentary.movie.title} using {min(args.comment_limit, len(artifacts.commentary.comments))} comments.")
        demo_runner.watch(artifacts.commentary, once=False)
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
