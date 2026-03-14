from __future__ import annotations

import time
from dataclasses import dataclass

from .cache import CacheStore
from .config import AppConfig, StartRequest
from .generator import CommentaryPlanner
from .ingest import ContextIngestor
from .models import CommentaryPlan
from .playback import PlaybackConfig, VLCBridge
from .providers import ProviderFactory
from .tts import NoopSpeechAdapter, SpeechAdapter, SpeechRequest


@dataclass(slots=True)
class SessionArtifacts:
    commentary: CommentaryPlan
    cached: bool


class SessionRunner:
    def __init__(self, config: AppConfig, bridge: VLCBridge | None = None, ingestor: ContextIngestor | None = None, speech: SpeechAdapter | None = None) -> None:
        self.config = config
        self.cache = CacheStore(config.cache_dir)
        self.bridge = bridge or VLCBridge(
            PlaybackConfig(host=config.vlc_host, port=config.vlc_port, timeout_seconds=config.vlc_timeout_seconds)
        )
        self.ingestor = ingestor or ContextIngestor()
        self.speech = speech or NoopSpeechAdapter()

    def prepare(self, request: StartRequest) -> SessionArtifacts:
        movie = request.movie_identity()
        cached = self.cache.load(movie)
        if cached and cached.commentary.persona == request.persona and cached.commentary.provider == request.provider:
            return SessionArtifacts(commentary=cached.commentary, cached=True)
        provider = ProviderFactory.create(request.provider)
        ingested = self.ingestor.ingest(movie)
        if self.config.style_profile_name:
            ingested.metadata["style_profile"] = self.config.style_profile_name
        if self.config.style_profile_path:
            ingested.metadata["style_profile_path"] = str(self.config.style_profile_path)
        commentary = CommentaryPlanner(provider=provider, density="medium").build_plan(
            movie=movie,
            transcript_chunks=ingested.transcript_chunks,
            metadata=ingested.metadata,
            persona=request.persona,
        )
        self.cache.save(movie, commentary)
        return SessionArtifacts(commentary=commentary, cached=False)

    def watch(self, commentary: CommentaryPlan, once: bool = False) -> None:
        delivered_ids: set[int] = set()
        last_timestamp: float | None = None
        print(f"Watching {commentary.movie.title} with provider={commentary.provider}. Press Ctrl+C to stop.")
        while True:
            try:
                state = self.bridge.get_state()
            except StopIteration:
                break
            if state.total_seconds and not commentary.runtime_seconds:
                commentary.runtime_seconds = state.total_seconds
            if last_timestamp is not None and state.current_seconds + self.config.seek_backtrack_seconds < last_timestamp:
                delivered_ids = {idx for idx in delivered_ids if commentary.comments[idx].timestamp_seconds < max(0.0, state.current_seconds - 5.0)}
            if state.is_playing:
                self._emit_due_comments(commentary, state.current_seconds, delivered_ids)
            last_timestamp = state.current_seconds
            if once:
                break
            time.sleep(self.config.poll_interval)

    def _emit_due_comments(self, commentary: CommentaryPlan, current_seconds: float, delivered_ids: set[int]) -> None:
        reset_cutoff = max(0.0, current_seconds - 20.0)
        for index, comment in enumerate(commentary.comments):
            if comment.timestamp_seconds < reset_cutoff:
                delivered_ids.discard(index)
            if index in delivered_ids:
                continue
            if abs(comment.timestamp_seconds - current_seconds) <= self.config.reveal_window_seconds:
                print(f"[{self._format_seconds(comment.timestamp_seconds)}] {comment.text}")
                delivered_ids.add(index)
                if self.config.voice:
                    self.speech.speak(SpeechRequest(text=comment.text, voice=self.config.voice))

    @staticmethod
    def _format_seconds(value: float) -> str:
        total = int(value)
        hours, rem = divmod(total, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
