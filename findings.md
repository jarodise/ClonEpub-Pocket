# Findings: Pocket TTS Upgrade Investigation

## 1. Current State (ClonEpub-Pocket)
- **Dependency**: `pocket-tts>=1.1.1` in `pyproject.toml`, pinned to `1.1.1` in `uv.lock` (released Feb 16, 2026).
- **Model**: Original English model (`english_2026-01`), temperature 0.7.
- **Built-in Voices**: 8 hardcoded voices (`marius`, `alba`, `javert`, `jean`, `fantine`, `cosette`, `eponine`, `azelma`).
- **Quantization**: Unquantized FP32.
- **Audio Processing**: Custom `ensure_compatible_audio` converting to 24kHz mono WAV via ffmpeg.
- **Custom Voices**: Saved as `.safetensors` + `.json` metadata containing `source_audio`.

## 2. Upstream Pocket TTS Updates (v1.1.1 -> v3.1.0)
- **Releases**:
  - `v2.0.0` (April 2026): Multilingual models (French, German, Spanish, Italian, Portuguese), Int8 dynamic quantization (`quantize=True`), audio streaming (`generate_audio_stream`), long sentence splitting on commas/punctuation, native audio input formats.
  - `v2.1.0` (May 2026): Device fixes, default voice per language, quantization fixes for voice cloning.
  - `v3.0.0 - v3.0.2` (August 2026): Official training & distillation pipeline released, English 24-layer variant (`english_24l`), default temperature lowered to 0.3 for higher quality/stability, default voice changed to `alba`, Mimi decoder latent queue improvements.
  - `v3.1.0` (September 2026): Sentence chunker decimal protection (e.g. `3.14`), terminal punctuation enforcement, modern typing, expanded community models (Czech, Hindi, Korean, Polish, Estonian, Welsh, etc.).
- **Breaking Changes / Architecture Differences**:
  - `english.yaml` switched to 32-dim Mimi quantizer inner dimension (v1 was 512-dim).
  - Voice states (`.safetensors`) exported on v1.1.1 cannot be loaded directly by v2/v3 without re-encoding.
  - ClonEpub stores `source_audio` in the voice `.json` metadata, enabling automated re-extraction.
  - `pocket-tts 3.1.0` requires `torch>=2.5.0` and `numpy>=2`.
