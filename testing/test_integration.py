import unittest
import sys
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock dependencies that might not be installed in the test environment
# if we are just testing the binary check logic.
# However, we want to test the actual binary *files* we downloaded.
sys.modules["spacy"] = MagicMock()
sys.modules["ebooklib"] = MagicMock()
sys.modules["ebooklib.epub"] = MagicMock()
sys.modules["soundfile"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["bs4"] = MagicMock()
sys.modules["pocket_tts"] = MagicMock()

from clonepub.models import (
    check_ffmpeg_installed,
    get_ffmpeg_path,
    get_ffprobe_path,
    check_model_installed,
    REQUIRED_MODELS,
)


class TestDependencies(unittest.TestCase):
    def test_ffmpeg_binary_exists(self):
        """Test that ffmpeg binary exists and is executable."""
        ffmpeg_path = get_ffmpeg_path()
        self.assertIsNotNone(ffmpeg_path, "ffmpeg path should not be None")
        self.assertTrue(
            os.path.exists(ffmpeg_path), f"ffmpeg binary not found at {ffmpeg_path}"
        )
        self.assertTrue(
            os.access(ffmpeg_path, os.X_OK), "ffmpeg binary is not executable"
        )

    def test_ffmpeg_execution(self):
        """Test that ffmpeg actually runs."""
        ffmpeg_path = get_ffmpeg_path()
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "ffmpeg failed to run")
            self.assertIn("ffmpeg version", result.stdout, "ffmpeg output unexpected")
        except OSError as e:
            if getattr(e, "errno", None) == 86:
                self.skipTest("Rosetta 2 not installed for x86_64 ffmpeg binary on arm64")
            raise

    def test_ffprobe_binary_exists(self):
        """Test that ffprobe binary exists and is executable."""
        ffprobe_path = get_ffprobe_path()
        self.assertIsNotNone(ffprobe_path, "ffprobe path should not be None")
        self.assertTrue(
            os.path.exists(ffprobe_path), f"ffprobe binary not found at {ffprobe_path}"
        )
        self.assertTrue(
            os.access(ffprobe_path, os.X_OK), "ffprobe binary is not executable"
        )

    def test_ffprobe_execution(self):
        """Test that ffprobe actually runs."""
        ffprobe_path = get_ffprobe_path()
        try:
            result = subprocess.run(
                [ffprobe_path, "-version"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, "ffprobe failed to run")
            self.assertIn("ffprobe version", result.stdout, "ffprobe output unexpected")
        except OSError as e:
            if getattr(e, "errno", None) == 86:
                self.skipTest("Rosetta 2 not installed for x86_64 ffprobe binary on arm64")
            raise

    def test_no_bad_dependencies(self):
        """Test that binaries do not link to Homebrew/local paths."""
        ffmpeg_path = get_ffmpeg_path()
        result = subprocess.run(
            ["otool", "-L", ffmpeg_path], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if "/opt/homebrew" in line or "/usr/local" in line:
                self.fail(f"Found dynamic dependency on local system: {line.strip()}")


class TestServerDownload(unittest.TestCase):
    def test_start_download_endpoint_passes_token(self):
        """Test that /api/start_download passes token to api.start_model_download."""
        from clonepub import server
        from unittest.mock import patch

        client = server.app.test_client()

        with patch.object(server.api, "start_model_download") as mock_start:
            mock_start.return_value = {"success": True}

            # Test with token
            response = client.post(
                "/api/start_download",
                json={"token": "hf_dummy_12345"},
            )
            self.assertEqual(response.status_code, 200)
            mock_start.assert_called_with(token="hf_dummy_12345")

            # Test without token
            mock_start.reset_mock()
            response = client.post("/api/start_download", json={})
            self.assertEqual(response.status_code, 200)
            mock_start.assert_called_with(token=None)


if __name__ == "__main__":
    unittest.main()

