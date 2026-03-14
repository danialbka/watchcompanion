from __future__ import annotations

from math import ceil

from .models import CommentaryPlan, MovieIdentity, TimedComment, TimedTranscriptChunk
from .providers import CommentaryProvider, GenerationRequest


class CommentaryPlanner:
    def __init__(self, provider: CommentaryProvider, density: str = "medium") -> None:
        self.provider = provider
        self.density = density

    def build_plan(self, movie: MovieIdentity, transcript_chunks: list[TimedTranscriptChunk], metadata: dict, persona: str) -> CommentaryPlan:
        comments: list[TimedComment] = []
        for window in self.window_chunks(transcript_chunks):
            generated = self.provider.generate(
                GenerationRequest(
                    movie=movie,
                    persona=persona,
                    metadata=metadata,
                    transcript_window=window,
                    target_count=self.target_count(len(window)),
                )
            )
            for comment in generated:
                if comment.source_window is None and window:
                    comment.source_window = (window[0].start_seconds, window[-1].end_seconds)
            comments.extend(generated)
        comments.sort(key=lambda item: item.timestamp_seconds)
        comments = self.deduplicate(comments)
        return CommentaryPlan(
            movie=movie,
            persona=persona,
            provider=type(self.provider).__name__.replace("Provider", "").lower(),
            transcript_chunks=transcript_chunks,
            comments=comments,
            metadata=metadata,
            runtime_seconds=transcript_chunks[-1].end_seconds if transcript_chunks else None,
        )

    def window_chunks(self, chunks: list[TimedTranscriptChunk], window_seconds: int = 180) -> list[list[TimedTranscriptChunk]]:
        if not chunks:
            return []
        windows: list[list[TimedTranscriptChunk]] = []
        current: list[TimedTranscriptChunk] = []
        current_start = chunks[0].start_seconds
        for chunk in chunks:
            if current and chunk.end_seconds - current_start > window_seconds:
                windows.append(current)
                current = []
                current_start = chunk.start_seconds
            current.append(chunk)
        if current:
            windows.append(current)
        return windows

    def target_count(self, chunk_count: int) -> int:
        density = {"sparse": 1, "medium": 2, "high": 3}.get(self.density, 2)
        return max(1, min(density, ceil(chunk_count / 8)))

    @staticmethod
    def deduplicate(comments: list[TimedComment]) -> list[TimedComment]:
        deduped: list[TimedComment] = []
        seen: set[tuple[int, str]] = set()
        for comment in comments:
            key = (int(comment.timestamp_seconds), comment.text.lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(comment)
        return deduped
