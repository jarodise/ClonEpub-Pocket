import os
import sys
from pathlib import Path
import traceback

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

print("Importing pipeline...")
from clonepub.core import PocketTTSPipeline


def test_generation():
    print("Initializing pipeline (this may download models)...")
    try:
        # Test Default Preset (Marius)
        print("\n--- Testing Preset: Marius ---")
        pipeline = PocketTTSPipeline(voice_preset="marius")
        text = "This is a test of the Pocket TTS pipeline with the Marius preset."

        print("Generating audio...")
        audio = pipeline.generate(text)

        if audio is None:
            print("Error: Audio generation returned None")
            return

        print(f"Success! Generated audio shape: {audio.shape}")

        # Test Custom Preset (Alba)
        print("\n--- Testing Preset: Alba ---")
        pipeline_alba = PocketTTSPipeline(voice_preset="alba")
        text_alba = "This is a test with Alba voice."
        audio_alba = pipeline_alba.generate(text_alba)
        if audio_alba is not None:
            print(f"Success! Generated audio shape: {audio_alba.shape}")
        else:
            print("Error generating Alba audio")

    except Exception as e:
        print(f"Error generating audio with Pocket TTS: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    test_generation()
