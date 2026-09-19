# Implementation Plan: Upgrade Pocket TTS to v3.1.0 with TDD

Upgrade ClonEpub-Pocket from `pocket-tts 1.1.1` to `pocket-tts 3.1.0` to take advantage of retrained high-stability models (0.3 default temperature), Int8 dynamic quantization for ~30% faster CPU generation and ~48% memory savings, 26+ built-in catalog voices, enhanced text chunking, and direct audio format handling.

## User Review Required

> [!IMPORTANT]
> **1. Legacy Voice Preset Compatibility**:
> Pocket TTS v2/v3 changed the latent projection and Mimi quantizer inner dimensions (from 512 to 32). Saved `.safetensors` voice states from v1.1.1 cannot be loaded directly. We will implement automatic background re-extraction using the saved `source_audio` recorded in each voice's `.json` metadata file.
>
> **2. Default Voice Selection**:
> Upstream Pocket TTS changed the default voice from `marius` to `alba` (higher quality/casual). In ClonEpub, we will set `alba` as the default built-in voice while keeping `marius` and all 25 other voices available.

## Proposed Changes

### Dependencies
#### [MODIFY] [pyproject.toml](file:///Users/jarodise/Documents/GitHub/ClonEpub-Pocket/pyproject.toml)
- Bump `pocket-tts>=1.1.1` to `pocket-tts>=3.1.0`.
- Update `uv.lock` via `uv lock --upgrade-package pocket-tts`.

---

### Core Pipeline & Voice Management
#### [MODIFY] [clonepub/core.py](file:///Users/jarodise/Documents/GitHub/ClonEpub-Pocket/clonepub/core.py)
- Expand `BUILTIN_VOICES` from 8 to 26+ catalog voices (including `alba` [default], `marius`, `eve`, `george`, `mary`, `michael`, `anna`, `vera`, `bill_boerst`, `peter_yearsley`, `stuart_bell`, `caro_davy`, `charles`, `paul`, `jane`, `giovanni`, `lola`, `juergen`, `rafael`, `estelle`, `javert`, `jean`, `fantine`, `cosette`, `eponine`, `azelma`).
- Update `get_tts_model(quantize: bool = True)` to enable Int8 dynamic quantization by default (giving ~30% faster inference and ~48% lower memory usage).
- Enhance `resolve_voice_preset()` and voice state loading to detect legacy/incompatible `.safetensors` states and automatically re-export them from `source_audio` without crashing or losing voices.
- Relax `ensure_compatible_audio()` to leverage Pocket TTS's native `audio_read` multi-format decoder while keeping mono/24kHz conversion as fallback.

---

### Test Suite (TDD Approach)
#### [MODIFY] [testing/test_voice_presets.py](file:///Users/jarodise/Documents/GitHub/ClonEpub-Pocket/testing/test_voice_presets.py)
- Update tests to assert 26 built-in voices.
- Test that default fallback voice is `alba`.
- Add test for legacy `.safetensors` auto-recovery when `source_audio` is present.

#### [NEW] [testing/test_tts_pipeline.py](file:///Users/jarodise/Documents/GitHub/ClonEpub-Pocket/testing/test_tts_pipeline.py)
- Test `get_tts_model()` with `quantize=True` and `quantize=False`.
- Test `PocketTTSPipeline` voice selection with new catalog voices.
- Test audio generation error handling and fallback behavior.

---

## Verification Plan

### Automated Tests
1. **Red Phase (Voice Presets)**:
   ```bash
   python3 -m unittest testing/test_voice_presets.py
   ```
   *Expected*: Fails because count is currently 8 instead of 26.
2. **Green Phase (Voice Presets)**:
   *After updating `clonepub/core.py`*, rerun:
   ```bash
   python3 -m unittest testing/test_voice_presets.py
   ```
   *Expected*: Passes (100% OK).
3. **Pipeline & Quantization Tests**:
   ```bash
   python3 -m unittest testing/test_tts_pipeline.py
   ```
4. **Full Test Discovery**:
   ```bash
   python3 -m unittest discover -s testing -p "test_*.py"
   ```

### Manual Verification
- Test API voice list output: verify `list_voices()` returns all custom and 26 built-in voices.
- Generate a sample audio sentence using `alba` and verify output audio file properties.
