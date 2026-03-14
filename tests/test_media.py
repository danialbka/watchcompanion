from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from companion.ingest import ContextIngestor
from companion.media import extract_embedded_subtitles, probe_subtitle_streams
from companion.models import MovieIdentity


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe required")
def test_extract_embedded_subtitles_and_ingest(tmp_path: Path):
    subtitle_path = tmp_path / "sample.srt"
    subtitle_path.write_text(
        """1\n00:00:00,500 --> 00:00:01,500\nhello from embedded subtitles\n\n2\n00:00:02,000 --> 00:00:03,000\nsecond line here\n"""
    )
    movie_path = tmp_path / "embedded.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=4",
            "-i",
            str(subtitle_path),
            "-c:v",
            "libx264",
            "-t",
            "4",
            "-pix_fmt",
            "yuv420p",
            "-c:s",
            "mov_text",
            str(movie_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    streams = probe_subtitle_streams(movie_path)
    assert streams

    extracted = extract_embedded_subtitles(movie_path, tmp_path / "extracted.srt")
    assert extracted is not None
    assert "hello from embedded subtitles" in extracted.read_text()

    movie = MovieIdentity(title="Embedded", normalized_title="embedded", media_path=str(movie_path))
    chunks = ContextIngestor().load_local_transcript(movie)
    assert len(chunks) == 2
    assert chunks[0].text == "hello from embedded subtitles"


def test_load_local_transcript_ignores_unrelated_sidecars(tmp_path: Path):
    movie_path = tmp_path / "Movie.One.2024.mp4"
    movie_path.write_text("x")
    unrelated = tmp_path / "Other.Movie.srt"
    unrelated.write_text("""1\n00:00:01,000 --> 00:00:02,000\nwrong subtitle\n""")
    related = tmp_path / "Movie.One.2024.srt"
    related.write_text("""1\n00:00:01,000 --> 00:00:02,000\nright subtitle\n""")
    movie = MovieIdentity(title="Movie One 2024", normalized_title="movie-one-2024", media_path=str(movie_path))
    chunks = ContextIngestor().load_local_transcript(movie)
    assert len(chunks) == 1
    assert chunks[0].text == "right subtitle"


def test_parse_subtitle_text_ignores_watermark_lines():
    raw = """1\n00:00:02,000 --> 00:00:07,000\nDownloaded from\nYTS.MX\n\n2\n00:00:08,000 --> 00:00:10,000\nHello there\n"""
    chunks = ContextIngestor().parse_subtitle_text(raw, source="memory")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello there"
