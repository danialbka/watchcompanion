from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SpeechRequest:
    text: str
    voice: str


class SpeechAdapter:
    def speak(self, request: SpeechRequest) -> None:  # pragma: no cover
        raise NotImplementedError


class NoopSpeechAdapter(SpeechAdapter):
    def speak(self, request: SpeechRequest) -> None:
        return None


class PlaceholderSpeechAdapter(SpeechAdapter):
    def speak(self, request: SpeechRequest) -> None:
        print(f"[tts placeholder:{request.voice}] {request.text}")
