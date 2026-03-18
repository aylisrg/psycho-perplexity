"""
Health check endpoint.
GET /api/health
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ANTHROPIC_API_KEY, OPENAI_API_KEY, SUPABASE_URL, TELEGRAM_BOT_TOKEN


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        checks = {
            "telegram_token": bool(TELEGRAM_BOT_TOKEN),
            "supabase": bool(SUPABASE_URL),
            "anthropic": bool(ANTHROPIC_API_KEY),
            "openai": bool(OPENAI_API_KEY),
        }
        all_ok = all(checks.values())

        self.send_response(200 if all_ok else 503)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok" if all_ok else "missing_config",
            "checks": checks,
        }).encode())
