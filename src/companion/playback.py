from __future__ import annotations

import json
import socket
from dataclasses import dataclass

from .models import PlaybackState


class PlaybackError(RuntimeError):
    pass


@dataclass(slots=True)
class PlaybackConfig:
    host: str = "127.0.0.1"
    port: int = 42142
    timeout_seconds: float = 1.0


class VLCBridge:
    def __init__(self, config: PlaybackConfig | None = None) -> None:
        self.config = config or PlaybackConfig()

    def get_state(self) -> PlaybackState:
        try:
            payload = self._request("GET_STATE\n")
            data = json.loads(payload)
        except OSError as exc:
            raise PlaybackError(
                f"Unable to reach VLC Companion Bridge at {self.config.host}:{self.config.port}. Enable the VLC Lua extension from vlc/README.md."
            ) from exc
        except json.JSONDecodeError as exc:
            raise PlaybackError("VLC Companion Bridge returned invalid JSON") from exc
        if data.get("error"):
            raise PlaybackError(str(data["error"]))
        return PlaybackState(
            title=data.get("title") or None,
            media_path=self._normalize_uri(data.get("uri")),
            current_seconds=float(data.get("timestamp") or 0.0),
            total_seconds=float(data.get("length")) if data.get("length") is not None else None,
            is_playing=bool(data.get("playing") or data.get("state") == "playing"),
            position=float(data.get("position")) if data.get("position") is not None else None,
            event_id=None,
        )

    def _request(self, message: str) -> str:
        with socket.create_connection((self.config.host, self.config.port), timeout=self.config.timeout_seconds) as client:
            client.sendall(message.encode("utf-8"))
            client.shutdown(socket.SHUT_WR)
            chunks: list[bytes] = []
            while True:
                block = client.recv(4096)
                if not block:
                    break
                chunks.append(block)
        if not chunks:
            raise PlaybackError("VLC bridge returned no data")
        return b"".join(chunks).decode("utf-8").strip()

    @staticmethod
    def _normalize_uri(uri: str | None) -> str | None:
        if not uri:
            return None
        if uri.startswith("file://"):
            return uri.removeprefix("file://")
        return uri
