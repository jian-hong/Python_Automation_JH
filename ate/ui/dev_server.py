"""Serve liquid-glass UI + ensure worker is reachable. Tauri wraps this later."""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import webbrowser
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
PORT = 5174


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        pass


def main() -> None:
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler)
    httpd.daemon_threads = True
    print(f"ATE UI http://127.0.0.1:{PORT}")
    threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    httpd.serve_forever()


if __name__ == "__main__":
    main()
