import math
import os
import shutil
import tempfile

from groq import Groq
from loguru import logger
from pydub import AudioSegment

# Groq Whisper API 单文件限制 25MB，留 1MB 安全展居
MAX_FILE_SIZE_BYTES = 24 * 1024 * 1024  # 24MB


class GroqASR:
    def __init__(self):
        self._client = None

    def _get_client(self) -> Groq:
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is not set")
            self._client = Groq(api_key=api_key)
        return self._client

    def _split_audio(self, audio_file: str) -> tuple[list[str], str | None]:
        """若文件超过 24MB，自动按时长切片并导出为 mp3。
        返回 (chunk_files, temp_dir)，若无需切片则 temp_dir=None。"""
        file_size = os.path.getsize(audio_file)
        if file_size <= MAX_FILE_SIZE_BYTES:
            return [audio_file], None

        logger.info(
            f"groq asr :: file {os.path.basename(audio_file)} "
            f"size {file_size / 1024 / 1024:.1f}MB > 24MB, splitting into chunks..."
        )

        audio = AudioSegment.from_file(audio_file)
        total_ms = len(audio)
        # 按文件大小比例估算需要切成几片，并多加一片余量
        num_chunks = math.ceil(file_size / MAX_FILE_SIZE_BYTES) + 1
        chunk_ms = math.ceil(total_ms / num_chunks)

        temp_dir = tempfile.mkdtemp(prefix="audionotes_")
        chunk_files = []

        for i in range(num_chunks):
            start = i * chunk_ms
            end = min((i + 1) * chunk_ms, total_ms)
            if start >= total_ms:
                break
            chunk = audio[start:end]
            chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.mp3")
            chunk.export(chunk_path, format="mp3", parameters=["-q:a", "4"])
            chunk_files.append(chunk_path)
            logger.info(
                f"groq asr :: chunk {i + 1}/{num_chunks}: "
                f"{(end - start) / 1000:.1f}s, {os.path.getsize(chunk_path) / 1024 / 1024:.1f}MB"
            )

        return chunk_files, temp_dir

    def _transcribe_file(self, client: Groq, model: str, language: str, audio_file: str) -> str:
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file), f.read()),
                model=model,
                language=language,
            )
        return transcription.text

    def transcribe(self, audio_file: str) -> str:
        client = self._get_client()
        model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
        language = os.getenv("GROQ_WHISPER_LANGUAGE", "zh")

        logger.info(f"groq asr :: start transcribe: {audio_file}")
        chunk_files, temp_dir = self._split_audio(audio_file)

        try:
            parts = []
            for idx, chunk_file in enumerate(chunk_files):
                logger.info(f"groq asr :: transcribing chunk {idx + 1}/{len(chunk_files)}: {chunk_file}")
                text = self._transcribe_file(client, model, language, chunk_file)
                parts.append(text)

            result = " ".join(parts)
            logger.info(f"groq asr :: complete transcribe: {audio_file}, total length: {len(result)}")
            return result
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


groq_asr = GroqASR()
