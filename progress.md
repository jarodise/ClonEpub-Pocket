# Progress Log: Pocket TTS Upgrade

## Session Log
- **2026-09-19 08:24**: Research completed. Identified upstream changes from v1.1.1 to v3.1.0 (English CFG-distilled models with temp 0.3, Int8 quantization, 26+ catalog voices, multilingual support, audio streaming, decimal/punctuation protection).
- **2026-09-19 08:25**: Created `findings.md`, `task_plan.md`, and prepared implementation plan for user review. User approved.
- **2026-09-19 08:26**: Phase 1 completed. Bumped `pyproject.toml` to `pocket-tts>=3.1.0` and updated `uv.lock` to `v3.1.0`.
- **2026-09-19 08:27**: Phase 2 completed with TDD. Added unit tests for 26 built-in catalog voices and Alba default. Verified 5 failures, updated `BUILTIN_VOICES` and fallbacks in `clonepub/core.py`, verified all 20 tests pass.
- **2026-09-19 08:28**: Phase 3 completed with TDD. Created `testing/test_tts_pipeline.py` testing `quantize=True/False` model loading. Verified failure, updated `get_tts_model()` and `PocketTTSPipeline` in `clonepub/core.py`, verified all 5 tests pass.
- **2026-09-19 08:29**: Phase 4 completed with TDD. Added unit test `TestLoadVoiceState` in `testing/test_voice_presets.py` simulating legacy tensor mismatch. Verified failure, implemented `load_voice_state` in `clonepub/core.py` with automatic recovery and re-export from `source_audio`. All 23 tests pass.
- **2026-09-19 08:30**: Phase 5 completed with TDD. Added unit test `TestEnsureCompatibleAudio` in `testing/test_tts_pipeline.py`. Handled OSError/conversion errors to fallback gracefully to native Pocket TTS 3.x audio decoding. All 8 pipeline tests pass.
- **2026-09-19 08:32**: Phase 6 completed. Ran full test suite discover across all 36 test cases with 100% pass rate. Verified `ClonEpubAPI.list_voices()` returns all custom + 26 built-in voices. All phases complete.
- **2026-09-19 08:43**: DMG Distribution bundled and verified:
  - Replaced x86 ffmpeg with native Apple Silicon arm64 static builds in `clonepub/bin/`.
  - Bumped version to `1.2.0` in `pyproject.toml` and `electron/package.json` to trigger automatic `uv sync` on upgrade.
  - Added ad-hoc code signing hook in `forge.config.ts`.
  - Built `electron/out/make/ClonEpub.dmg` (171MB). Mounted and verified app signature and bundled dependencies.
