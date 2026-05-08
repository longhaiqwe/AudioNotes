import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.services import asr_groq


class GroqASRSplitTests(unittest.TestCase):
    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp(prefix="audionotes_test_"))
        self.addCleanup(shutil.rmtree, self.work_dir, ignore_errors=True)
        self.input_file = self.work_dir / "sample.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:duration=4",
                str(self.input_file),
            ],
            check=True,
        )

    def test_large_media_split_does_not_load_entire_file_with_pydub(self):
        splitter = asr_groq.GroqASR()
        with (
            mock.patch.object(asr_groq, "MAX_FILE_SIZE_BYTES", 1024),
            mock.patch(
                "app.services.asr_groq.AudioSegment.from_file",
                side_effect=AssertionError("should not load entire media into memory"),
            ),
        ):
            chunks, temp_dir = splitter._split_audio(str(self.input_file))

        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        self.assertIsNotNone(temp_dir)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(Path(chunk).exists())
            self.assertEqual(Path(chunk).suffix, ".mp3")


if __name__ == "__main__":
    unittest.main()
