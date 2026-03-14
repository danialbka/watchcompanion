#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import sys
import time

import requests

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 42142
STATUS_URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8080/requests/status.json"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "codexpass"

session = requests.Session()


def current_state() -> dict:
    response = session.get(STATUS_URL, auth=("", PASSWORD), timeout=2)
    response.raise_for_status()
    payload = response.json()
    meta = payload.get("information", {}).get("category", {}).get("meta", {})
    filename = meta.get("filename") or ""
    title = meta.get("title") or filename
    uri = f"file://{filename}" if filename and not str(filename).startswith("file://") else filename
    return {
        "active": True,
        "playing": payload.get("state") == "playing",
        "paused": payload.get("state") == "paused",
        "state": payload.get("state") or "stopped",
        "title": title,
        "uri": uri,
        "position": payload.get("position") or 0,
        "length": payload.get("length") or 0,
        "timestamp": payload.get("time") or 0,
        "rate": payload.get("rate") or 1,
        "volume": payload.get("volume") or 0,
        "error": None,
    }


def main() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
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
                    payload = current_state()
                except Exception as exc:  # pragma: no cover
                    payload = {"error": str(exc)}
                client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        return 0
    finally:
        server.close()


if __name__ == "__main__":
    raise SystemExit(main())
