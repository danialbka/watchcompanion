#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import sys
import time

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 42142
RC_HOST = sys.argv[2] if len(sys.argv) > 2 else "172.20.64.1"
RC_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 42150
MOVIE_PATH = sys.argv[4] if len(sys.argv) > 4 else ""


def _drain(sock: socket.socket, wait: float = 0.2) -> str:
    sock.settimeout(wait)
    chunks: list[bytes] = []
    while True:
        try:
            block = sock.recv(4096)
        except socket.timeout:
            break
        if not block:
            break
        chunks.append(block)
    return b"".join(chunks).decode("utf-8", errors="ignore")


def _query_rc() -> dict:
    with socket.create_connection((RC_HOST, RC_PORT), timeout=2) as sock:
        _drain(sock, 0.3)
        values: dict[str, str] = {}
        for command in ("get_time", "get_length", "is_playing"):
            sock.sendall((command + "\n").encode("utf-8"))
            time.sleep(0.15)
            values[command] = _drain(sock, 0.3)
    current_seconds = _last_int(values.get("get_time", ""))
    total_seconds = _last_int(values.get("get_length", ""))
    is_playing = _last_int(values.get("is_playing", "")) == 1
    return {
        "active": True,
        "playing": is_playing,
        "paused": not is_playing,
        "state": "playing" if is_playing else "paused",
        "title": MOVIE_PATH.rsplit("/", 1)[-1] if MOVIE_PATH else "Windows VLC",
        "uri": MOVIE_PATH,
        "position": (current_seconds / total_seconds) if total_seconds else 0,
        "length": total_seconds,
        "timestamp": current_seconds,
        "rate": 1,
        "volume": 0,
        "error": None,
    }


def _last_int(raw: str) -> int:
    for line in reversed([line.strip() for line in raw.splitlines() if line.strip()]):
        if line.lstrip("-").isdigit():
            return int(line)
    return 0


def main() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(5)
    server.settimeout(0.5)
    try:
        while True:
            try:
                client, _ = server.accept()
            except socket.timeout:
                continue
            with client:
                try:
                    _ = client.recv(1024)
                    payload = _query_rc()
                except Exception as exc:
                    payload = {"error": str(exc)}
                client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        return 0
    finally:
        server.close()


if __name__ == "__main__":
    raise SystemExit(main())
