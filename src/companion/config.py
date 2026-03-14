from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .models import MovieIdentity, infer_title_from_path, normalize_title

DEFAULT_PERSONA = (
    "You are a warm, playful movie companion with affectionate 'watching together' energy. "
    "Be concise, natural, lightly funny, and non-cringe. Mild foreshadowing only; do not explicitly spoil future plot beats."
)


@dataclass(slots=True)
class AppConfig:
    cache_dir: Path
    provider: str
    persona: str
    voice: str | None
    vlc_host: str = "127.0.0.1"
    vlc_port: int = 42142
    poll_interval: float = 1.0
    reveal_window_seconds: float = 2.0
    seek_backtrack_seconds: float = 3.0


@dataclass(slots=True)
class StartRequest:
    movie_path: str | None
    title: str | None
    provider: str
    persona: str
    voice: str | None
    once: bool = False

    def movie_identity(self) -> MovieIdentity:
        if self.title:
            title = self.title
        elif self.movie_path:
            title = infer_title_from_path(self.movie_path)
        else:
            raise ValueError("either movie path or title is required")
        return MovieIdentity(title=title, normalized_title=normalize_title(title), media_path=self.movie_path)


def load_config(provider: str | None = None, persona: str | None = None, voice: str | None = None) -> AppConfig:
    cache_dir = Path(os.environ.get("MOVIE_COMPANION_CACHE_DIR", Path.home() / ".cache" / "movie-companion"))
    return AppConfig(
        cache_dir=cache_dir,
        provider=provider or os.environ.get("MOVIE_COMPANION_PROVIDER", "dummy"),
        persona=persona or os.environ.get("MOVIE_COMPANION_PERSONA", DEFAULT_PERSONA),
        voice=voice or os.environ.get("MOVIE_COMPANION_VOICE"),
        vlc_host=os.environ.get("MOVIE_COMPANION_VLC_HOST", "127.0.0.1"),
        vlc_port=int(os.environ.get("MOVIE_COMPANION_VLC_PORT", "42142")),
        poll_interval=float(os.environ.get("MOVIE_COMPANION_POLL_INTERVAL", "1.0")),
    )
