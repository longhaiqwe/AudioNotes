import os

from loguru import logger


async def chat(messages: list[dict], callback=None, provider: str | None = None) -> str:
    provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
    logger.info(f"llm provider: {provider}")

    if provider == "groq":
        from app.services.groq_llm import chat_with_groq

        return await chat_with_groq(messages, callback=callback)

    if provider == "ollama":
        from app.services.ollama import chat_with_ollama

        return await chat_with_ollama(messages, callback=callback)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
