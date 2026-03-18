"""
Конфигурация — загрузка из переменных окружения Vercel.
"""
import os


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# Telegram
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = [
    int(uid.strip())
    for uid in get_env("TELEGRAM_ALLOWED_USERS", "").split(",")
    if uid.strip()
]

# Supabase
SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_SERVICE_KEY")

# AI
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")
CLAUDE_DEFAULT_MODEL = get_env("CLAUDE_DEFAULT_MODEL", "claude-sonnet-4-20250514")

OPENAI_API_KEY = get_env("OPENAI_API_KEY")
OPENAI_DEFAULT_MODEL = get_env("OPENAI_DEFAULT_MODEL", "gpt-4o")

DEFAULT_AI_PROVIDER = get_env("DEFAULT_AI_PROVIDER", "claude")

# Custom provider (OpenRouter, Groq, etc.)
CUSTOM_AI_API_KEY = get_env("CUSTOM_AI_API_KEY")
CUSTOM_AI_BASE_URL = get_env("CUSTOM_AI_BASE_URL")
CUSTOM_AI_NAME = get_env("CUSTOM_AI_NAME", "Custom AI")
CUSTOM_AI_DEFAULT_MODEL = get_env("CUSTOM_AI_DEFAULT_MODEL")
CUSTOM_AI_MODELS = get_env("CUSTOM_AI_MODELS")

# Voice
VOICE_ENABLED = get_env("VOICE_ENABLED", "true").lower() == "true"
TTS_VOICE = get_env("TTS_VOICE", "alloy")

# Session
MAX_CONTEXT_MESSAGES = int(get_env("MAX_CONTEXT_MESSAGES", "50"))
WEBHOOK_SECRET = get_env("WEBHOOK_SECRET", "")
