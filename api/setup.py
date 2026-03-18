"""
Vercel Serverless Function — Установка Telegram Webhook.
Вызвать один раз после деплоя: GET /api/setup

Также загружает начальную базу знаний.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import TELEGRAM_BOT_TOKEN, WEBHOOK_SECRET
from storage.supabase_client import get_knowledge, add_knowledge
from knowledge.default_knowledge import DEFAULT_KNOWLEDGE

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        results = []

        # 1. Определяем URL webhook
        host = self.headers.get("Host", "")
        proto = self.headers.get("X-Forwarded-Proto", "https")
        webhook_url = f"{proto}://{host}/api/webhook"

        # 2. Устанавливаем webhook
        payload = {"url": webhook_url}
        if WEBHOOK_SECRET:
            payload["secret_token"] = WEBHOOK_SECRET
        payload["allowed_updates"] = ["message", "callback_query"]

        resp = httpx.post(f"{TELEGRAM_API}/setWebhook", json=payload, timeout=30)
        webhook_result = resp.json()
        results.append(f"Webhook: {webhook_result}")

        # 3. Устанавливаем команды бота
        commands = [
            {"command": "start", "description": "Начало"},
            {"command": "newsession", "description": "Новая сессия"},
            {"command": "endsession", "description": "Завершить сессию"},
            {"command": "model", "description": "Выбор AI-модели"},
            {"command": "voice", "description": "Вкл/выкл голосовые ответы"},
            {"command": "memory", "description": "Что я помню о тебе"},
            {"command": "history", "description": "История сессий"},
            {"command": "knowledge", "description": "База знаний"},
            {"command": "help", "description": "Помощь"},
        ]
        resp = httpx.post(
            f"{TELEGRAM_API}/setMyCommands",
            json={"commands": commands},
            timeout=30,
        )
        results.append(f"Commands: {resp.json()}")

        # 4. Загружаем базу знаний (если пусто)
        existing = get_knowledge()
        if not existing:
            for item in DEFAULT_KNOWLEDGE:
                add_knowledge(
                    category=item["category"],
                    title=item["title"],
                    content=item["content"],
                    source=item.get("source", ""),
                )
            results.append(f"Knowledge: loaded {len(DEFAULT_KNOWLEDGE)} entries")
        else:
            results.append(f"Knowledge: already loaded ({len(existing)} entries)")

        # Ответ
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "ok": True,
            "webhook_url": webhook_url,
            "results": results,
        }, ensure_ascii=False).encode())
