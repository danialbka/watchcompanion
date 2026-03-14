from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "movie-companion v0.1"


@dataclass(slots=True)
class OpenSubtitleResult:
    subtitle_id: str
    file_id: int
    language: str
    release: str | None
    page_url: str | None = None
    filename: str | None = None
    hearing_impaired: bool = False
    ratings: float | None = None


class OpenSubtitlesClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.api_key = api_key or os.environ.get("OPENSUBTITLES_API_KEY")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        if self.api_key:
            self.session.headers.update({"Api-Key": self.api_key})

    def search(self, query: str, year: int | None = None, language: str = "en") -> list[OpenSubtitleResult]:
        if not self.api_key:
            return []
        params = {"query": query, "languages": language, "type": "movie"}
        if year:
            params["year"] = str(year)
        response = self.session.get(f"{API_BASE}/subtitles", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        results: list[OpenSubtitleResult] = []
        for item in payload.get("data") or []:
            attrs = item.get("attributes") or {}
            files = attrs.get("files") or []
            if not files:
                continue
            file0 = files[0]
            results.append(
                OpenSubtitleResult(
                    subtitle_id=str(item.get("id") or ""),
                    file_id=int(file0.get("file_id")),
                    language=str(attrs.get("language") or language),
                    release=attrs.get("release"),
                    page_url=attrs.get("url"),
                    filename=file0.get("file_name") or attrs.get("release"),
                    hearing_impaired=bool(attrs.get("hearing_impaired")),
                    ratings=float(attrs.get("ratings") or 0) if attrs.get("ratings") is not None else None,
                )
            )
        return results

    def download(self, file_id: int, destination: str | Path) -> Path:
        if not self.api_key:
            raise RuntimeError("OPENSUBTITLES_API_KEY is required to download subtitles")
        response = self.session.post(f"{API_BASE}/download", json={"file_id": file_id}, timeout=self.timeout)
        response.raise_for_status()
        link = response.json()["link"]
        with self.session.get(link, stream=True, timeout=self.timeout) as download:
            download.raise_for_status()
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as handle:
                for chunk in download.iter_content(chunk_size=65536):
                    if chunk:
                        handle.write(chunk)
        return Path(destination)


def pick_best_result(results: list[OpenSubtitleResult], preferred_release_terms: list[str] | None = None) -> OpenSubtitleResult | None:
    preferred_release_terms = [item.lower() for item in (preferred_release_terms or []) if item]
    ranked: list[tuple[float, OpenSubtitleResult]] = []
    for item in results:
        score = 0.0
        release = (item.release or "").lower()
        filename = (item.filename or "").lower()
        if item.language.lower().startswith("en"):
            score += 5
        if not item.hearing_impaired:
            score += 1
        if item.ratings is not None:
            score += min(item.ratings, 10) / 10
        for term in preferred_release_terms:
            if term and (term in release or term in filename):
                score += 3
        ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1] if ranked else None
