"""
Голосовой модуль — serverless версия.
STT: Groq Whisper (дёшево, $0.04/час) с фолбэком на OpenAI.
TTS: OpenAI (для голосовых ответов).
"""
import io
import os
import tempfile
import logging
import openai
from core.config import OPENAI_API_KEY, GROQ_API_KEY, TTS_VOICE

logger = logging.getLogger(__name__)


def speech_to_text(audio_bytes: bytes, file_format: str = "ogg") -> str:
    """Голос → текст. Groq Whisper (приоритет) → OpenAI Whisper (фолбэк)."""
    tmp_path = None
    try:
        tmp_path = tempfile.mktemp(suffix=f".{file_format}")
        with open(tmp_path, "wb") as f:
            f.write(audio_bytes)

        # Groq Whisper — $0.04/час, быстрый
        if GROQ_API_KEY:
            try:
                client = openai.OpenAI(
                    api_key=GROQ_API_KEY,
                    base_url="https://api.groq.com/openai/v1",
                )
                with open(tmp_path, "rb") as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=audio_file,
                        language="ru",
                    )
                return transcription.text
            except Exception as e:
                logger.warning(f"Groq STT failed, falling back to OpenAI: {e}")

        # OpenAI Whisper — $0.36/час, фолбэк
        if OPENAI_API_KEY:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            with open(tmp_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                )
            return transcription.text

        raise ValueError("No STT provider configured (need GROQ_API_KEY or OPENAI_API_KEY)")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def text_to_speech(text: str, voice: str = "") -> bytes:
    """Текст → голос (OGG для Telegram). Требует OPENAI_API_KEY."""
    if not OPENAI_API_KEY:
        raise ValueError("TTS requires OPENAI_API_KEY")
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    voice = voice or TTS_VOICE

    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="opus",  # Telegram принимает opus напрямую
    )
    return response.content


def text_to_speech_buffer(text: str, voice: str = "") -> io.BytesIO:
    """TTS → BytesIO буфер для Telegram API."""
    data = text_to_speech(text, voice)
    buf = io.BytesIO(data)
    buf.name = "voice.ogg"
    return buf
