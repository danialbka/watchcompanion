from __future__ import annotations

import json
import subprocess
from pathlib import Path


TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "webvtt", "mov_text"}


def probe_duration_seconds(video_path: str | Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return None


def probe_subtitle_streams(video_path: str | Path) -> list[dict]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index,codec_name:stream_tags=language,title",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return []
    return payload.get("streams", [])


def choose_subtitle_stream(streams: list[dict], language: str = "eng") -> int | None:
    preferred = None
    tokens = {language.lower(), language[:2].lower(), "english", "en", "eng"}
    for stream in streams:
        codec = str(stream.get("codec_name") or "").lower()
        if codec not in TEXT_SUBTITLE_CODECS:
            continue
        tags = stream.get("tags") or {}
        stream_language = str(tags.get("language") or "").lower()
        stream_title = str(tags.get("title") or "").lower()
        score = 0
        if stream_language in tokens or any(token in stream_language for token in tokens):
            score += 200
        if any(token in stream_title for token in tokens):
            score += 80
        if "forced" in stream_title:
            score -= 100
        if "sdh" in stream_title:
            score -= 10
        candidate = (score, int(stream.get("index", -1)))
        if preferred is None or candidate[0] > preferred[0]:
            preferred = candidate
    return preferred[1] if preferred and preferred[1] >= 0 else None


def extract_embedded_subtitles(video_path: str | Path, output_path: str | Path, language: str = "eng", max_seconds: float | None = None) -> Path | None:
    streams = probe_subtitle_streams(video_path)
    stream_index = choose_subtitle_stream(streams, language=language)
    if stream_index is None:
        return None
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
    ]
    if max_seconds is not None:
        command.extend(["-t", str(max_seconds)])
    command.extend(["-map", f"0:{stream_index}", str(output)])
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    return output if result.returncode == 0 and output.exists() else None
