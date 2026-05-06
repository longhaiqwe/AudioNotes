import os

from loguru import logger


def transcribe(audio_file: str, provider: str | None = None) -> str:
    provider = (provider or os.getenv("ASR_PROVIDER", "groq")).lower()
    logger.info(f"asr provider: {provider}")

    if provider == "groq":
        from app.services.asr_groq import groq_asr

        return groq_asr.transcribe(audio_file)

    if provider == "funasr":
        from app.services.asr_funasr import funasr

        return funasr.transcribe(audio_file)

    raise ValueError(f"Unsupported ASR_PROVIDER: {provider}")
