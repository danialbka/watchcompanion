from __future__ import annotations

from pathlib import Path

from companion.cli import main
from companion.demo import ScriptedBridge, build_demo_states
from companion.models import CommentaryPlan, MovieIdentity, TimedComment
from companion.media import choose_subtitle_stream


def test_choose_subtitle_stream_prefers_non_sdh_english():
    streams = [
        {"index": 2, "codec_name": "subrip", "tags": {"language": "eng"}},
        {"index": 3, "codec_name": "subrip", "tags": {"language": "eng", "title": "SDH"}},
    ]
    assert choose_subtitle_stream(streams) == 2


def test_build_demo_states_includes_rewind():
    commentary = CommentaryPlan(
        movie=MovieIdentity(title="Movie", normalized_title="movie"),
        persona="warm",
        provider="dummy",
        transcript_chunks=[],
        comments=[
            TimedComment(timestamp_seconds=5.0, text="first"),
            TimedComment(timestamp_seconds=20.0, text="second"),
        ],
        runtime_seconds=100.0,
    )
    states = build_demo_states(commentary, movie_path=None, comment_limit=2)
    assert states[1].current_seconds == 5.0
    assert states[-2].current_seconds == 4.0
    assert states[-1].current_seconds == 5.0


def test_cli_demo_runs_without_vlc(tmp_path: Path, capsys):
    movie_path = tmp_path / "Demo.Movie.2024.mkv"
    movie_path.write_text("not a real movie")
    subtitle_path = tmp_path / "Demo.Movie.2024.srt"
    subtitle_path.write_text("""1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n2\n00:03:00,000 --> 00:03:02,000\nGeneral Kenobi\n""")
    exit_code = main(["demo", str(movie_path), "--provider", "dummy", "--comment-limit", "2"])
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Demo bridge prepared" in captured
    assert "Watching Demo Movie" in captured
