#!/usr/bin/env python3
"""
Локальный сервер: отдаёт index.html и PNG, принимает POST /api/report
и шлёт сводку в Telegram. Токен только из окружения — не вставляйте в HTML.

Переменные окружения:
  TELEGRAM_BOT_TOKEN  — токен от @BotFather
  TELEGRAM_CHAT_ID    — ID получателя (например 6248342909)
  PORT                — порт (по умолчанию 8765)
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import report_core as rc

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        if self.path == "/api/report":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/report":
            self.send_error(404)
            return

        token = rc.normalize_telegram_token(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        chat_id = rc.normalize_telegram_chat_id(os.environ.get("TELEGRAM_CHAT_ID", ""))
        if not token or not chat_id:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"Server: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment."
            )
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 2_000_000:
            self.send_error(413)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return

        g = payload.get("geolocation") or {}
        lat, lon = g.get("latitude"), g.get("longitude")
        address = None
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            address = rc.reverse_geocode(float(lat), float(lon))

        try:
            rc.send_telegram_report(token, chat_id, payload, address)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8", errors="replace"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")


def main():
    port = int(os.environ.get("PORT", "8765"))
    os.chdir(ROOT)
    httpd = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving http://127.0.0.1:{port}/  (dir: {ROOT})")
    print("POST /api/report -> Telegram (env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
