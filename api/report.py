"""Vercel Serverless: POST /api/report -> Telegram."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

import report_core as rc


class handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        token = rc.normalize_telegram_token(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        chat_id = rc.normalize_telegram_chat_id(os.environ.get("TELEGRAM_CHAT_ID", ""))
        if not token or not chat_id:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(
                b"Server: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Vercel env."
            )
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 2_000_000:
            self.send_response(413)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
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
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8", errors="replace"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"OK")
