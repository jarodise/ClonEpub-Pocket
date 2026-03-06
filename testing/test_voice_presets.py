"""Tests for voice preset management (save, list, delete, resolve)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Mock heavy dependencies not needed for voice management logic
sys.modules["spacy"] = MagicMock()
sys.modules["ebooklib"] = MagicMock()
sys.modules["ebooklib.epub"] = MagicMock()
sys.modules["soundfile"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["bs4"] = MagicMock()

# Mock pocket_tts with specific exports we need
mock_pocket_tts = MagicMock()
mock_tts_model_class = MagicMock()
mock_export_model_state = MagicMock()
mock_pocket_tts.TTSModel = mock_tts_model_class
mock_pocket_tts.export_model_state = mock_export_model_state
sys.modules["pocket_tts"] = mock_pocket_tts

from clonepub.core import (
    BUILTIN_VOICES,
    get_voices_dir,
    list_voices,
    save_custom_voice,
    delete_custom_voice,
    resolve_voice_preset,
)


class TestBuiltinVoices(unittest.TestCase):
    """Test the built-in voice list constant."""

    def test_builtin_voices_count(self):
        """Should have exactly 8 built-in voices."""
        self.assertEqual(len(BUILTIN_VOICES), 8)

    def test_builtin_voices_structure(self):
        """Each voice should have id, name, and type='builtin'."""
        for voice in BUILTIN_VOICES:
            self.assertIn("id", voice)
            self.assertIn("name", voice)
            self.assertEqual(voice["type"], "builtin")

    def test_builtin_voice_ids(self):
        """Should contain all expected voice IDs."""
        ids = {v["id"] for v in BUILTIN_VOICES}
        expected = {"marius", "alba", "javert", "jean", "fantine", "cosette", "eponine", "azelma"}
        self.assertEqual(ids, expected)


class TestVoiceDirectory(unittest.TestCase):
    """Test voice directory creation."""

    @patch("clonepub.core.get_app_support_dir")
    def test_get_voices_dir_creates_directory(self, mock_app_dir):
        """get_voices_dir should create the voices subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = get_voices_dir()
            self.assertTrue(voices_dir.exists())
            self.assertEqual(voices_dir.name, "voices")


class TestListVoices(unittest.TestCase):
    """Test listing all available voices."""

    @patch("clonepub.core.get_app_support_dir")
    def test_list_voices_no_custom(self, mock_app_dir):
        """With no saved voices, should return only built-in voices."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices = list_voices()
            # All voices should be built-in
            self.assertEqual(len(voices), 8)
            self.assertTrue(all(v["type"] == "builtin" for v in voices))

    @patch("clonepub.core.get_app_support_dir")
    def test_list_voices_with_custom(self, mock_app_dir):
        """Custom voices should appear first, before built-in voices."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            # Create a fake custom voice
            (voices_dir / "my_voice.safetensors").write_bytes(b"fake")
            (voices_dir / "my_voice.json").write_text(
                json.dumps({"name": "My Voice", "source_audio": "/tmp/test.wav"})
            )

            voices = list_voices()
            self.assertEqual(len(voices), 9)  # 1 custom + 8 builtin

            # Custom voice should be first
            self.assertEqual(voices[0]["type"], "custom")
            self.assertEqual(voices[0]["id"], "custom:my_voice")
            self.assertEqual(voices[0]["name"], "My Voice")

            # Built-in voices follow
            self.assertTrue(all(v["type"] == "builtin" for v in voices[1:]))

    @patch("clonepub.core.get_app_support_dir")
    def test_list_voices_ignores_orphaned_json(self, mock_app_dir):
        """A .json without a matching .safetensors should be ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            # Only metadata, no safetensors file
            (voices_dir / "orphan.json").write_text(
                json.dumps({"name": "Orphan"})
            )

            voices = list_voices()
            self.assertEqual(len(voices), 8)  # Only built-in

    @patch("clonepub.core.get_app_support_dir")
    def test_list_voices_ignores_bad_json(self, mock_app_dir):
        """A malformed .json should be silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            (voices_dir / "bad.safetensors").write_bytes(b"fake")
            (voices_dir / "bad.json").write_text("not valid json!!!")

            voices = list_voices()
            self.assertEqual(len(voices), 8)  # Only built-in, bad entry skipped


class TestSaveCustomVoice(unittest.TestCase):
    """Test saving custom voice presets."""

    @patch("clonepub.core.get_app_support_dir")
    @patch("clonepub.core.ensure_compatible_audio", return_value="/tmp/compat.wav")
    @patch("clonepub.core.get_tts_model")
    def test_save_voice_creates_files(self, mock_model, mock_compat, mock_app_dir):
        """Saving a voice should create both .safetensors and .json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.get_state_for_audio_prompt.return_value = "fake_state"

            # Mock export_model_state to actually create the file
            from clonepub import core as core_module
            original_export = core_module.export_model_state
            def fake_export(state, path):
                Path(path).write_bytes(b"fake_safetensors_data")
            core_module.export_model_state = fake_export

            try:
                result = save_custom_voice("/tmp/test.wav", "Test Voice")

                self.assertTrue(result["success"])
                self.assertTrue(result["voice_id"].startswith("custom:"))

                voices_dir = Path(tmpdir) / "voices"
                voice_id = result["voice_id"].replace("custom:", "")
                self.assertTrue((voices_dir / f"{voice_id}.safetensors").exists())
                self.assertTrue((voices_dir / f"{voice_id}.json").exists())

                # Check metadata
                with open(voices_dir / f"{voice_id}.json") as f:
                    meta = json.load(f)
                self.assertEqual(meta["name"], "Test Voice")
            finally:
                core_module.export_model_state = original_export

    @patch("clonepub.core.get_app_support_dir")
    @patch("clonepub.core.ensure_compatible_audio", return_value="/tmp/compat.wav")
    @patch("clonepub.core.get_tts_model")
    def test_save_voice_unique_ids(self, mock_model, mock_compat, mock_app_dir):
        """Saving two voices with the same name should get unique IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.get_state_for_audio_prompt.return_value = "fake_state"

            from clonepub import core as core_module
            original_export = core_module.export_model_state
            def fake_export(state, path):
                Path(path).write_bytes(b"fake_safetensors_data")
            core_module.export_model_state = fake_export

            try:
                result1 = save_custom_voice("/tmp/test.wav", "Same Name")
                result2 = save_custom_voice("/tmp/test.wav", "Same Name")

                self.assertTrue(result1["success"])
                self.assertTrue(result2["success"])
                self.assertNotEqual(result1["voice_id"], result2["voice_id"])
            finally:
                core_module.export_model_state = original_export

    @patch("clonepub.core.get_app_support_dir")
    @patch("clonepub.core.ensure_compatible_audio", return_value=None)
    @patch("clonepub.core.get_tts_model")
    def test_save_voice_bad_audio(self, mock_model, mock_compat, mock_app_dir):
        """Should return error if audio can't be processed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            result = save_custom_voice("/tmp/bad.wav", "Bad Voice")
            self.assertFalse(result["success"])
            self.assertIn("error", result)

    @patch("clonepub.core.get_app_support_dir")
    @patch("clonepub.core.ensure_compatible_audio", return_value="/tmp/compat.wav")
    @patch("clonepub.core.get_tts_model")
    def test_save_voice_sanitizes_name(self, mock_model, mock_compat, mock_app_dir):
        """Voice IDs should be filesystem-safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance
            mock_model_instance.get_state_for_audio_prompt.return_value = "fake_state"

            result = save_custom_voice("/tmp/test.wav", "My Voice! (v2)")
            self.assertTrue(result["success"])
            voice_id = result["voice_id"].replace("custom:", "")
            # Should only contain alphanumeric and underscore
            self.assertTrue(all(c.isalnum() or c == "_" for c in voice_id))


class TestDeleteCustomVoice(unittest.TestCase):
    """Test deleting custom voice presets."""

    @patch("clonepub.core.get_app_support_dir")
    def test_delete_removes_files(self, mock_app_dir):
        """Deleting a voice should remove both .safetensors and .json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            # Create files to delete
            (voices_dir / "test_voice.safetensors").write_bytes(b"fake")
            (voices_dir / "test_voice.json").write_text(json.dumps({"name": "Test"}))

            result = delete_custom_voice("custom:test_voice")
            self.assertTrue(result["success"])
            self.assertFalse((voices_dir / "test_voice.safetensors").exists())
            self.assertFalse((voices_dir / "test_voice.json").exists())

    @patch("clonepub.core.get_app_support_dir")
    def test_delete_without_prefix(self, mock_app_dir):
        """Should work with or without the 'custom:' prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()

            (voices_dir / "test_voice.safetensors").write_bytes(b"fake")
            (voices_dir / "test_voice.json").write_text(json.dumps({"name": "Test"}))

            result = delete_custom_voice("test_voice")  # No prefix
            self.assertTrue(result["success"])

    @patch("clonepub.core.get_app_support_dir")
    def test_delete_nonexistent(self, mock_app_dir):
        """Deleting a voice that doesn't exist should return error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            result = delete_custom_voice("custom:nonexistent")
            self.assertFalse(result["success"])
            self.assertIn("error", result)


class TestResolveVoicePreset(unittest.TestCase):
    """Test resolving voice preset IDs to paths/names."""

    def test_resolve_builtin(self):
        """Built-in voice names should pass through unchanged."""
        self.assertEqual(resolve_voice_preset("marius"), "marius")
        self.assertEqual(resolve_voice_preset("alba"), "alba")

    def test_resolve_none(self):
        """None should pass through unchanged."""
        self.assertIsNone(resolve_voice_preset(None))

    @patch("clonepub.core.get_app_support_dir")
    def test_resolve_custom_existing(self, mock_app_dir):
        """Custom voice should resolve to .safetensors path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            voices_dir = Path(tmpdir) / "voices"
            voices_dir.mkdir()
            safetensors_path = voices_dir / "my_voice.safetensors"
            safetensors_path.write_bytes(b"fake")

            result = resolve_voice_preset("custom:my_voice")
            self.assertEqual(result, str(safetensors_path))

    @patch("clonepub.core.get_app_support_dir")
    def test_resolve_custom_missing_fallback(self, mock_app_dir):
        """Missing custom voice should fall back to 'marius'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_dir.return_value = Path(tmpdir)
            result = resolve_voice_preset("custom:nonexistent")
            self.assertEqual(result, "marius")


if __name__ == "__main__":
    unittest.main()
