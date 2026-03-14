from __future__ import annotations

import json
import os
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests

from .models import MovieIdentity, TimedComment, TimedTranscriptChunk
from .prompts import build_generation_prompt

OPENAI_RESPONSES = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES = "https://api.anthropic.com/v1/messages"


@dataclass(slots=True)
class GenerationRequest:
    movie: MovieIdentity
    persona: str
    metadata: dict[str, Any]
    transcript_window: list[TimedTranscriptChunk]
    target_count: int


class CommentaryProvider(ABC):
    @abstractmethod
    def generate(self, request: GenerationRequest) -> list[TimedComment]:
        raise NotImplementedError


class DummyProvider(CommentaryProvider):
    def generate(self, request: GenerationRequest) -> list[TimedComment]:
        if not request.transcript_window:
            return []
        seed = sum(ord(ch) for ch in request.movie.title) + int(request.transcript_window[0].start_seconds)
        rng = random.Random(seed)
        vibe_bank = [
            "Okay wait, that line had main-character-delusion energy.",
            "I love how this scene is trying so hard to look casual.",
            "Tiny detail, huge vibes. I'm into it.",
            "This movie is absolutely cooking right here.",
            "Not me getting emotionally invested already.",
            "That was suspiciously smooth. I do not trust it.",
        ]
        step = max(1, len(request.transcript_window) // max(1, request.target_count))
        comments: list[TimedComment] = []
        for index, chunk in enumerate(request.transcript_window[::step][: request.target_count]):
            choice = vibe_bank[(rng.randint(0, 1000) + index) % len(vibe_bank)]
            offset = min(2.0, max(0.5, (chunk.end_seconds - chunk.start_seconds) / 4))
            comments.append(
                TimedComment(
                    timestamp_seconds=chunk.start_seconds + offset,
                    text=choice,
                    confidence=0.35,
                    source_window=(chunk.start_seconds, chunk.end_seconds),
                    spoiler_level="mild",
                )
            )
        return comments


class OpenAIProvider(CommentaryProvider):
    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for provider=openai")

    def generate(self, request: GenerationRequest) -> list[TimedComment]:
        prompt = build_generation_prompt(request.movie, request.persona, request.transcript_window, request.metadata, request.target_count)
        response = requests.post(
            OPENAI_RESPONSES,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": "You create timed movie companion commentary as strict JSON."}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text", "") or self._collect_output_text(payload)
        return parse_comments_json(text)

    @staticmethod
    def _collect_output_text(payload: dict[str, Any]) -> str:
        texts: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(content["text"])
        return "\n".join(texts)


class AnthropicProvider(CommentaryProvider):
    def __init__(self, model: str = "claude-3-5-haiku-latest") -> None:
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for provider=anthropic")

    def generate(self, request: GenerationRequest) -> list[TimedComment]:
        prompt = build_generation_prompt(request.movie, request.persona, request.transcript_window, request.metadata, request.target_count)
        response = requests.post(
            ANTHROPIC_MESSAGES,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1000,
                "temperature": 0.8,
                "system": "You create timed movie companion commentary as strict JSON.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        return parse_comments_json(text)


class ProviderFactory:
    @staticmethod
    def create(name: str) -> CommentaryProvider:
        normalized = name.lower()
        if normalized == "dummy":
            return DummyProvider()
        if normalized == "openai":
            return OpenAIProvider()
        if normalized == "anthropic":
            return AnthropicProvider()
        raise ValueError(f"unsupported provider: {name}")


def parse_comments_json(raw: str) -> list[TimedComment]:
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return []
    data = json.loads(match.group(0))
    results: list[TimedComment] = []
    for item in data.get("comments", []):
        try:
            results.append(
                TimedComment(
                    timestamp_seconds=float(item["timestamp_seconds"]),
                    text=str(item["text"]).strip(),
                    confidence=float(item.get("confidence", 0.7)),
                    spoiler_level=str(item.get("spoiler_level", "mild")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results
