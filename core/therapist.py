"""
Ядро AI-психотерапевта — serverless версия.
"""
import json
import logging
from typing import Optional

from core import ai_provider
from core.config import MAX_CONTEXT_MESSAGES
from core.system_prompt import (
    build_system_prompt,
    MEMORY_EXTRACTION_PROMPT,
    SESSION_SUMMARY_PROMPT,
)
from storage import supabase_client as db

logger = logging.getLogger(__name__)


def process_message(telegram_id: int, user_message: str, user_name: str = "") -> str:
    """
    Обработать сообщение и вернуть ответ терапевта.

    1. Профиль + сессия
    2. Контекст (память + история)
    3. Системный промпт
    4. Ответ AI
    5. Сохранение
    6. Извлечение фактов (периодически)
    """
    # 1. Профиль и сессия
    profile = db.get_or_create_profile(telegram_id, user_name)
    session = db.get_active_session(telegram_id)
    if not session:
        session = db.create_session(telegram_id)

    # 2. Контекст
    prefs = json.loads(profile.get("preferences", "{}"))
    provider_key = prefs.get("ai_provider", "claude")
    ai_model = prefs.get("ai_model") or ""

    memory_facts = db.get_memory_facts(telegram_id)
    session_messages = db.get_session_messages(session["id"], limit=MAX_CONTEXT_MESSAGES)

    # Резюме прошлых сессий
    past_sessions = db.get_session_history(telegram_id, limit=5)
    summaries = [
        s.get("summary", "")
        for s in past_sessions
        if s["id"] != session["id"] and s.get("summary")
    ]
    history_summary = "\n".join(f"- {s}" for s in summaries[-3:]) if summaries else ""

    # База знаний
    knowledge_text = db.get_all_knowledge_for_prompt()

    # 3. Системный промпт
    system_prompt = build_system_prompt(
        memory_facts=memory_facts,
        session_history_summary=history_summary,
        knowledge_base_text=knowledge_text,
    )

    # 4. Сообщения для AI
    messages = [{"role": m["role"], "content": m["content"]} for m in session_messages]
    messages.append({"role": "user", "content": user_message})

    # 5. Ответ
    usage_data = None
    try:
        response, usage_data = ai_provider.chat(
            messages=messages,
            system_prompt=system_prompt,
            provider=provider_key,
            model=ai_model,
        )
    except Exception as e:
        logger.error(f"AI error: {e}")
        response = (
            "Прости, у меня сейчас технические трудности. "
            "Давай попробуем продолжить через минуту."
        )

    # 5.5. Сохраняем usage
    if usage_data:
        try:
            db.save_token_usage(telegram_id, session["id"], usage_data)
        except Exception as e:
            logger.error(f"Token usage save error: {e}")

    # 6. Сохраняем
    db.save_message(session["id"], "user", user_message)
    db.save_message(session["id"], "assistant", response)

    # 7. Извлечение фактов (каждые 10 сообщений)
    total = len(session_messages) + 2
    if total % 10 == 0 and total > 0:
        _extract_memory(telegram_id, session["id"])

    return response


def _extract_memory(telegram_id: int, session_id: int):
    """Извлечь факты из диалога в долгосрочную память."""
    try:
        messages = db.get_session_messages(session_id, limit=20)
        if len(messages) < 4:
            return

        dialogue = "\n".join(
            f"{'Клиент' if m['role'] == 'user' else 'Терапевт'}: {m['content']}"
            for m in messages[-20:]
        )

        known = db.get_memory_facts(telegram_id)
        known_text = "\n".join(f"- [{f['category']}] {f['fact']}" for f in known)

        prompt = MEMORY_EXTRACTION_PROMPT.format(
            dialogue=dialogue,
            known_facts=known_text or "Пока нет известных фактов.",
        )

        result = ai_provider.chat_json(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Ты анализатор диалогов. Извлекаешь факты для памяти терапевта.",
        )

        facts = result if isinstance(result, list) else result.get("facts", []) if isinstance(result, dict) else []
        for fact in facts:
            if isinstance(fact, dict) and "category" in fact and "fact" in fact:
                db.save_memory_fact(
                    telegram_id=telegram_id,
                    category=fact["category"],
                    fact=fact["fact"],
                    importance=fact.get("importance", 5),
                )
    except Exception as e:
        logger.error(f"Memory extraction error: {e}")


def end_session(telegram_id: int) -> str:
    """Завершить сессию с резюме."""
    session = db.get_active_session(telegram_id)
    if not session:
        return "Нет активной сессии."

    messages = db.get_session_messages(session["id"])
    if not messages:
        db.close_session(session["id"])
        return "Сессия закрыта."

    dialogue = "\n".join(
        f"{'Клиент' if m['role'] == 'user' else 'Терапевт'}: {m['content']}"
        for m in messages
    )
    prompt = SESSION_SUMMARY_PROMPT.format(dialogue=dialogue)

    try:
        summary, _usage = ai_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Ты психотерапевт, создающий резюме сессии.",
            temperature=0.3, max_tokens=500,
        )
        if _usage:
            try:
                db.save_token_usage(telegram_id, session["id"], _usage)
            except Exception:
                pass
    except Exception:
        summary = "Резюме не удалось создать."

    _extract_memory(telegram_id, session["id"])
    db.close_session(session["id"], summary=summary)
    return f"Сессия завершена.\n\n📝 Резюме:\n{summary}"


def switch_model(telegram_id: int, provider_key: str, model: str = "") -> str:
    """Переключить AI-модель."""
    providers = ai_provider.list_providers()
    keys = [p["key"] for p in providers]

    if provider_key not in keys:
        lines = "\n".join(f"• {p['key']}: {p['name']} ({', '.join(p['models'])})" for p in providers)
        return f"Доступные провайдеры:\n{lines}"

    info = next(p for p in providers if p["key"] == provider_key)
    if model and model not in info["models"]:
        return f"Доступные модели для {provider_key}: {', '.join(info['models'])}"

    db.update_profile_preferences(telegram_id, {"ai_provider": provider_key, "ai_model": model})
    name = model or info["default_model"]
    return f"✅ Переключено на {info['name']}, модель: {name}"


def get_memory_summary(telegram_id: int) -> str:
    """Сводка памяти."""
    facts = db.get_memory_facts(telegram_id)
    if not facts:
        return "Память пока пуста. Расскажи мне о себе, и я буду запоминать."

    categories = {}
    for f in facts:
        cat = f["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"  • {f['fact']}")

    lines = ["📋 Что я помню о тебе:\n"]
    for cat, items in categories.items():
        lines.append(f"{cat.title()}:")
        lines.extend(items)
        lines.append("")
    return "\n".join(lines)
