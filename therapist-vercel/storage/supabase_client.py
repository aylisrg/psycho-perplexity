"""
Supabase Storage — память, сессии, профиль, база знаний.
Serverless-совместимый: создаёт клиент при каждом вызове.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from supabase import create_client, Client
from core.config import SUPABASE_URL, SUPABASE_KEY


def _get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── USER PROFILES ──

def get_or_create_profile(telegram_id: int, name: str = "") -> dict:
    db = _get_client()
    result = db.table("user_profiles").select("*").eq("telegram_id", telegram_id).execute()
    if result.data:
        return result.data[0]
    new_profile = {
        "telegram_id": telegram_id,
        "display_name": name,
        "created_at": _now(),
        "preferences": json.dumps({
            "ai_provider": "claude",
            "ai_model": None,
            "voice_responses": False,
            "language": "ru",
        }),
    }
    result = db.table("user_profiles").insert(new_profile).execute()
    return result.data[0]


def get_user_preferences(telegram_id: int) -> dict:
    profile = get_or_create_profile(telegram_id)
    return json.loads(profile.get("preferences", "{}"))


def update_profile_preferences(telegram_id: int, updates: dict):
    profile = get_or_create_profile(telegram_id)
    current = json.loads(profile.get("preferences", "{}"))
    current.update(updates)
    db = _get_client()
    db.table("user_profiles").update(
        {"preferences": json.dumps(current)}
    ).eq("telegram_id", telegram_id).execute()


# ── SESSIONS ──

def create_session(telegram_id: int) -> dict:
    db = _get_client()
    session = {
        "telegram_id": telegram_id,
        "started_at": _now(),
        "status": "active",
        "summary": None,
        "mood_start": None,
        "mood_end": None,
        "topics": json.dumps([]),
    }
    result = db.table("sessions").insert(session).execute()
    return result.data[0]


def get_active_session(telegram_id: int) -> Optional[dict]:
    db = _get_client()
    result = (
        db.table("sessions")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("status", "active")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def close_session(session_id: int, summary: str = "", mood_end: str = ""):
    db = _get_client()
    db.table("sessions").update({
        "status": "closed",
        "ended_at": _now(),
        "summary": summary,
        "mood_end": mood_end,
    }).eq("id", session_id).execute()


def get_session_history(telegram_id: int, limit: int = 10) -> list[dict]:
    db = _get_client()
    result = (
        db.table("sessions")
        .select("*")
        .eq("telegram_id", telegram_id)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


# ── MESSAGES ──

def save_message(session_id: int, role: str, content: str, metadata: Optional[dict] = None):
    db = _get_client()
    db.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": _now(),
        "metadata": json.dumps(metadata or {}),
    }).execute()


def get_session_messages(session_id: int, limit: int = 50) -> list[dict]:
    db = _get_client()
    result = (
        db.table("messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return result.data


# ── MEMORY FACTS ──

def save_memory_fact(telegram_id: int, category: str, fact: str, importance: int = 5):
    db = _get_client()
    db.table("memory_facts").insert({
        "telegram_id": telegram_id,
        "category": category,
        "fact": fact,
        "importance": importance,
        "created_at": _now(),
        "active": True,
    }).execute()


def get_memory_facts(telegram_id: int, category: Optional[str] = None, limit: int = 50) -> list[dict]:
    db = _get_client()
    query = (
        db.table("memory_facts")
        .select("*")
        .eq("telegram_id", telegram_id)
        .eq("active", True)
        .order("importance", desc=True)
    )
    if category:
        query = query.eq("category", category)
    return query.limit(limit).execute().data


# ── KNOWLEDGE BASE ──

def add_knowledge(category: str, title: str, content: str, source: str = ""):
    db = _get_client()
    db.table("knowledge_base").insert({
        "category": category,
        "title": title,
        "content": content,
        "source": source,
        "created_at": _now(),
        "active": True,
    }).execute()


def get_knowledge(category: Optional[str] = None) -> list[dict]:
    db = _get_client()
    query = db.table("knowledge_base").select("*").eq("active", True)
    if category:
        query = query.eq("category", category)
    return query.execute().data


def get_all_knowledge_for_prompt() -> str:
    db = _get_client()
    result = (
        db.table("knowledge_base")
        .select("category, title, content")
        .eq("active", True)
        .execute()
    )
    if not result.data:
        return ""
    sections = {}
    for item in result.data:
        cat = item["category"]
        if cat not in sections:
            sections[cat] = []
        sections[cat].append(f"### {item['title']}\n{item['content']}")
    parts = []
    for cat, items in sections.items():
        parts.append(f"## {cat.upper()}\n" + "\n\n".join(items))
    return "\n\n".join(parts)
