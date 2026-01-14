import os
import sys
import traceback
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    print("Importing pipeline...")
    from clonepub.core import PocketTTSPipeline

    print("Initializing pipeline (this may download models)...")
    pipeline = PocketTTSPipeline()

    print("Generating simple audio...")
    audio = pipeline.generate("This is a test of Pocket TTS integration.")

    if audio is None:
        print("Error: Audio generation returned None")
    else:
        print(f"Success! Generated audio shape: {audio.shape}")

except Exception as e:
    print(f"Generation failed: {e}")
    traceback.print_exc()
