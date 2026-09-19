# Task Plan: Upgrade Pocket TTS to v3.1.0 with TDD

## Phases & Status

- [x] **Phase 1: Dependency Upgrade & Verification**
  - Update `pyproject.toml` to `pocket-tts>=3.1.0`
  - Update lockfile via `uv lock --upgrade-package pocket-tts`
  - Verify import and version in python
- [x] **Phase 2: Expanded Voice Catalog (TDD)**
  - Write test for 26+ built-in catalog voices in `testing/test_voice_presets.py`
  - Verify test fails on current 8-voice list
  - Update `BUILTIN_VOICES` and default voice in `clonepub/core.py`
  - Verify test passes
- [x] **Phase 3: Model Loading & Quantization Support (TDD)**
  - Write tests for quantized model loading in `testing/test_tts_pipeline.py`
  - Verify test fails
  - Implement `quantize=True` support in `get_tts_model()` and `PocketTTSPipeline`
  - Verify test passes
- [x] **Phase 4: Custom Voice Auto-Migration & Recovery (TDD)**
  - Write test simulating legacy/incompatible `.safetensors` with valid `source_audio`
  - Verify test fails
  - Implement auto-regeneration fallback in `resolve_voice_preset` / `PocketTTSPipeline`
  - Verify test passes
- [x] **Phase 5: Audio Input Flexibility & Preprocessing (TDD)**
  - Write test for handling various audio formats without ffmpeg hard failures
  - Verify test fails
  - Update `ensure_compatible_audio` to leverage Pocket TTS native audio loader
  - Verify test passes
- [x] **Phase 6: Full Test Suite Verification & Quality Gates**
  - Run all unit tests
  - Verify API endpoints (`list_voices`, `preview_voice`, `save_voice`)
  - Update documentation if needed
