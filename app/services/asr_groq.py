import math
import os
import shutil
import subprocess
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

    def _probe_duration_seconds(self, audio_file: str) -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_file,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())

    def _export_audio_chunk(
        self,
        audio_file: str,
        chunk_path: str,
        start_seconds: float,
        duration_seconds: float,
    ):
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-y",
                    "-ss",
                    f"{start_seconds:.3f}",
                    "-t",
                    f"{duration_seconds:.3f}",
                    "-i",
                    audio_file,
                    "-map",
                    "0:a:0",
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-q:a",
                    "4",
                    chunk_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            error = exc.stderr.strip() or exc.stdout.strip()
            raise RuntimeError(f"Failed to split media with ffmpeg: {error}") from exc

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

        total_seconds = self._probe_duration_seconds(audio_file)
        if total_seconds <= 0:
            raise ValueError(f"Could not determine media duration: {audio_file}")

        # 按文件大小比例估算需要切成几片，并多加一片余量
        num_chunks = math.ceil(file_size / MAX_FILE_SIZE_BYTES) + 1
        chunk_seconds = math.ceil(total_seconds / num_chunks)

        temp_dir = tempfile.mkdtemp(prefix="audionotes_")
        chunk_files = []

        for i in range(num_chunks):
            start = i * chunk_seconds
            end = min((i + 1) * chunk_seconds, total_seconds)
            if start >= total_seconds:
                break
            chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.mp3")
            self._export_audio_chunk(audio_file, chunk_path, start, end - start)
            chunk_files.append(chunk_path)
            logger.info(
                f"groq asr :: chunk {i + 1}/{num_chunks}: "
                f"{end - start:.1f}s, {os.path.getsize(chunk_path) / 1024 / 1024:.1f}MB"
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
        model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
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
