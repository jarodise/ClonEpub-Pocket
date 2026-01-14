print("Verifying Pocket TTS environment...")
try:
    import pocket_tts, torch

    print(f"pocket-tts imported successfully")
    print(f"torch version: {torch.__version__}")

    from clonepub.core import PocketTTSPipeline, get_tts_model

    print("PocketTTSPipeline imported successfully.")

    # Optional: Try to load model if it doesn't download huge files immediately
    # print("Loading model...")
    # model = get_tts_model()
    # print("Model loaded.")

except ImportError as e:
    print(f"Import failed: {e}")
    exit(1)
except Exception as e:
    print(f"Error: {e}")
    exit(1)

print("Verification passed!")
