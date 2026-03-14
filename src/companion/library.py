from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re

from .models import infer_title_from_path, normalize_title

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm"}


@dataclass(slots=True)
class LibraryMovie:
    path: Path
    title: str
    normalized_title: str
    year: int | None
    size_bytes: int


YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def scan_library(roots: list[str | Path]) -> list[LibraryMovie]:
    movies: list[LibraryMovie] = []
    for root in roots:
        base = Path(root).expanduser()
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            title, year = _parse_title_and_year(path)
            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = 0
            movies.append(
                LibraryMovie(
                    path=path,
                    title=title,
                    normalized_title=normalize_title(title),
                    year=year,
                    size_bytes=size_bytes,
                )
            )
    movies.sort(key=lambda item: (item.title.lower(), str(item.path)))
    return movies


def find_best_local_match(title: str, roots: list[str | Path]) -> LibraryMovie | None:
    candidates = scan_library(roots)
    if not candidates:
        return None
    query_title, query_year = _parse_query_title_and_year(title)
    query_norm = normalize_title(query_title)
    ranked: list[tuple[float, LibraryMovie]] = []
    for item in candidates:
        score = SequenceMatcher(None, query_norm, item.normalized_title).ratio()
        if query_norm in item.normalized_title or item.normalized_title in query_norm:
            score += 0.3
        if query_year and item.year == query_year:
            score += 0.2
        score += min(item.size_bytes / (1024**3), 10) * 0.001
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best_item = ranked[0]
    return best_item if best_score >= 0.55 else None


def _parse_title_and_year(path: Path) -> tuple[str, int | None]:
    stem = path.stem.replace("_", " ").replace(".", " ")
    year_match = YEAR_RE.search(stem)
    year = int(year_match.group(0)) if year_match else None
    title = infer_title_from_path(path)
    return title, year


def _parse_query_title_and_year(title: str) -> tuple[str, int | None]:
    year_match = YEAR_RE.search(title)
    year = int(year_match.group(0)) if year_match else None
    cleaned = title.replace("(", " ").replace(")", " ")
    return " ".join(part for part in cleaned.split() if not YEAR_RE.fullmatch(part)), year
