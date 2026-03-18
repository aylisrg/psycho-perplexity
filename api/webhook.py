"""
Vercel Serverless Function — Telegram Webhook.
Принимает обновления от Telegram, обрабатывает и отвечает.
"""
import json
import logging
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler
import httpx

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import (
    TELEGRAM_BOT_TOKEN,
    BOT_PASSWORD,
    WEBHOOK_SECRET,
    VOICE_ENABLED,
)
from core.therapist import process_message, end_session, switch_model, get_memory_summary
from core.voice import speech_to_text, text_to_speech_buffer
from core.ai_provider import list_providers
from storage.supabase_client import (
    get_or_create_profile,
    is_authenticated,
    set_authenticated,
    get_user_preferences,
    update_profile_preferences,
    create_session,
    get_active_session,
    get_session_history,
    get_knowledge,
    add_knowledge,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ── Telegram API helpers ──

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
    """Отправить текстовое сообщение."""
    # Разбиваем длинные сообщения
    max_len = 4000
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]
    for chunk in chunks:
        try:
            httpx.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
            }, timeout=30)
        except Exception:
            # Fallback без parse_mode (на случай если Markdown сломался)
            httpx.post(f"{TELEGRAM_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": chunk,
            }, timeout=30)


def send_voice(chat_id: int, voice_buffer):
    """Отправить голосовое сообщение."""
    httpx.post(
        f"{TELEGRAM_API}/sendVoice",
        data={"chat_id": chat_id},
        files={"voice": ("voice.ogg", voice_buffer, "audio/ogg")},
        timeout=60,
    )


def send_chat_action(chat_id: int, action: str = "typing"):
    httpx.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": action,
    }, timeout=10)


def send_inline_keyboard(chat_id: int, text: str, keyboard: list):
    httpx.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard},
    }, timeout=30)


def answer_callback_query(callback_id: str, text: str = ""):
    httpx.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text,
    }, timeout=10)


def edit_message_text(chat_id: int, message_id: int, text: str):
    httpx.post(f"{TELEGRAM_API}/editMessageText", json={
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=30)


def get_file_url(file_id: str) -> str:
    """Получить URL файла для скачивания."""
    resp = httpx.get(f"{TELEGRAM_API}/getFile", params={"file_id": file_id}, timeout=30)
    file_path = resp.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"


# ── Проверка доступа (по паролю) ──

def check_auth(user_id: int) -> bool:
    """Проверить, авторизован ли пользователь (пароль уже введён ранее)."""
    if not BOT_PASSWORD:
        return True  # Пароль не задан — доступ открыт
    return is_authenticated(user_id)


def try_password(user_id: int, first_name: str, text: str) -> bool:
    """Проверить пароль. Если верный — запомнить пользователя навсегда."""
    if text.strip() == BOT_PASSWORD:
        set_authenticated(user_id, first_name)
        return True
    return False


# ── Обработка команд ──

def handle_start(chat_id: int, user_id: int, first_name: str):
    get_or_create_profile(user_id, first_name)
    send_message(chat_id, (
        f"Привет, {first_name} 👋\n\n"
        "Я — Алекс, твой приватный психотерапевт.\n\n"
        "Я работаю в интегративном подходе: КПТ, ACT, DBT, "
        "психодинамика, майндфулнес — адаптируюсь под твой запрос.\n\n"
        "Можешь писать мне текстом или отправлять голосовые.\n\n"
        "*Команды:*\n"
        "/newsession — новая сессия\n"
        "/endsession — завершить с резюме\n"
        "/model — переключить AI-модель\n"
        "/voice — вкл/выкл голосовые ответы\n"
        "/memory — что я помню\n"
        "/history — история сессий\n"
        "/help — помощь\n\n"
        "Расскажи, как у тебя дела?"
    ))


def handle_new_session(chat_id: int, user_id: int):
    active = get_active_session(user_id)
    if active:
        end_session(user_id)
    create_session(user_id)
    send_message(chat_id, "🆕 Новая сессия начата.\n\nКак ты себя чувствуешь сегодня?")


def handle_end_session(chat_id: int, user_id: int):
    send_chat_action(chat_id, "typing")
    result = end_session(user_id)
    send_message(chat_id, result)


def handle_model(chat_id: int, user_id: int):
    providers = list_providers()
    keyboard = []
    for p in providers:
        for model in p["models"]:
            keyboard.append([{
                "text": f"{p['name']}: {model}",
                "callback_data": f"model:{p['key']}:{model}",
            }])

    prefs = get_user_preferences(user_id)
    current = f"{prefs.get('ai_provider', '?')} / {prefs.get('ai_model', 'default')}"
    send_inline_keyboard(chat_id, f"Текущая модель: *{current}*\n\nВыбери модель:", keyboard)


def handle_voice_toggle(chat_id: int, user_id: int):
    prefs = get_user_preferences(user_id)
    new_state = not prefs.get("voice_responses", False)
    update_profile_preferences(user_id, {"voice_responses": new_state})
    status = "включены ✅" if new_state else "выключены ❌"
    send_message(chat_id, f"Голосовые ответы {status}")


def handle_memory(chat_id: int, user_id: int):
    summary = get_memory_summary(user_id)
    send_message(chat_id, summary)


def handle_history(chat_id: int, user_id: int):
    sessions = get_session_history(user_id, limit=10)
    if not sessions:
        send_message(chat_id, "Пока нет завершённых сессий.")
        return
    lines = ["📖 *История сессий:*\n"]
    for s in sessions:
        emoji = "🟢" if s["status"] == "active" else "✅"
        date = s["started_at"][:10]
        summary = s.get("summary") or "без резюме"
        if len(summary) > 100:
            summary = summary[:100] + "..."
        lines.append(f"{emoji} {date}: {summary}")
    send_message(chat_id, "\n".join(lines))


def handle_knowledge(chat_id: int):
    keyboard = [
        [{"text": "📋 Список знаний", "callback_data": "kb:list"}],
        [{"text": "➕ Добавить знание", "callback_data": "kb:add"}],
    ]
    send_inline_keyboard(
        chat_id,
        "📚 *База знаний психотерапевта*\n\nЗдесь хранятся терапевтические техники.",
        keyboard,
    )


def handle_help(chat_id: int):
    send_message(chat_id, (
        "🧠 *AI-психотерапевт Алекс*\n\n"
        "*Общение:*\n"
        "• Пиши текстом или отправляй голосовые\n"
        "• Если включены голосовые ответы — отвечу голосом\n\n"
        "*Сессии:*\n"
        "/newsession — начать новую\n"
        "/endsession — завершить с резюме\n\n"
        "*Настройки:*\n"
        "/model — выбрать AI-модель\n"
        "/voice — переключить голос\n\n"
        "*Память:*\n"
        "/memory — что я помню\n"
        "/history — история сессий\n\n"
        "*База знаний:*\n"
        "/knowledge — управление\n\n"
        "Всё конфиденциально."
    ))


# ── Обработка текста и голоса ──

def handle_text(chat_id: int, user_id: int, first_name: str, text: str):
    send_chat_action(chat_id, "typing")
    response = process_message(user_id, text, first_name)

    prefs = get_user_preferences(user_id)
    if prefs.get("voice_responses") and VOICE_ENABLED:
        try:
            send_chat_action(chat_id, "record_voice")
            voice_buf = text_to_speech_buffer(response)
            send_voice(chat_id, voice_buf)
        except Exception as e:
            logger.error(f"TTS error: {e}")
    send_message(chat_id, response)


def handle_voice_message(chat_id: int, user_id: int, first_name: str, file_id: str):
    send_chat_action(chat_id, "typing")
    try:
        file_url = get_file_url(file_id)
        audio_resp = httpx.get(file_url, timeout=30)
        transcribed = speech_to_text(audio_resp.content, "ogg")
    except Exception as e:
        logger.error(f"STT error: {e}")
        send_message(chat_id, "Не удалось распознать голосовое. Попробуй ещё раз или напиши текстом.")
        return

    send_message(chat_id, f"🎤 _{transcribed}_")
    send_chat_action(chat_id, "typing")

    response = process_message(user_id, transcribed, first_name)

    prefs = get_user_preferences(user_id)
    if prefs.get("voice_responses") and VOICE_ENABLED:
        try:
            send_chat_action(chat_id, "record_voice")
            voice_buf = text_to_speech_buffer(response)
            send_voice(chat_id, voice_buf)
        except Exception as e:
            logger.error(f"TTS error: {e}")

    send_message(chat_id, response)


# ── Callback queries ──

def handle_callback(callback_id: str, chat_id: int, message_id: int, user_id: int, data: str):
    answer_callback_query(callback_id)

    if data.startswith("model:"):
        parts = data.split(":")
        result = switch_model(user_id, parts[1], parts[2])
        edit_message_text(chat_id, message_id, result)

    elif data == "kb:list":
        knowledge = get_knowledge()
        if not knowledge:
            edit_message_text(chat_id, message_id, "База знаний пуста.")
            return
        categories = {}
        for k in knowledge:
            cat = k["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(k["title"])
        lines = ["📚 *База знаний:*\n"]
        for cat, titles in categories.items():
            lines.append(f"\n*{cat.upper()}:*")
            for t in titles:
                lines.append(f"  • {t}")
        edit_message_text(chat_id, message_id, "\n".join(lines))

    elif data == "kb:add":
        edit_message_text(chat_id, message_id, (
            "Отправь знание в формате:\n\n"
            "категория | заголовок | содержание | источник\n\n"
            "Категории: cbt, act, dbt, psychodynamic, mindfulness, "
            "crisis, general, techniques, exercises"
        ))


# ── Vercel Handler ──

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Опциональная проверка секрета
            if WEBHOOK_SECRET:
                token = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if token != WEBHOOK_SECRET:
                    self.send_response(403)
                    self.end_headers()
                    return

            update = json.loads(body)
            self._process_update(update)

        except Exception as e:
            logger.error(f"Webhook error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def _process_update(self, update: dict):
        # Callback query (кнопки)
        if "callback_query" in update:
            cq = update["callback_query"]
            user_id = cq["from"]["id"]
            if not check_auth(user_id):
                return
            handle_callback(
                callback_id=cq["id"],
                chat_id=cq["message"]["chat"]["id"],
                message_id=cq["message"]["message_id"],
                user_id=user_id,
                data=cq["data"],
            )
            return

        # Обычное сообщение
        message = update.get("message")
        if not message:
            return

        user = message.get("from", {})
        user_id = user.get("id")
        chat_id = message["chat"]["id"]
        first_name = user.get("first_name", "")

        # Проверка аутентификации
        if not check_auth(user_id):
            text = message.get("text", "")
            # Проверяем, не пароль ли это
            if text and try_password(user_id, first_name, text):
                send_message(chat_id, (
                    f"Добро пожаловать, {first_name}! 🔓\n\n"
                    "Авторизация пройдена. Теперь отправь /start чтобы начать."
                ))
            else:
                send_message(chat_id, "🔐 Это приватный бот. Введите пароль:")
            return

        # Голосовое сообщение
        if "voice" in message:
            handle_voice_message(chat_id, user_id, first_name, message["voice"]["file_id"])
            return

        # Текст
        text = message.get("text", "")
        if not text:
            return

        # Команды
        cmd = text.split()[0].lower().split("@")[0]  # убираем @botname

        if cmd == "/start":
            handle_start(chat_id, user_id, first_name)
        elif cmd == "/help":
            handle_help(chat_id)
        elif cmd == "/newsession":
            handle_new_session(chat_id, user_id)
        elif cmd == "/endsession":
            handle_end_session(chat_id, user_id)
        elif cmd == "/model":
            handle_model(chat_id, user_id)
        elif cmd == "/voice":
            handle_voice_toggle(chat_id, user_id)
        elif cmd == "/memory":
            handle_memory(chat_id, user_id)
        elif cmd == "/history":
            handle_history(chat_id, user_id)
        elif cmd == "/knowledge":
            handle_knowledge(chat_id)
        else:
            # Проверяем, не добавление ли знания (формат с |)
            if "|" in text and text.count("|") >= 2:
                try:
                    parts = text.split("|")
                    add_knowledge(
                        parts[0].strip(), parts[1].strip(),
                        parts[2].strip(), parts[3].strip() if len(parts) > 3 else "",
                    )
                    send_message(chat_id, f"✅ Знание добавлено: {parts[1].strip()}")
                    return
                except Exception:
                    pass

            handle_text(chat_id, user_id, first_name, text)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "Therapist webhook is running"}')
