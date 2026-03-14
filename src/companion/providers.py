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
        style_hint = " ".join(
            str(item)
            for item in [
                request.persona,
                request.metadata.get("style_profile", ""),
                request.metadata.get("voice_summary", ""),
                request.metadata.get("commentary_style", ""),
            ]
        ).lower()
        casual_mode = any(token in style_hint for token in {"whatsapp", "casual", "funny friend", "close funny friend"})
        step = max(1, len(request.transcript_window) // max(1, request.target_count))
        comments: list[TimedComment] = []
        for index, chunk in enumerate(request.transcript_window[::step][: request.target_count]):
            window_text = " ".join(item.text for item in request.transcript_window[max(0, index - 1): index + 2]).strip()
            choice = self._build_comment(chunk.text, window_text, rng, casual_mode=casual_mode)
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

    def _build_comment(self, chunk_text: str, window_text: str, rng: random.Random, *, casual_mode: bool) -> str:
        normalized = re.sub(r"\s+", " ", chunk_text).strip()
        lowered = normalized.lower()
        context = re.sub(r"\s+", " ", window_text).strip()
        if casual_mode:
            openers = [
                "bro",
                "nah",
                "man",
                "okay wait",
                "lmao",
                "see this is exactly why",
            ]
            generic = [
                "this already feels like a terrible decision with good lighting.",
                "everyone is talking like consequences are optional. dangerous vibe.",
                "the confidence in this scene is way too high for the amount of bad energy present.",
                "this whole moment feels like the movie quietly telling us nobody here is about to act sensible.",
                "i'm sorry but the vibes are cooked already.",
            ]
        else:
            openers = [
                "Okay,",
                "Wait,",
                "Honestly,",
                "That said,",
            ]
            generic = [
                "this feels like a very bad idea presented with a little too much confidence.",
                "the energy here is suspiciously calm for a scene that clearly has consequences.",
                "someone in this scene is making a choice they will absolutely regret.",
                "the vibe just shifted in a way I do not trust at all.",
            ]

        if "no!" in lowered or lowered == "no":
            return "bro we opened on a guy yelling no. this movie is not easing us in at all." if casual_mode else "We are opening on full panic already; subtlety has left the building."
        if "game" in lowered:
            return "nah the second a horror movie starts giving me game lore i'm locked in. evil with patch notes is always a problem." if casual_mode else "The moment horror gives us game rules, the threat gets instantly more interesting."
        if "don't freak" in lowered or "dont freak" in lowered:
            return "the phrase 'don't freak' has literally never arrived early enough to help anybody." if casual_mode else "Any version of 'don't freak out' means the calm part is already over."
        if "stay alive" in lowered:
            return "the title drop this early is nasty work. i already don't trust anybody recommending this thing." if casual_mode else "A title drop like that feels less like marketing and more like a warning label."
        if "funeral" in lowered:
            return "why is this movie treating grief like side quest intel. that's so dark it's almost impressive." if casual_mode else "This is such a grim way to turn tragedy into useful information."
        if "bag" in lowered or "stuff" in lowered or "took" in lowered and "bag" in context.lower():
            return "dead person's bag turning into clue storage is such mean little horror admin. bleak but effective." if casual_mode else "Turning someone's belongings into clue delivery is a very cold horror move."
        if "police" in lowered or "cop" in lowered:
            return "i love when the cops show up just to be professionally unconvinced for a while." if casual_mode else "Authority arriving late and skeptical is practically part of the genre contract."
        if "elizabeth" in lowered or "countess" in lowered or "bathory" in lowered:
            return "okay now we're getting haunted history on top of gamer nonsense. this is honestly doing a lot and i respect that." if casual_mode else "Now that the old legend is in play, the whole curse starts to feel much bigger."
        if "door" in lowered or "open" in lowered or "come on" in lowered:
            return "nobody in horror has ever opened a door with the correct amount of fear." if casual_mode else "There is never enough caution around a door in a horror movie."
        if "run" in lowered:
            return "finally some cardio. took long enough honestly." if casual_mode else "At last, someone is treating this like an actual emergency."
        if "sorry" in lowered and len(lowered.split()) <= 4:
            return "oh that's never a good little sentence. that's a last-words-sized apology." if casual_mode else "Short apologies in horror are almost never reassuring."
        if "what" in lowered and "?" in normalized:
            return "yeah no that's the exact tone people use right before the night gets fully cursed." if casual_mode else "Confused disbelief is rarely the end of the problem in scenes like this."
        if normalized:
            snippet = normalized.strip("\"' ")
            if len(snippet) > 72:
                snippet = snippet[:69].rstrip() + "..."
            if casual_mode and rng.random() < 0.45:
                opener = openers[rng.randint(0, len(openers) - 1)]
                return f"{opener} hearing \"{snippet}\" like it's normal is actually crazy."
            if not casual_mode and rng.random() < 0.35:
                opener = openers[rng.randint(0, len(openers) - 1)]
                return f"{opener} hearing \"{snippet}\" said out loud does not improve the situation."
        return generic[rng.randint(0, len(generic) - 1)]


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
