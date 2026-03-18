"""
AI-провайдеры — синхронная версия для serverless.
Claude, OpenAI, Custom (OpenRouter/Groq/etc.)
Возвращает (text, usage_dict) для трекинга токенов.
"""
import json
import re
import logging
import anthropic
import openai
from core.config import (
    ANTHROPIC_API_KEY, CLAUDE_DEFAULT_MODEL,
    OPENAI_API_KEY, OPENAI_DEFAULT_MODEL,
    CUSTOM_AI_API_KEY, CUSTOM_AI_BASE_URL,
    CUSTOM_AI_NAME, CUSTOM_AI_DEFAULT_MODEL, CUSTOM_AI_MODELS,
    DEFAULT_AI_PROVIDER,
)

logger = logging.getLogger(__name__)

# Цены за 1M токенов (USD). Обнови при изменении цен.
MODEL_PRICING = {
    # Claude
    "claude-sonnet-4-20250514":    {"input": 3.0,  "output": 15.0},
    "claude-opus-4-20250514":      {"input": 15.0, "output": 75.0},
    "claude-3-5-haiku-20241022":   {"input": 0.8,  "output": 4.0},
    # OpenAI
    "gpt-4o":                      {"input": 2.5,  "output": 10.0},
    "gpt-4o-mini":                 {"input": 0.15, "output": 0.6},
    "o1-preview":                  {"input": 15.0, "output": 60.0},
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Посчитать стоимость запроса в USD."""
    pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def chat_claude(
    messages: list[dict],
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
) -> tuple[str, dict]:
    """Запрос к Claude. Возвращает (text, usage)."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    model = model or CLAUDE_DEFAULT_MODEL
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in messages if m["role"] in ("user", "assistant")
    ]
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=clean,
    )
    usage = {
        "provider": "claude",
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
    }
    usage["cost_usd"] = _calc_cost(model, usage["input_tokens"], usage["output_tokens"])
    return response.content[0].text, usage


def chat_openai(
    messages: list[dict],
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
    base_url: str = None,
    api_key: str = None,
) -> tuple[str, dict]:
    """Запрос к OpenAI или совместимому API. Возвращает (text, usage)."""
    client = openai.OpenAI(
        api_key=api_key or OPENAI_API_KEY,
        base_url=base_url,
    )
    model = model or OPENAI_DEFAULT_MODEL
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(
        {"role": m["role"], "content": m["content"]}
        for m in messages if m["role"] in ("user", "assistant", "system")
    )
    response = client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    u = response.usage
    usage = {
        "provider": "openai" if not base_url else "custom",
        "model": model,
        "input_tokens": u.prompt_tokens if u else 0,
        "output_tokens": u.completion_tokens if u else 0,
        "total_tokens": u.total_tokens if u else 0,
    }
    usage["cost_usd"] = _calc_cost(model, usage["input_tokens"], usage["output_tokens"])
    return response.choices[0].message.content, usage


def chat(
    messages: list[dict],
    system_prompt: str = "",
    provider: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
) -> tuple[str, dict]:
    """Универсальный вызов AI. Возвращает (text, usage_dict)."""
    provider = provider or DEFAULT_AI_PROVIDER

    if provider == "claude" and ANTHROPIC_API_KEY:
        return chat_claude(messages, system_prompt, model, temperature, max_tokens)
    elif provider == "openai" and OPENAI_API_KEY:
        return chat_openai(messages, system_prompt, model, temperature, max_tokens)
    elif provider == "custom" and CUSTOM_AI_API_KEY:
        return chat_openai(
            messages, system_prompt,
            model=model or CUSTOM_AI_DEFAULT_MODEL,
            temperature=temperature, max_tokens=max_tokens,
            base_url=CUSTOM_AI_BASE_URL, api_key=CUSTOM_AI_API_KEY,
        )
    else:
        # Fallback
        if ANTHROPIC_API_KEY:
            return chat_claude(messages, system_prompt, model, temperature, max_tokens)
        elif OPENAI_API_KEY:
            return chat_openai(messages, system_prompt, model, temperature, max_tokens)
        raise ValueError("No AI provider configured")


def chat_json(
    messages: list[dict],
    system_prompt: str = "",
    provider: str = "",
) -> list | dict:
    """Вызов AI с ответом в JSON (без трекинга)."""
    text, _usage = chat(
        messages, system_prompt + "\n\nОтвечай ТОЛЬКО валидным JSON, без маркдауна.",
        provider=provider, temperature=0.3, max_tokens=4096,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []


def list_providers() -> list[dict]:
    """Список доступных провайдеров."""
    providers = []
    if ANTHROPIC_API_KEY:
        providers.append({
            "key": "claude",
            "name": "Claude (Anthropic)",
            "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-20241022"],
            "default_model": CLAUDE_DEFAULT_MODEL,
        })
    if OPENAI_API_KEY:
        providers.append({
            "key": "openai",
            "name": "OpenAI",
            "models": ["gpt-4o", "gpt-4o-mini", "o1-preview"],
            "default_model": OPENAI_DEFAULT_MODEL,
        })
    if CUSTOM_AI_API_KEY and CUSTOM_AI_BASE_URL:
        providers.append({
            "key": "custom",
            "name": CUSTOM_AI_NAME,
            "models": [m.strip() for m in (CUSTOM_AI_MODELS or "").split(",") if m.strip()],
            "default_model": CUSTOM_AI_DEFAULT_MODEL,
        })
    return providers
