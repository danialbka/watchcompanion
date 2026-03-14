from __future__ import annotations

from pathlib import Path

from companion.config import StartRequest, load_config
from companion.generator import CommentaryPlanner
from companion.ingest import ContextIngestor
from companion.models import MovieIdentity, PlaybackState, TimedComment, TimedTranscriptChunk
from companion.providers import DummyProvider, parse_comments_json
from companion.session import SessionRunner


class FakeBridge:
    def __init__(self, states):
        self._states = iter(states)

    def get_state(self):
        return next(self._states)


class FakeSpeech:
    def __init__(self):
        self.calls = []

    def speak(self, request):
        self.calls.append(request)


class FakeIngestor:
    def ingest(self, movie):
        return type(
            "Ingested",
            (),
            {
                "transcript_chunks": [
                    TimedTranscriptChunk(start_seconds=0, end_seconds=6, text="Hello there", source="test"),
                    TimedTranscriptChunk(start_seconds=8, end_seconds=12, text="General Kenobi", source="test"),
                ],
                "metadata": {"summary": "A test movie."},
            },
        )()


def test_parse_srt_text():
    raw = """1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n2\n00:00:03,000 --> 00:00:05,000\nGeneral Kenobi\n"""
    chunks = ContextIngestor().parse_subtitle_text(raw, source="memory")
    assert len(chunks) == 2
    assert chunks[0].start_seconds == 1.0
    assert chunks[1].text == "General Kenobi"


def test_commentary_planner_builds_sorted_comments():
    planner = CommentaryPlanner(provider=DummyProvider())
    movie = MovieIdentity(title="Test Movie", normalized_title="test-movie")
    chunks = [
        TimedTranscriptChunk(start_seconds=0, end_seconds=10, text="A", source="x"),
        TimedTranscriptChunk(start_seconds=11, end_seconds=20, text="B", source="x"),
        TimedTranscriptChunk(start_seconds=21, end_seconds=30, text="C", source="x"),
    ]
    plan = planner.build_plan(movie=movie, transcript_chunks=chunks, metadata={}, persona="warm")
    assert plan.comments
    assert plan.comments == sorted(plan.comments, key=lambda item: item.timestamp_seconds)


def test_parse_comments_json_handles_embedded_json():
    raw = 'hello {"comments":[{"timestamp_seconds":12,"text":"cute","confidence":0.8,"spoiler_level":"mild"}]}'
    comments = parse_comments_json(raw)
    assert len(comments) == 1
    assert comments[0].text == "cute"


def test_session_prepare_caches_and_reuses(tmp_path: Path):
    config = load_config(provider="dummy", persona="persona", voice=None)
    config.cache_dir = tmp_path
    runner = SessionRunner(config=config, bridge=FakeBridge([]), ingestor=FakeIngestor(), speech=FakeSpeech())
    request = StartRequest(movie_path=None, title="My Movie", provider="dummy", persona="persona", voice=None)
    first = runner.prepare(request)
    second = runner.prepare(request)
    assert not first.cached
    assert second.cached
    assert (tmp_path / "my-movie.json").exists()


def test_watch_emits_due_comment_and_tts(tmp_path: Path, capsys):
    config = load_config(provider="dummy", persona="persona", voice="alloy")
    config.cache_dir = tmp_path
    speech = FakeSpeech()
    states = [
        PlaybackState(title="Movie", media_path=None, current_seconds=10.0, total_seconds=100.0, is_playing=True),
    ]
    runner = SessionRunner(config=config, bridge=FakeBridge(states), ingestor=FakeIngestor(), speech=speech)
    commentary = type(
        "Commentary",
        (),
        {
            "movie": MovieIdentity(title="Movie", normalized_title="movie"),
            "provider": "dummy",
            "comments": [TimedComment(timestamp_seconds=11.0, text="Aww, that's cute.")],
            "runtime_seconds": None,
        },
    )()
    runner.watch(commentary, once=True)
    captured = capsys.readouterr()
    assert "Aww, that's cute." in captured.out
    assert len(speech.calls) == 1
