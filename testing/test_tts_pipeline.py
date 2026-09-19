"""Tests for TTS pipeline and model loading (including quantization)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock heavy dependencies not needed for unit testing pipeline logic
sys.modules["spacy"] = MagicMock()
sys.modules["ebooklib"] = MagicMock()
sys.modules["ebooklib.epub"] = MagicMock()
sys.modules["soundfile"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["bs4"] = MagicMock()

# Mock pocket_tts
mock_pocket_tts = MagicMock()
mock_tts_model_class = MagicMock()
mock_pocket_tts.TTSModel = mock_tts_model_class
sys.modules["pocket_tts"] = mock_pocket_tts

import clonepub.core as core


class TestModelLoading(unittest.TestCase):
    """Test model loading and quantization options."""

    def setUp(self):
        # Reset model singleton before each test
        core._tts_model_instance = None
        self.mock_tts_model_class = MagicMock()
        patcher = patch.object(core, "TTSModel", self.mock_tts_model_class)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        core._tts_model_instance = None

    def test_get_tts_model_default_quantize(self):
        """get_tts_model should default to quantize=True for performance and low memory."""
        mock_instance = MagicMock()
        self.mock_tts_model_class.load_model.return_value = mock_instance

        model = core.get_tts_model()

        self.mock_tts_model_class.load_model.assert_called_once_with(quantize=True)
        self.assertEqual(model, mock_instance)

    def test_get_tts_model_explicit_no_quantize(self):
        """get_tts_model(quantize=False) should pass quantize=False."""
        mock_instance = MagicMock()
        self.mock_tts_model_class.load_model.return_value = mock_instance

        model = core.get_tts_model(quantize=False)

        self.mock_tts_model_class.load_model.assert_called_once_with(quantize=False)
        self.assertEqual(model, mock_instance)

    def test_get_tts_model_singleton_caching(self):
        """Subsequent calls should return the cached instance without reloading."""
        mock_instance = MagicMock()
        self.mock_tts_model_class.load_model.return_value = mock_instance

        m1 = core.get_tts_model()
        m2 = core.get_tts_model()

        self.assertEqual(self.mock_tts_model_class.load_model.call_count, 1)
        self.assertEqual(m1, m2)


class TestPipelineVoiceSelection(unittest.TestCase):
    """Test PocketTTSPipeline initialization with voices."""

    def setUp(self):
        core._tts_model_instance = None
        self.mock_tts_model_class = MagicMock()
        patcher = patch.object(core, "TTSModel", self.mock_tts_model_class)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        core._tts_model_instance = None

    @patch("clonepub.core.ensure_compatible_audio", return_value="/tmp/test.wav")
    def test_pipeline_init_default_voice(self, mock_compat):
        """Pipeline initialized without voice_preset should use None initially, falling back to alba."""
        pipeline = core.PocketTTSPipeline()
        self.assertIsNone(pipeline.voice_preset)

    def test_pipeline_generate_fallback_to_alba(self):
        """If preset fails or is not provided, should fall back to 'alba'."""
        mock_model = MagicMock()
        self.mock_tts_model_class.load_model.return_value = mock_model
        mock_model.get_state_for_audio_prompt.return_value = MagicMock()
        mock_model.generate_audio.return_value = MagicMock()

        pipeline = core.PocketTTSPipeline(voice_preset=None)
        pipeline._generate_single_audio("Test sentence.")

        mock_model.get_state_for_audio_prompt.assert_called_with("alba")


class TestEnsureCompatibleAudio(unittest.TestCase):
    """Test audio format compatibility and ffmpeg graceful fallback."""

    def test_nonexistent_file_returns_none(self):
        self.assertIsNone(core.ensure_compatible_audio("/nonexistent/path/test.wav"))

    def test_24k_heuristic_passes_through(self):
        with patch.object(Path, "exists", return_value=True):
            result = core.ensure_compatible_audio("/some/path/my_audio_24k.wav")
            self.assertEqual(result, "/some/path/my_audio_24k.wav")

    @patch("clonepub.core.get_ffmpeg_path", return_value="/fake/ffmpeg")
    @patch("subprocess.run", side_effect=OSError(86, "Bad CPU type in executable"))
    def test_ffmpeg_oserror_falls_back_to_original(self, mock_run, mock_ffmpeg):
        """When ffmpeg execution fails with OSError, fallback to original path for native Pocket TTS decoding."""
        def mock_exists(self):
            # Original file exists, but converted 24k file does not exist yet
            return not str(self).endswith("_24k.wav")

        with patch.object(Path, "exists", autospec=True, side_effect=mock_exists):
            result = core.ensure_compatible_audio("/some/path/my_audio.mp3")
            self.assertEqual(result, "/some/path/my_audio.mp3")


if __name__ == "__main__":
    unittest.main()
