from __future__ import annotations

from dataclasses import dataclass, field

from pathlib import Path

from .media import extract_embedded_subtitles, probe_duration_seconds
from .models import CommentaryPlan, PlaybackState


@dataclass(slots=True)
class ScriptedBridge:
    states: list[PlaybackState]
    _index: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._index = 0

    def get_state(self) -> PlaybackState:
        if self._index >= len(self.states):
            raise StopIteration
        state = self.states[self._index]
        self._index += 1
        return state


def build_demo_states(commentary: CommentaryPlan, movie_path: str | None, comment_limit: int = 5) -> list[PlaybackState]:
    runtime = commentary.runtime_seconds or (probe_duration_seconds(movie_path) if movie_path else None) or 600.0
    chosen = commentary.comments[:comment_limit]
    if not chosen:
        chosen = []
    states: list[PlaybackState] = [
        PlaybackState(
            title=commentary.movie.title,
            media_path=movie_path,
            current_seconds=0.0,
            total_seconds=runtime,
            is_playing=True,
            position=0.0,
        )
    ]
    for comment in chosen:
        timestamp = max(0.0, comment.timestamp_seconds)
        states.append(
            PlaybackState(
                title=commentary.movie.title,
                media_path=movie_path,
                current_seconds=timestamp,
                total_seconds=runtime,
                is_playing=True,
                position=min(1.0, timestamp / runtime) if runtime else None,
            )
        )
    if chosen:
        rewind_target = max(0.0, chosen[0].timestamp_seconds - 1.0)
        states.append(
            PlaybackState(
                title=commentary.movie.title,
                media_path=movie_path,
                current_seconds=rewind_target,
                total_seconds=runtime,
                is_playing=True,
                position=min(1.0, rewind_target / runtime) if runtime else None,
            )
        )
        states.append(
            PlaybackState(
                title=commentary.movie.title,
                media_path=movie_path,
                current_seconds=chosen[0].timestamp_seconds,
                total_seconds=runtime,
                is_playing=True,
                position=min(1.0, chosen[0].timestamp_seconds / runtime) if runtime else None,
            )
        )
    return states


def ensure_demo_transcript(movie_path: str | None) -> Path | None:
    if not movie_path:
        return None
    media = Path(movie_path)
    for candidate in (media.with_suffix(".srt"), media.with_suffix(".vtt"), media.with_suffix(".txt")):
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    demo_path = media.with_suffix(".demo.srt")
    extracted = extract_embedded_subtitles(media, demo_path, max_seconds=900)
    return extracted
