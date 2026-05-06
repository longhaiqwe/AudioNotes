import os
import uuid
import asyncio
import chainlit as cl
from io import BytesIO
from chainlit.types import ThreadDict
from chainlit.element import ElementBased
from chainlit.input_widget import Select
from loguru import logger
from app.services import data_layer
from app.services.asr import transcribe
from app.services.llm import chat as chat_with_llm

from app.utils import utils

# load environment variables
from dotenv import load_dotenv

load_dotenv()

logger.remove()
logger.add(f"{utils.storage_dir('logs')}/log.log", rotation="500 MB")

data_layer.init()


def default_asr_provider() -> str:
    provider = os.getenv("ASR_PROVIDER", "groq").lower()
    return provider if provider in {"groq", "funasr"} else "groq"


def default_llm_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    return provider if provider in {"groq", "ollama"} else "groq"


def apply_chat_settings(settings: dict):
    asr_provider = settings.get("asr_provider") or default_asr_provider()
    llm_provider = settings.get("llm_provider") or default_llm_provider()
    cl.user_session.set("asr_provider", asr_provider)
    cl.user_session.set("llm_provider", llm_provider)
    logger.info(f"chat settings updated: asr={asr_provider}, llm={llm_provider}")


async def setup_chat_settings():
    settings = await cl.ChatSettings(
        [
            Select(
                id="asr_provider",
                label="ASR 引擎",
                items={
                    "Groq Whisper（云端）": "groq",
                    "FunASR（本地）": "funasr",
                },
                initial_value=cl.user_session.get("asr_provider") or default_asr_provider(),
                description="选择音频/视频转文字服务。Groq 需要 GROQ_API_KEY；FunASR 会在本地加载模型。",
            ),
            Select(
                id="llm_provider",
                label="LLM 引擎",
                items={
                    "Groq LLM（云端）": "groq",
                    "Ollama（本地）": "ollama",
                },
                initial_value=cl.user_session.get("llm_provider") or default_llm_provider(),
                description="选择结构化笔记与问答所使用的大模型服务。",
            ),
        ]
    ).send()
    apply_chat_settings(settings)


def current_asr_provider() -> str:
    return cl.user_session.get("asr_provider") or default_asr_provider()


def current_llm_provider() -> str:
    return cl.user_session.get("llm_provider") or default_llm_provider()


@cl.password_auth_callback
def password_auth_callback(username: str, password: str):
    u = os.getenv("USERNAME", "admin")
    p = os.getenv("PASSWORD", "admin")
    if (username, password) == (u, p):
        return cl.User(
            identifier="admin", metadata={"role": "admin", "provider": "credentials"}
        )
    else:
        return None


@cl.on_chat_start
async def on_chat_start():
    await setup_chat_settings()
    files = None
    while files == None:
        msg = cl.AskFileMessage(
            content="请上传一个**音频/视频**文件",
            # accept=["audio/*", "video/*"],
            accept=["*/*"],
            max_size_mb=10240,
        )
        files = await msg.send()
    file = files[0]

    msg = cl.Message(content="")

    async def transcribe_file(uploaded_file):
        await msg.stream_token(f"文件 《{uploaded_file.name}》 上传成功, 识别中...\n")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, transcribe, uploaded_file.path, current_asr_provider())
        await msg.stream_token(f"## 识别结果 \n{result}\n")
        return result

    async def summarize_notes(text):
        messages = [
            {"role": "system", "content": "你是一名笔记整理专家，根据用户提供的内容，整理出一份内容详尽的结构化的笔记"},
            {"role": "user", "content": text},
        ]

        async def on_message(content):
            await msg.stream_token(content)

        await msg.stream_token("## 整理笔记\n\n")
        await chat_with_llm(messages, callback=on_message, provider=current_llm_provider())

    asr_result = await transcribe_file(file)
    await summarize_notes(asr_result)
    await msg.send()


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)
    cl.user_session.get("audio_buffer").write(chunk.data)


@cl.on_audio_end
async def on_audio_end(elements: list[ElementBased]):
    audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)
    file_path = f"{utils.upload_dir()}/{str(uuid.uuid4())}.wav"
    with open(file_path, "wb") as f:
        f.write(audio_buffer.read())

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, transcribe, file_path, current_asr_provider())
    await cl.Message(
        content=result,
        type="user_message",
    ).send()

    await chat()


async def chat():
    history = cl.chat_context.to_openai()
    logger.info(history)

    msg = cl.Message(content="")
    messages = [
        {"role": "system", "content": "你是一名笔记整理专家，严格根据音频识别的结果和整理的笔记内容，回答用户的问题。"},
        {"role": "user", "content": "请识别这段音频文件并且整理成结构化的笔记"},  # 无实际意义，用于补充缺失的user消息
    ]
    messages.extend(history)  # history 中包含了用户的提问
    logger.info(messages)

    async def on_message(content):
        await msg.stream_token(content)

    await chat_with_llm(messages, callback=on_message, provider=current_llm_provider())
    await msg.send()

@cl.on_settings_update
async def on_settings_update(settings: dict):
    apply_chat_settings(settings)


@cl.on_message
async def on_message(message: cl.Message):
    await chat()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    await setup_chat_settings()
