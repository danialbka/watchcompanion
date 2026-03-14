from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import requests


@dataclass(slots=True)
class CatalogMovie:
    imdb_id: str
    title: str
    year: int | None = None
    released_at: str | None = None
    description: str | None = None
    poster: str | None = None
    catalog: str | None = None


class CinemetaClient:
    BASE_URL = "https://v3-cinemeta.strem.io"

    def __init__(self, timeout_seconds: float = 15.0, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.session.headers.setdefault("User-Agent", "movie-companion/0.1 (+catalog-search)")

    def discover_movies(self, catalog: str = "new", *, search: str | None = None, skip: int = 0) -> list[CatalogMovie]:
        if search:
            path = f"/catalog/movie/top/search={quote(search)}.json"
            result_catalog = "search"
        else:
            extra = f"/skip={skip}" if skip else ""
            path = f"/catalog/movie/{catalog}{extra}.json"
            result_catalog = catalog
        response = self.session.get(f"{self.BASE_URL}{path}", timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        return [self._movie_from_payload(item, catalog=result_catalog) for item in payload.get("metas") or []]

    @staticmethod
    def _movie_from_payload(payload: dict, *, catalog: str) -> CatalogMovie:
        imdb_id = str(payload.get("imdb_id") or payload.get("id") or "")
        title = str(payload.get("name") or imdb_id)
        released_at = payload.get("released")
        return CatalogMovie(
            imdb_id=imdb_id,
            title=title,
            year=_infer_year(payload),
            released_at=str(released_at) if released_at else None,
            description=payload.get("description"),
            poster=payload.get("poster"),
            catalog=catalog,
        )


def _infer_year(payload: dict) -> int | None:
    release_info = payload.get("releaseInfo")
    if isinstance(release_info, str):
        trimmed = release_info.strip()
        if len(trimmed) >= 4 and trimmed[:4].isdigit():
            return int(trimmed[:4])
    released = payload.get("released")
    if isinstance(released, str):
        try:
            return datetime.fromisoformat(released.replace("Z", "+00:00")).year
        except ValueError:
            return None
    return None
