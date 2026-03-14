from __future__ import annotations

from pathlib import Path

from companion.catalog import CinemetaClient
from companion.cli import main
from companion.library import find_best_local_match, scan_library


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers = {}
        self.urls = []

    def get(self, url, timeout):
        self.urls.append((url, timeout))
        return FakeResponse(self.payload)

    def close(self):
        return None


def test_cinemeta_search_parses_results():
    session = FakeSession(
        {
            "metas": [
                {
                    "id": "tt0133093",
                    "name": "The Matrix",
                    "releaseInfo": "1999",
                    "description": "Neo learns kung fu.",
                }
            ]
        }
    )
    client = CinemetaClient(session=session)
    results = client.discover_movies(search="matrix")
    assert len(results) == 1
    assert results[0].title == "The Matrix"
    assert results[0].year == 1999
    assert "search=matrix" in session.urls[0][0]


def test_scan_library_and_find_match(tmp_path: Path):
    movie = tmp_path / "Interstellar.2014.mkv"
    movie.write_text("x")
    (tmp_path / "Arrival.2016.mkv").write_text("x")
    items = scan_library([tmp_path])
    assert len(items) == 2
    match = find_best_local_match("Interstellar (2014)", [tmp_path])
    assert match is not None
    assert match.path == movie


def test_cli_resolves_title_from_library_dir(tmp_path: Path, capsys):
    movie_path = tmp_path / "My.Movie.2024.mkv"
    movie_path.write_text("not a real movie")
    subtitle_path = tmp_path / "My.Movie.2024.srt"
    subtitle_path.write_text("""1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n2\n00:03:00,000 --> 00:03:02,000\nGeneral Kenobi\n""")
    exit_code = main([
        "--title",
        "My Movie (2024)",
        "--library-dir",
        str(tmp_path),
        "--provider",
        "dummy",
        "--precompute-only",
    ])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Resolved local movie" in captured.out
    assert "Prepared commentary" in captured.out


def test_cli_library_query(tmp_path: Path, capsys):
    movie_path = tmp_path / "Heat.1995.mkv"
    movie_path.write_text("x")
    exit_code = main(["library", str(tmp_path), "--query", "Heat (1995)"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(movie_path) in captured.out


def test_infer_title_from_release_filename():
    from companion.models import infer_title_from_path

    title = infer_title_from_path("Stay.Alive.2006.1080p.WEBRip.x264.AAC5.1-[YTS.MX].mp4")
    assert title == "Stay Alive 2006"
