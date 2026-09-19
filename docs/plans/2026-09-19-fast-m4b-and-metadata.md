# Implementation Plan: Fast M4B Bundling (M4A Stream Copy) & Editable Book Metadata

Switch chapter audio generation from MP3 to M4A (AAC) to enable instant M4B stream copying (`-c copy`), and add editable Title/Author UI controls with smarter EPUB metadata extraction.

## User Review Required

> [!IMPORTANT]
> - **Chapter File Format**: Individual chapter files in the output directory will now be saved as `.m4a` (AAC, 64k bitrate) instead of `.mp3`. M4A is universally supported on macOS, iOS, Windows, and Android.
> - **M4B Bundling Speed**: M4B creation will drop from **20+ minutes** to **~5-7 seconds** on a 10-hour book because FFmpeg will stream-copy the audio without re-encoding.
> - **Metadata & Spoken Intro**: The UI will now show editable Title and Author inputs. The spoken intro ("*Book Title, by Book Author*") and the final M4B filename will use the exact values confirmed in the UI.

## Proposed Changes

### Core Engine & Audio Pipeline

#### [MODIFY] clonepub/core.py
1. **AAC Encoder Selection**: Add `get_best_aac_encoder()` to use `aac_at` (Apple AudioToolbox) when available, falling back to `aac`.
2. **Chapter Generation**: In `generate_audiobook()`, encode TTS WAV output directly to `.m4a` at 64k bitrate instead of `.mp3`.
3. **M4B Stream Copy**: In `concat_chapters_with_ffmpeg()` and `create_m4b()`, concatenate `.m4a` files and mux with chapters metadata and cover art using `-c:a copy` (pure stream copy, zero re-encoding).
4. **Metadata Extraction (`load_epub`)**:
   - Inspect `<dc:creator>` elements for `opf:file-as` and `opf:role`.
   - If `opf:file-as` is present and `opf:role="aut"`, prefer the author in `file-as` when the element text is a foreword/contributor (resolving the "Marco Pallis" vs "Chögyam Trungpa" bug).

---

### Backend API & Server

#### [MODIFY] clonepub/api.py
- Update `start_synthesis` to accept optional `book_title` and `book_author` arguments passed from the user interface.
- Fall back to `_current_book` metadata if not provided.

#### [MODIFY] clonepub/server.py
- In `/api/start_synthesis`, parse `book_title` and `book_author` from the request JSON and pass them to `api.start_synthesis()`.

---

### Frontend UI

#### [MODIFY] clonepub/ui/index.html
- Replace static `<h2 id="bookTitle">` and `<p id="bookAuthor">` with styled, editable text inputs (`bookTitleInput`, `bookAuthorInput`) inside `.book-meta`.

#### [MODIFY] clonepub/ui/styles.css
- Add styling for `.book-title-input` and `.book-author-input` to match the dark aesthetic (subtle focus border, clean typography).

#### [MODIFY] clonepub/ui/app.js
- Update `load_epub` response handler to populate the new inputs.
- Pass `book_title` and `book_author` in `start_synthesis` API call.

---

### Test Suite (TDD)

#### [NEW] testing/test_m4b_bundling.py
- Unit test for `get_best_aac_encoder()` detecting `aac_at` / `aac`.
- Unit test for `create_m4b()` using `.m4a` files with `-c:a copy` (verifying duration, chapters, and embedded cover).
- Unit test for `load_epub()` with `opf:file-as` and role heuristics.
- Integration test for `generate_audiobook()` generating `.m4a` chapters and assembling `.m4b`.
- API test for `start_synthesis` with custom `book_title` and `book_author`.

---

## Verification Plan

### Automated Tests
```bash
# Run new test suite to verify M4A generation, stream-copy M4B, and metadata
.venv/bin/python -m unittest discover -s testing
```

### Manual Verification
1. Run `load_epub` on the user's actual `Born in Tibet` EPUB to verify author extracts as "Chögyam Trungpa" instead of "Marco Pallis".
2. Run M4B bundling on 22 chapters to verify completion time is < 10 seconds.
