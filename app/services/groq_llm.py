import os
from groq import AsyncGroq
from loguru import logger


async def chat_with_groq(messages: list[dict], callback=None) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")

    model = os.getenv("GROQ_LLM_MODEL", "qwen/qwen3-32b")
    logger.debug(f"chat with groq, model: {model}")

    client = AsyncGroq(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        stream=True,
        temperature=0.1,
        messages=messages,
    )

    full_content = ""
    async for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            if callback:
                await callback(content)
            full_content += content

    return full_content
