from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass(slots=True)
class MovieIdentity:
    title: str
    normalized_title: str
    media_path: str | None = None
    year: int | None = None

    def slug(self) -> str:
        year = f"-{self.year}" if self.year else ""
        return f"{self.normalized_title}{year}"


@dataclass(slots=True)
class TimedTranscriptChunk:
    start_seconds: float
    end_seconds: float
    text: str
    source: str
    confidence: float = 1.0


@dataclass(slots=True)
class TimedComment:
    timestamp_seconds: float
    text: str
    confidence: float = 0.5
    source_window: tuple[float, float] | None = None
    spoiler_level: str = "mild"
    delivered: bool = False


@dataclass(slots=True)
class CommentaryPlan:
    movie: MovieIdentity
    persona: str
    provider: str
    transcript_chunks: list[TimedTranscriptChunk]
    comments: list[TimedComment]
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_seconds: float | None = None


@dataclass(slots=True)
class PlaybackState:
    title: str | None
    media_path: str | None
    current_seconds: float
    total_seconds: float | None
    is_playing: bool
    position: float | None = None
    event_id: int | None = None


@dataclass(slots=True)
class CacheRecord:
    movie: MovieIdentity
    commentary: CommentaryPlan
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "movie": asdict(self.movie),
            "commentary": {
                "movie": asdict(self.commentary.movie),
                "persona": self.commentary.persona,
                "provider": self.commentary.provider,
                "transcript_chunks": [asdict(chunk) for chunk in self.commentary.transcript_chunks],
                "comments": [asdict(comment) for comment in self.commentary.comments],
                "metadata": self.commentary.metadata,
                "runtime_seconds": self.commentary.runtime_seconds,
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheRecord":
        movie = MovieIdentity(**data["movie"])
        commentary_data = data["commentary"]
        commentary = CommentaryPlan(
            movie=MovieIdentity(**commentary_data["movie"]),
            persona=commentary_data["persona"],
            provider=commentary_data["provider"],
            transcript_chunks=[TimedTranscriptChunk(**item) for item in commentary_data.get("transcript_chunks", [])],
            comments=[TimedComment(**item) for item in commentary_data.get("comments", [])],
            metadata=commentary_data.get("metadata", {}),
            runtime_seconds=commentary_data.get("runtime_seconds"),
        )
        return cls(movie=movie, commentary=commentary, created_at=data["created_at"], updated_at=data["updated_at"])


def normalize_title(value: str) -> str:
    stripped = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    collapsed = "-".join(part for part in stripped.split("-") if part)
    return collapsed or "movie"


RELEASE_STOP_WORDS = {
    "2160p", "1080p", "720p", "480p", "webrip", "web-dl", "webdl", "bluray", "brrip", "dvdrip",
    "x264", "x265", "h264", "h265", "hevc", "aac", "aac5", "dts", "yts", "ytsmx", "proper",
    "repack", "extended", "remastered", "unrated", "ac3", "10bit"
}


def infer_title_from_path(path: str | Path) -> str:
    stem = Path(path).stem
    normalized = re.sub(r"[._\-\[\]\(\)]+", " ", stem)
    parts = [part for part in normalized.split() if part]
    title_parts: list[str] = []
    seen_year = False
    for part in parts:
        lowered = part.lower()
        compact = re.sub(r"[^a-z0-9]", "", lowered)
        if re.fullmatch(r"(?:19|20)\d{2}", part):
            title_parts.append(part)
            seen_year = True
            break
        if lowered in RELEASE_STOP_WORDS or compact in RELEASE_STOP_WORDS:
            break
        if re.fullmatch(r"\d{3,4}p", lowered):
            break
        title_parts.append(part)
    if not title_parts:
        title_parts = parts
    cleaned = " ".join(title_parts).strip()
    if seen_year:
        return cleaned
    return cleaned.title() or Path(path).stem.title()
