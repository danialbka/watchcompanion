from __future__ import annotations

import json
from textwrap import dedent

from .models import MovieIdentity, TimedTranscriptChunk


def build_generation_prompt(movie: MovieIdentity, persona: str, transcript_window: list[TimedTranscriptChunk], metadata: dict, target_count: int) -> str:
    transcript_payload = [
        {
            "start_seconds": round(chunk.start_seconds, 1),
            "end_seconds": round(chunk.end_seconds, 1),
            "text": chunk.text,
        }
        for chunk in transcript_window
    ]
    return dedent(
        f"""
        Create timed companion commentary for the movie {movie.title!r}.

        Persona instructions:
        {persona}

        Output strict JSON with this shape:
        {{
          "comments": [
            {{
              "timestamp_seconds": number,
              "text": string,
              "confidence": number,
              "spoiler_level": "none" | "mild"
            }}
          ]
        }}

        Rules:
        - Produce at most {target_count} comments for this window.
        - Comments should feel like watching the movie with an affectionate, funny partner.
        - Keep each comment under 22 words.
        - Mild teasing is allowed; explicit future spoilers are not.
        - Reference only the current or earlier transcript context.
        - Place comment timestamps inside the provided transcript window.

        Movie metadata:
        {json.dumps(metadata, ensure_ascii=False)}

        Transcript window:
        {json.dumps(transcript_payload, ensure_ascii=False)}
        """
    ).strip()
