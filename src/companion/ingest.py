from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import requests

from .media import extract_embedded_subtitles
from .opensubtitles import OpenSubtitlesClient, pick_best_result
from .models import MovieIdentity, TimedTranscriptChunk

USER_AGENT = "movie-companion/0.1 (+https://localhost)"
SEARCH_ENDPOINT = "https://duckduckgo.com/html/"
WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
PREFERRED_TRANSCRIPT_DOMAINS = ["subslikescript.com", "scriptslug.com", "imsdb.com"]
SUBTITLE_NOISE_PATTERNS = [
    r"yts\.mx",
    r"yify",
    r"opensubtitles\.org",
    r"downloaded from",
    r"official .*movies site",
]


@dataclass(slots=True)
class IngestedContext:
    transcript_chunks: list[TimedTranscriptChunk]
    metadata: dict


class ContextIngestor:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def ingest(self, movie: MovieIdentity) -> IngestedContext:
        subtitle_chunks = self.load_local_transcript(movie)
        metadata = self.fetch_movie_metadata(movie)
        transcript_chunks: list[TimedTranscriptChunk] = []
        if not subtitle_chunks:
            subtitle_chunks = self.fetch_opensubtitles(movie)
        transcript_chunks = self.fetch_online_transcript(movie)
        if subtitle_chunks:
            metadata["subtitle_source"] = subtitle_chunks[0].source
            if transcript_chunks:
                metadata["transcript_source"] = transcript_chunks[0].source
                metadata["transcript_context"] = [chunk.text for chunk in transcript_chunks[:40]]
            return IngestedContext(transcript_chunks=subtitle_chunks, metadata=metadata)
        if transcript_chunks:
            metadata["transcript_source"] = transcript_chunks[0].source
            return IngestedContext(transcript_chunks=transcript_chunks, metadata=metadata)
        transcript_chunks = self.synthetic_transcript_from_metadata(movie, metadata)
        return IngestedContext(transcript_chunks=transcript_chunks, metadata=metadata)

    def load_local_transcript(self, movie: MovieIdentity) -> list[TimedTranscriptChunk]:
        candidates: list[Path] = []
        if movie.media_path:
            media = Path(movie.media_path)
            if media.parent.exists():
                stem = media.stem
                for suffix in (".srt", ".vtt", ".txt"):
                    direct = media.parent / f"{stem}{suffix}"
                    if direct.exists():
                        candidates.append(direct)
                for suffix in (".srt", ".vtt", ".txt"):
                    candidates.extend(sorted(media.parent.glob(f"{stem}*{suffix}")))
        for path in candidates:
            parsed = self.parse_subtitle_text(path.read_text(errors="ignore"), source=str(path))
            if parsed:
                return parsed
        if movie.media_path:
            media = Path(movie.media_path)
            extracted = media.with_suffix('.companion.en.srt')
            embedded = extract_embedded_subtitles(media, extracted)
            if embedded:
                parsed = self.parse_subtitle_text(embedded.read_text(errors="ignore"), source=str(embedded))
                if parsed:
                    return parsed
        return []

    def fetch_opensubtitles(self, movie: MovieIdentity) -> list[TimedTranscriptChunk]:
        client = OpenSubtitlesClient(timeout=self.timeout)
        preferred_terms: list[str] = []
        if movie.media_path:
            preferred_terms = [part.lower() for part in Path(movie.media_path).stem.replace('.', ' ').split()]
        try:
            results = client.search(movie.title, year=movie.year, language="en")
        except requests.RequestException:
            return []
        chosen = pick_best_result(results, preferred_release_terms=preferred_terms)
        if not chosen:
            return []
        target = Path(movie.media_path).with_suffix('.opensubtitles.en.srt') if movie.media_path else Path.cwd() / f"{movie.normalized_title}.opensubtitles.en.srt"
        try:
            downloaded = client.download(chosen.file_id, target)
        except (requests.RequestException, RuntimeError):
            return []
        parsed = self.parse_subtitle_text(downloaded.read_text(errors="ignore"), source=str(downloaded))
        return parsed

    def fetch_online_transcript(self, movie: MovieIdentity) -> list[TimedTranscriptChunk]:
        results = sorted(self.search_web(f'{movie.title} movie subtitles transcript'), key=self._transcript_rank)
        for url in results[:6]:
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException:
                continue
            body = response.text
            content_type = response.headers.get("content-type", "")
            if any(token in content_type for token in ("text/plain", "application/x-subrip", "text/vtt")) or url.endswith((".srt", ".vtt", ".txt")):
                parsed = self.parse_subtitle_text(body, source=url)
                if parsed:
                    return parsed
            extracted = self.extract_transcript_from_html(body, source=url)
            if extracted:
                return extracted
        return []

    def fetch_movie_metadata(self, movie: MovieIdentity) -> dict:
        metadata: dict[str, object] = {"title": movie.title}
        try:
            response = self.session.get(WIKIPEDIA_SUMMARY.format(title=quote_plus(movie.title)), timeout=self.timeout)
            if response.ok:
                payload = response.json()
                metadata.update(
                    {
                        "summary": payload.get("extract"),
                        "description": payload.get("description"),
                        "content_urls": payload.get("content_urls", {}),
                    }
                )
        except requests.RequestException:
            pass
        metadata["web_results"] = self.search_web(f"{movie.title} movie trivia")[:5]
        return metadata

    def synthetic_transcript_from_metadata(self, movie: MovieIdentity, metadata: dict) -> list[TimedTranscriptChunk]:
        summary = str(metadata.get("summary") or f"{movie.title} is playing.")
        sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", summary) if item.strip()]
        chunks: list[TimedTranscriptChunk] = []
        current = 0.0
        for sentence in sentences:
            chunks.append(TimedTranscriptChunk(start_seconds=current, end_seconds=current + 30.0, text=sentence, source="metadata", confidence=0.15))
            current += 30.0
        return chunks

    def search_web(self, query: str) -> list[str]:
        try:
            response = self.session.get(SEARCH_ENDPOINT, params={"q": query}, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            return []
        hrefs = re.findall(r'nofollow" class="result__a" href="([^"]+)"', response.text)
        results: list[str] = []
        for href in hrefs:
            href = html.unescape(href)
            if "uddg=" in href:
                href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
            href = unquote(href)
            if href.startswith("http") and href not in results:
                results.append(href)
        return results

    def extract_transcript_from_html(self, body: str, source: str) -> list[TimedTranscriptChunk]:
        text = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        transcript_lines = [line for line in lines if 15 <= len(line) <= 220]
        if len(transcript_lines) < 8:
            return []
        chunks: list[TimedTranscriptChunk] = []
        current = 0.0
        for line in transcript_lines[:120]:
            chunks.append(TimedTranscriptChunk(start_seconds=current, end_seconds=current + 12.0, text=line, source=source, confidence=0.35))
            current += 12.0
        return chunks

    @staticmethod
    def is_noise_subtitle_text(text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return True
        return any(re.search(pattern, lowered) for pattern in SUBTITLE_NOISE_PATTERNS)

    def parse_subtitle_text(self, raw: str, source: str) -> list[TimedTranscriptChunk]:
        if "-->" not in raw:
            return self.parse_plaintext(raw, source)
        lines = raw.replace("\ufeff", "").splitlines()
        chunks: list[TimedTranscriptChunk] = []
        idx = 0
        while idx < len(lines):
            line = lines[idx].strip()
            if "-->" not in line:
                idx += 1
                continue
            start_text, end_text = [part.strip() for part in line.split("-->", 1)]
            start = self.parse_timestamp(start_text)
            end = self.parse_timestamp(end_text)
            idx += 1
            text_lines: list[str] = []
            while idx < len(lines) and lines[idx].strip():
                text_lines.append(re.sub(r"<[^>]+>", "", lines[idx]).strip())
                idx += 1
            text = " ".join(part for part in text_lines if part)
            if self.is_noise_subtitle_text(text):
                idx += 1
                continue
            if text and start is not None and end is not None and end >= start:
                chunks.append(TimedTranscriptChunk(start_seconds=start, end_seconds=end, text=text, source=source, confidence=0.95))
            idx += 1
        return chunks

    def parse_plaintext(self, raw: str, source: str) -> list[TimedTranscriptChunk]:
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        lines = [line for line in lines if len(line) >= 10]
        if not lines:
            return []
        chunks: list[TimedTranscriptChunk] = []
        current = 0.0
        for line in lines[:200]:
            chunks.append(TimedTranscriptChunk(start_seconds=current, end_seconds=current + 8.0, text=line, source=source, confidence=0.45))
            current += 8.0
        return chunks

    @staticmethod
    def parse_timestamp(value: str) -> float | None:
        match = re.search(r"(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})", value)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        millis = int(match.group(4))
        return hours * 3600 + minutes * 60 + seconds + millis / 1000

    @staticmethod
    def _transcript_rank(url: str) -> tuple[int, int]:
        lowered = url.lower()
        preferred_score = 0
        for index, domain in enumerate(PREFERRED_TRANSCRIPT_DOMAINS):
            if domain in lowered:
                preferred_score = -10 + index
                break
        transcript_bonus = -5 if any(token in lowered for token in ("subtitle", "transcript", "script")) else 0
        return (preferred_score + transcript_bonus, len(url))
