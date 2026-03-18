"""
AI-провайдеры — синхронная версия для serverless.
Claude, OpenAI, Custom (OpenRouter/Groq/etc.)
"""
import json
import re
import anthropic
import openai
from core.config import (
    ANTHROPIC_API_KEY, CLAUDE_DEFAULT_MODEL,
    OPENAI_API_KEY, OPENAI_DEFAULT_MODEL,
    CUSTOM_AI_API_KEY, CUSTOM_AI_BASE_URL,
    CUSTOM_AI_NAME, CUSTOM_AI_DEFAULT_MODEL, CUSTOM_AI_MODELS,
    DEFAULT_AI_PROVIDER,
)


def chat_claude(
    messages: list[dict],
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
) -> str:
    """Запрос к Claude."""
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
    return response.content[0].text


def chat_openai(
    messages: list[dict],
    system_prompt: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
    base_url: str = None,
    api_key: str = None,
) -> str:
    """Запрос к OpenAI или совместимому API."""
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
    return response.choices[0].message.content


def chat(
    messages: list[dict],
    system_prompt: str = "",
    provider: str = "",
    model: str = "",
    temperature: float = 0.75,
    max_tokens: int = 1500,
) -> str:
    """Универсальный вызов AI — автоматически выбирает провайдер."""
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
    """Вызов AI с ответом в JSON."""
    response = chat(
        messages, system_prompt + "\n\nОтвечай ТОЛЬКО валидным JSON, без маркдауна.",
        provider=provider, temperature=0.3, max_tokens=4096,
    )
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]|\{.*\}', response, re.DOTALL)
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
