import unittest
import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock heavy dependencies not needed for bundling logic
sys.modules["spacy"] = MagicMock()
mock_ebooklib = MagicMock()
sys.modules["ebooklib"] = mock_ebooklib
sys.modules["ebooklib.epub"] = mock_ebooklib.epub
sys.modules["soundfile"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["bs4"] = MagicMock()
sys.modules["pocket_tts"] = MagicMock()
sys.modules["webview"] = MagicMock()

from clonepub.models import get_ffmpeg_path, get_ffprobe_path
from clonepub.core import (
    get_best_aac_encoder,
    create_m4b,
    concat_chapters_with_ffmpeg,
    generate_audiobook,
)


class TestM4BBundling(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ffmpeg = get_ffmpeg_path()
        self.ffprobe = get_ffprobe_path()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_dummy_m4a(self, filename: str, duration_sec: int = 2) -> Path:
        """Helper to create a small valid .m4a AAC audio file using ffmpeg lavfi."""
        path = Path(self.test_dir) / filename
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f", "lavfi",
                "-i", f"sine=frequency=440:duration={duration_sec}",
                "-c:a", "aac",
                "-b:a", "64k",
                str(path),
            ],
            capture_output=True,
            check=True,
        )
        return path

    def test_get_best_aac_encoder(self):
        """Test that get_best_aac_encoder returns 'aac_at' on macOS with AudioToolbox, or 'aac'."""
        encoder = get_best_aac_encoder()
        self.assertIn(encoder, ["aac_at", "aac"])
        if sys.platform == "darwin":
            self.assertEqual(encoder, "aac_at")

    def test_create_m4b_stream_copies_m4a_chapters(self):
        """Test that create_m4b takes .m4a files and produces a valid .m4b via stream copy."""
        ch1 = self._create_dummy_m4a("chapter_1.m4a", duration_sec=3)
        ch2 = self._create_dummy_m4a("chapter_2.m4a", duration_sec=4)

        # Create dummy 100x100 JPEG cover
        cover_path = Path(self.test_dir) / "dummy_cover.jpg"
        subprocess.run(
            [
                self.ffmpeg,
                "-y",
                "-f", "lavfi",
                "-i", "color=c=navy:s=100x100",
                "-vframes", "1",
                str(cover_path),
            ],
            capture_output=True,
            check=True,
        )
        with open(cover_path, "rb") as f:
            cover_bytes = f.read()

        with patch("subprocess.run", wraps=subprocess.run) as spy_run:
            m4b_path = create_m4b(
                chapter_files=[ch1, ch2],
                filename="my_book.epub",
                cover_image=cover_bytes,
                output_folder=self.test_dir,
                title="My Great Book",
                author="Book Author",
            )
            # Find the final ffmpeg command call producing .m4b
            final_ffmpeg_call = None
            for call_args in spy_run.call_args_list:
                args = call_args[0][0]
                if isinstance(args, list) and len(args) > 0 and str(args[-1]).endswith(".m4b"):
                    final_ffmpeg_call = args
                    break
            self.assertIsNotNone(final_ffmpeg_call, "Could not find final M4B ffmpeg call")
            # Verify stream copy: -c:a copy must be used, NOT re-encoding -c:a aac
            self.assertIn("-c:a", final_ffmpeg_call)
            idx = final_ffmpeg_call.index("-c:a")
            self.assertEqual(final_ffmpeg_call[idx + 1], "copy")

        self.assertIsNotNone(m4b_path)
        self.assertTrue(os.path.exists(m4b_path))
        self.assertTrue(m4b_path.endswith("my_book.m4b"))

        # Verify metadata & duration using ffprobe
        probe = subprocess.run(
            [
                self.ffprobe,
                "-v", "quiet",
                "-show_entries", "format=duration:format_tags=title,artist",
                "-of", "default=noprint_wrappers=1",
                m4b_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        output = probe.stdout
        self.assertIn("TAG:title=My Great Book", output)
        self.assertIn("TAG:artist=Book Author", output)

        # Total duration should be ~7 seconds (3s + 4s)
        for line in output.splitlines():
            if line.startswith("duration="):
                dur = float(line.split("=")[1])
                self.assertAlmostEqual(dur, 7.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
