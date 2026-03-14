#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def infer_cache_path(movie_path: Path) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from companion.models import infer_title_from_path, normalize_title

    title = infer_title_from_path(movie_path)
    slug = normalize_title(title)
    return Path.home() / '.cache' / 'movie-companion' / f'{slug}.json'


def start_bridge(port: int, movie_path: Path, timestamps: list[float], title: str) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()

    def run() -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', port))
        server.listen(5)
        served = 0
        try:
            while not stop.is_set():
                server.settimeout(0.2)
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    _ = conn.recv(1024)
                    ts = timestamps[min(served, len(timestamps) - 1)]
                    payload = {
                        'title': title,
                        'uri': f'file://{movie_path}',
                        'timestamp': ts,
                        'length': max(timestamps[-1] + 60, 3600),
                        'playing': True,
                        'state': 'playing',
                        'position': 0.0,
                    }
                    conn.sendall((json.dumps(payload) + '\n').encode('utf-8'))
                    served += 1
        finally:
            server.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, stop


def main() -> int:
    parser = argparse.ArgumentParser(description='Run an end-to-end self-test against a local movie file using a fake VLC bridge.')
    parser.add_argument('movie_path')
    parser.add_argument('--provider', default='dummy')
    parser.add_argument('--port', type=int, default=43123)
    parser.add_argument('--count', type=int, default=4, help='How many timed comments to simulate.')
    args = parser.parse_args()

    movie_path = Path(args.movie_path).expanduser().resolve()
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'

    precompute = subprocess.run(
        ['movie-companion', str(movie_path), '--provider', args.provider, '--precompute-only'],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    sys.stdout.write(precompute.stdout)
    sys.stderr.write(precompute.stderr)
    if precompute.returncode != 0:
        return precompute.returncode

    cache_path = infer_cache_path(movie_path)
    payload = json.loads(cache_path.read_text())
    commentary = payload['commentary']
    title = commentary['movie']['title']
    timestamps = [float(item['timestamp_seconds']) for item in commentary['comments'][: max(1, args.count)]]
    if not timestamps:
        print('No comments generated; cannot self-test watch loop.', file=sys.stderr)
        return 1

    thread, stop = start_bridge(args.port, movie_path, timestamps, title)
    time.sleep(0.2)
    env['MOVIE_COMPANION_VLC_PORT'] = str(args.port)
    env['MOVIE_COMPANION_POLL_INTERVAL'] = '0.05'
    watch = subprocess.run(
        ['timeout', '0.6s', 'movie-companion', str(movie_path), '--provider', args.provider],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stop.set()
    thread.join(timeout=1)

    sys.stdout.write(watch.stdout)
    sys.stderr.write(watch.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
