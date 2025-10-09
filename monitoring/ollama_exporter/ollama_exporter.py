#!/usr/bin/env python3
"""Simple Ollama availability exporter.

Exposes Prometheus metrics for configured Ollama instances defined via
environment variable OLLAMA_TARGETS (comma separated URLs).

Metrics:
  ollama_instance_up{instance="<name>"} 1|0
  ollama_instances_online <count>

This avoids scraping Ollama directly (no native /metrics) and gives the
dashboard a reliable source for the number of online instances.
"""
from __future__ import annotations

import os
import socket
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Tuple
from urllib.parse import urlparse
import http.client


def parse_targets(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


def check_target(url: str, timeout: float) -> Tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or ''
    port = parsed.port or 80
    name = host  # Use hostname as instance label
    path = parsed.path or '/'
    if path == '/':
        path = '/api/tags'  # a lightweight Ollama endpoint
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request('GET', path)
        resp = conn.getresponse()
        up = 1 if resp.status < 500 else 0
    except Exception:  # noqa: BLE001 - exported as failure metric
        up = 0
    return name, up


class MetricsCache:
    def __init__(self, ttl: float = 5.0) -> None:
        self.ttl = ttl
        self._lock = threading.Lock()
        self._expires = 0.0
        self._data = ''

    def get(self, builder) -> str:
        now = time.time()
        with self._lock:
            if now < self._expires:
                return self._data
        data = builder()
        with self._lock:
            self._data = data
            self._expires = time.time() + self.ttl
        return data


TARGETS = parse_targets(os.getenv('OLLAMA_TARGETS'))
REQUEST_TIMEOUT = float(os.getenv('REQUEST_TIMEOUT', '2'))
CACHE_TTL = float(os.getenv('CACHE_TTL', '5'))
PORT = int(os.getenv('EXPORTER_PORT', '9105'))

cache = MetricsCache(ttl=CACHE_TTL)


def build_metrics() -> str:
    lines = [
        '# HELP ollama_instance_up 1 if the Ollama instance responds to a basic API request, else 0',
        '# TYPE ollama_instance_up gauge',
    ]
    up_total = 0
    for target in TARGETS:
        name, up = check_target(target, REQUEST_TIMEOUT)
        up_total += up
        lines.append(f'ollama_instance_up{{instance="{name}"}} {up}')
    lines += [
        '# HELP ollama_instances_online Count of responding Ollama instances',
        '# TYPE ollama_instances_online gauge',
        f'ollama_instances_online {up_total}',
    ]
    return '\n'.join(lines) + '\n'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != '/metrics':
            self.send_response(302)
            self.send_header('Location', '/metrics')
            self.end_headers()
            return
        body = cache.get(build_metrics)
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):  # noqa: D401
        # Suppress default noisy logging, minimal stderr line
        sys.stderr.write("[ollama_exporter] " + fmt % args + "\n")


def main() -> int:
    if not TARGETS:
        print('ERROR: OLLAMA_TARGETS not configured', file=sys.stderr)
        return 1
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Ollama exporter listening on :{PORT} for targets: {', '.join(TARGETS)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':  # pragma: no cover
    raise SystemExit(main())
