from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import CacheRecord, CommentaryPlan, MovieIdentity


class CacheStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, movie: MovieIdentity) -> Path:
        return self.base_dir / f"{movie.slug()}.json"

    def load(self, movie: MovieIdentity) -> CacheRecord | None:
        path = self.path_for(movie)
        if not path.exists():
            return None
        return CacheRecord.from_dict(json.loads(path.read_text()))

    def save(self, movie: MovieIdentity, commentary: CommentaryPlan) -> CacheRecord:
        now = datetime.now(timezone.utc).isoformat()
        path = self.path_for(movie)
        created_at = now
        if path.exists():
            try:
                created_at = json.loads(path.read_text()).get("created_at", now)
            except Exception:
                created_at = now
        record = CacheRecord(movie=movie, commentary=commentary, created_at=created_at, updated_at=now)
        path.write_text(json.dumps(record.to_dict(), indent=2))
        return record
