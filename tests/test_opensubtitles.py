from __future__ import annotations

from pathlib import Path

from companion.ingest import ContextIngestor
from companion.models import MovieIdentity, TimedTranscriptChunk
from companion.opensubtitles import OpenSubtitleResult, pick_best_result


def test_pick_best_result_prefers_release_match_and_non_hi():
    results = [
        OpenSubtitleResult(subtitle_id='1', file_id=1, language='en', release='Stay Alive DVDRip', filename='a.srt', hearing_impaired=True, ratings=8.0),
        OpenSubtitleResult(subtitle_id='2', file_id=2, language='en', release='Stay Alive WEBRip YTS', filename='b.srt', hearing_impaired=False, ratings=7.0),
    ]
    chosen = pick_best_result(results, preferred_release_terms=['webrip', 'yts'])
    assert chosen is not None
    assert chosen.file_id == 2


def test_ingest_prefers_subtitles_and_keeps_transcript_context(tmp_path: Path):
    movie = MovieIdentity(title='Stay Alive 2006', normalized_title='stay-alive-2006', media_path=str(tmp_path / 'Stay.Alive.2006.mp4'))
    movie_path = Path(movie.media_path)
    movie_path.write_text('x')
    subtitle_path = tmp_path / 'Stay.Alive.2006.opensubtitles.en.srt'
    subtitle_path.write_text('1\n00:00:01,000 --> 00:00:02,000\nsubtitle line\n')

    class StubIngestor(ContextIngestor):
        def load_local_transcript(self, movie):
            return []
        def fetch_opensubtitles(self, movie):
            return self.parse_subtitle_text(subtitle_path.read_text(), source=str(subtitle_path))
        def fetch_online_transcript(self, movie):
            return [TimedTranscriptChunk(start_seconds=0, end_seconds=8, text='transcript context', source='web-transcript')]
        def fetch_movie_metadata(self, movie):
            return {'title': movie.title}

    ingested = StubIngestor().ingest(movie)
    assert ingested.transcript_chunks[0].text == 'subtitle line'
    assert ingested.metadata['subtitle_source'].endswith('.opensubtitles.en.srt')
    assert ingested.metadata['transcript_context'] == ['transcript context']
