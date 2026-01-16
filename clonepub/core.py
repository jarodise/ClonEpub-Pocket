#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClonEpub - Convert EPUB e-books to audiobooks using Chatterbox Turbo TTS
with voice cloning capability. Optimized for Apple Silicon with MLX.

Based on audiblez by Claudio Santini 2025 - https://claudio.uk
"""

import os
import traceback

import spacy
import ebooklib
import soundfile
import numpy as np
import subprocess
import re
from pathlib import Path
from string import Formatter
from bs4 import BeautifulSoup
from ebooklib import epub
from clonepub.models import get_ffmpeg_path, get_ffprobe_path

# Remove MLX check as Pocket TTS is CPU based (or handles its own backend)
# but we might still want to keep platform check if user desired,
# though user plan says "CPU Execution: pocket-tts runs primarily on CPU"
# so I will remove the strict MLX check or adapt it.
# User plan: "Remove mlx-audio dependency", "Remove ChatterboxPipeline and mlx_audio imports"

try:
    from pocket_tts import TTSModel
except ImportError:
    TTSModel = None

sample_rate = 24000

# Singleton for TTS model
_tts_model_instance = None


def get_tts_model():
    global _tts_model_instance
    if _tts_model_instance is None:
        if TTSModel is None:
            raise ImportError("pocket-tts not found. Please install it.")
        print("Loading Pocket TTS model...")
        try:
            # Use load_model factory method which handles config and weights
            _tts_model_instance = TTSModel.load_model()
        except Exception as e:
            print(f"Failed to load Pocket TTS model: {e}")
            raise
    return _tts_model_instance


def ensure_compatible_audio(file_path):
    """
    Ensure the audio file is compatible with Pocket TTS (24kHz WAV).
    If not, convert it using ffmpeg.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    # Check extension and potentially format
    # Simple check: if it's already a wav, we might assume it's okay,
    # but Pocket TTS strictly prefers 24kHz.
    # To be safe, we can always convert/resample if it's not known 24k wav.
    # For now, let's just convert everything that isn't a likely-correct wav.

    # Heuristic: If filename ends in _24k.wav, assume it's good (our own convention)
    if path.name.endswith("_24k.wav"):
        return str(path)

    # Use a temp file for conversion
    compatible_path = path.parent / f"{path.stem}_24k.wav"

    # If the compatible file already exists, use it to save time
    if compatible_path.exists():
        return str(compatible_path)

    print(f"Converting {path.name} to 24kHz WAV...")
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        print("Warning: ffmpeg not found, using original file (may fail).")
        return str(path)

    try:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(path),
                "-ar",
                "24000",
                "-ac",
                "1",  # Force mono for consistency
                str(compatible_path),
            ],
            check=True,
            capture_output=True,
        )
        return str(compatible_path)
    except subprocess.CalledProcessError as e:
        print(f"Conversion failed: {e}")
        # Failure to convert reference audio is critical for cloning
        return None


class PocketTTSPipeline:
    """TTS Pipeline using Pocket TTS for voice cloning."""

    # Silence duration between sentences and paragraphs (in seconds)
    SENTENCE_PAUSE_DURATION = 0.5  # 500ms pause between sentences
    PARAGRAPH_PAUSE_DURATION = 0.9  # 900ms pause between paragraphs

    def __init__(self, ref_audio=None, voice_preset=None):
        self.ref_audio = ensure_compatible_audio(ref_audio) if ref_audio else None
        self.voice_preset = voice_preset
        self._nlp = None
        # Pre-load model
        self.model = get_tts_model()

    def _clean_text_for_tts(self, text):
        """Clean text for TTS by removing quotation marks and normalizing ALL CAPS."""
        # Normalize smart apostrophes to straight apostrophes first
        text = text.replace("’", "'").replace("‘", "'")

        # Remove double quotation marks and guillemets
        quote_chars = ['"', "“", "”", "«", "»", "‹", "›"]
        cleaned = text
        for char in quote_chars:
            cleaned = cleaned.replace(char, "")

        # Normalize ALL CAPS text to title case for better pronunciation
        alpha_chars = [c for c in cleaned if c.isalpha()]
        if alpha_chars:
            uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(
                alpha_chars
            )
            if uppercase_ratio > 0.7:
                cleaned = cleaned.title()

        return cleaned

    def _get_nlp(self):
        """Lazy load spaCy model for sentence detection."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                # Download if not available
                spacy.cli.download("en_core_web_sm")
                self._nlp = spacy.load("en_core_web_sm")
        return self._nlp

    def _generate_single_audio(self, text):
        """Generate audio for a single text segment using Pocket TTS."""
        cleaned_text = self._clean_text_for_tts(text)

        print(
            f"DEBUG: Processing Audio - ref_audio present? {bool(self.ref_audio)}, voice_preset={self.voice_preset}"
        )

        try:
            # Prepare audio prompt
            if self.ref_audio:
                # Use provided reference audio (Custom voice cloning)
                model_state = self.model.get_state_for_audio_prompt(self.ref_audio)
            elif self.voice_preset:
                # Use selected preset
                # Map 'custom' to fallback if it slipped through, though it shouldn't
                voice = self.voice_preset if self.voice_preset != "custom" else "marius"
                try:
                    model_state = self.model.get_state_for_audio_prompt(voice)
                except Exception as e:
                    print(
                        f"Warning: Preset '{voice}' failed ({e}). Falling back to 'marius'."
                    )
                    model_state = self.model.get_state_for_audio_prompt("marius")
            else:
                # Default fallback
                model_state = self.model.get_state_for_audio_prompt("marius")

            audio = self.model.generate_audio(
                model_state=model_state,
                text_to_generate=cleaned_text,
            )

            # Convert to numpy if needed
            if hasattr(audio, "numpy"):
                audio = audio.numpy()
            elif hasattr(audio, "detach"):  # Torch tensor
                audio = audio.detach().cpu().numpy()

            return audio

        except Exception as e:
            print(f"Error generating audio with Pocket TTS: {e}")
            traceback.print_exc()
            return None

    def _is_paragraph_break(self, text, sent_end, next_sent_start):
        """Check if there's a paragraph break between sentences."""
        if next_sent_start is None:
            return False
        between = text[sent_end:next_sent_start]
        return "\n\n" in between or "\n \n" in between

    def generate(self, text, progress_callback=None):
        """Generate audio from text, yielding progress updates."""
        nlp = self._get_nlp()
        doc = nlp(text)
        sentences = list(doc.sents)

        if not sentences:
            return self._generate_single_audio(text)

        # Generate silence for pauses
        sentence_silence = np.zeros(
            int(self.SENTENCE_PAUSE_DURATION * sample_rate), dtype=np.float32
        )
        paragraph_silence = np.zeros(
            int(self.PARAGRAPH_PAUSE_DURATION * sample_rate), dtype=np.float32
        )

        audio_segments = []
        total_sentences = len(sentences)

        for i, sent in enumerate(sentences):
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue

            audio = self._generate_single_audio(sentence_text)
            if audio is not None:
                audio_segments.append(audio)

                # Add pause after each sentence except the last
                if i < len(sentences) - 1:
                    next_sent = sentences[i + 1]
                    if self._is_paragraph_break(
                        text, sent.end_char, next_sent.start_char
                    ):
                        audio_segments.append(paragraph_silence)
                    else:
                        audio_segments.append(sentence_silence)

            if progress_callback:
                progress_callback((i + 1) / total_sentences * 100)

        if audio_segments:
            return np.concatenate(audio_segments)
        return None


def get_app_support_dir():
    """Get the Application Support directory for ClonEpub."""
    return Path.home() / "Library" / "Application Support" / "ClonEpub"


def get_models_dir():
    """Get the models directory."""
    return get_app_support_dir() / "models"


def check_model_installed():
    """Check if the Chatterbox model is installed."""
    # HuggingFace Hub caches models in ~/.cache/huggingface/
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_pattern = "*chatterbox*turbo*"
    return any(cache_dir.glob(model_pattern)) if cache_dir.exists() else False


def strfdelta(tdelta, fmt="{D:02}d {H:02}h {M:02}m {S:02}s"):
    """Format timedelta string."""
    remainder = int(tdelta)
    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ("W", "D", "H", "M", "S")
    constants = {"W": 604800, "D": 86400, "H": 3600, "M": 60, "S": 1}
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])
    return f.format(fmt, **values)


def probe_duration(file_name):
    """Get audio file duration in seconds using ffprobe."""
    ffprobe = get_ffprobe_path()
    if not ffprobe:
        return 0.0

    args = [
        ffprobe,
        "-i",
        str(file_name),
        "-show_entries",
        "format=duration",
        "-v",
        "quiet",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=True)
        return float(proc.stdout.strip())
    except Exception as e:
        print(f"Error probing duration for {file_name}: {e}")
        return 0.0


def create_index_file(title, creator, chapter_mp3_files, output_folder):
    """Create FFMETADATA1 chapters file."""
    output_file = Path(output_folder) / "chapters.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f";FFMETADATA1\ntitle={title}\nartist={creator}\n\n")
        start = 0
        i = 0
        for c in chapter_mp3_files:
            duration = probe_duration(c)
            end = start + (int)(duration * 1000)
            f.write(
                f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={start}\nEND={end}\ntitle=Chapter {i + 1}\n\n"
            )
            i += 1
            start = end
    return output_file


def concat_chapters_with_ffmpeg(chapter_files, output_folder, filename):
    """Concatenate chapter audio files using ffmpeg."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    file_list_txt = Path(output_folder) / filename.replace(".epub", "_file_list.txt")
    with open(file_list_txt, "w") as f:
        for chapter_file in chapter_files:
            # Use absolute path to avoid path resolution issues
            abs_path = Path(chapter_file).resolve()
            f.write(f"file '{abs_path}'\n")

    concat_file_path = Path(output_folder) / filename.replace(".epub", ".tmp.mp4")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(file_list_txt),
            "-c",
            "copy",
            str(concat_file_path),
        ],
        check=True,
    )
    Path(file_list_txt).unlink()
    return concat_file_path


def create_m4b(
    chapter_files,
    filename,
    cover_image,
    output_folder,
    title="Audiobook",
    author="Unknown",
):
    """Create final M4B audiobook file with metadata and cover."""
    print("Creating M4B file...")
    try:
        # Create chapters metadata
        chapters_txt_path = create_index_file(
            title, author, chapter_files, output_folder
        )

        # Concatenate audio
        concat_file_path = concat_chapters_with_ffmpeg(
            chapter_files, output_folder, filename
        )

        final_filename = Path(output_folder) / filename.replace(".epub", ".m4b")

        cover_image_args = []
        if cover_image:
            cover_file_path = Path(output_folder) / "cover.jpg"
            with open(cover_file_path, "wb") as f:
                f.write(cover_image)
            cover_image_args = [
                "-i",
                str(cover_file_path),
                "-map",
                "2:v",  # Map cover image
                "-disposition:v",
                "attached_pic",  # Ensure cover is embedded
                "-c:v",
                "copy",  # Keep cover unchanged
            ]

        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found")

        cmd = [
            ffmpeg,
            "-y",  # Overwrite output
            "-i",
            str(concat_file_path),  # Input audio
            "-i",
            str(chapters_txt_path),  # Input chapters
        ]

        if cover_image:
            cmd.extend(cover_image_args)

        cmd.extend(
            [
                "-map",
                "0:a",  # Map audio
                "-c:a",
                "aac",  # Convert to AAC
                "-b:a",
                "64k",  # Reduce bitrate for smaller size
                "-map_metadata",
                "1",  # Map metadata
                "-f",
                "mp4",  # Output as M4B
                str(final_filename),
            ]
        )

        subprocess.run(cmd, check=True, capture_output=True)

        # Cleanup
        if concat_file_path.exists():
            concat_file_path.unlink()
        if chapters_txt_path.exists():
            chapters_txt_path.unlink()
        if cover_image and cover_file_path.exists():
            cover_file_path.unlink()

        print(f"{final_filename} created.")
        return str(final_filename)

    except subprocess.CalledProcessError as e:
        print(f"Failed to create M4B: {e}")
        return None
    except Exception as e:
        print(f"Error in create_m4b: {e}")
        return None


def verify_audio_quality(audio_file_path, text_length):
    """
    Verify audio quality with simple checks:
    1. File exists and has reasonable size
    2. Duration is proportional to text length
    3. Audio isn't silent
    """
    MIN_DURATION_PER_CHAR = 0.03
    MAX_DURATION_PER_CHAR = 0.15
    MIN_RMS_THRESHOLD = 0.001

    issues = []
    path = Path(audio_file_path)

    # Check 1: File exists and size
    if not path.exists():
        return False, ["File does not exist"]

    file_size = path.stat().st_size
    if file_size < 1000:  # Less than 1KB is suspicious
        issues.append(f"File size too small: {file_size} bytes")

    # Check 2 & 3: Load audio and check duration + levels
    try:
        audio_data, sr = soundfile.read(path)
        duration = len(audio_data) / sr

        # Duration check
        expected_min = text_length * MIN_DURATION_PER_CHAR
        expected_max = text_length * MAX_DURATION_PER_CHAR

        if duration < expected_min:
            issues.append(
                f"Audio too short: {duration:.1f}s (expected >{expected_min:.1f}s for {text_length} chars)"
            )
        elif duration > expected_max:
            issues.append(
                f"Audio too long: {duration:.1f}s (expected <{expected_max:.1f}s for {text_length} chars)"
            )

        # RMS (loudness) check - detect silent audio
        rms = np.sqrt(np.mean(audio_data**2))
        if rms < MIN_RMS_THRESHOLD:
            issues.append(f"Audio appears silent: RMS={rms:.6f}")

    except Exception as e:
        issues.append(f"Failed to read audio: {str(e)}")

    return len(issues) == 0, issues


def load_epub(file_path):
    """Load an EPUB file and return book metadata and chapters."""
    book = epub.read_epub(file_path)

    meta_title = book.get_metadata("DC", "title")
    title = meta_title[0][0] if meta_title else Path(file_path).stem

    meta_creator = book.get_metadata("DC", "creator")
    author = meta_creator[0][0] if meta_creator else "Unknown Author"

    chapters = extract_chapters(book)
    cover = find_cover(book)

    return {
        "title": title,
        "author": author,
        "chapters": chapters,
        "cover": cover.get_content() if cover else None,
        "total_chars": sum(len(c["text"]) for c in chapters),
    }


def extract_chapters(book):
    """Extract chapters with text content from EPUB."""
    chapters = []

    for i, item in enumerate(book.get_items()):
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        xml = item.get_body_content()
        soup = BeautifulSoup(xml, features="lxml")

        # Remove footnote references
        for a in soup.find_all(
            "a", class_=re.compile(r"note|footnote|endnote|enref", re.I)
        ):
            a.decompose()
        for a in soup.find_all("a"):
            # Check for bracketed numbers like [1], [ 1 ], 1, etc.
            if re.match(r"^\s*\[?\s*\d+\s*\]?\s*$", a.get_text()):
                a.decompose()

        # Also remove superscript numbers that might be citations but not links
        for sup in soup.find_all("sup"):
            if re.match(r"^\s*\[?\s*\d+\s*\]?\s*$", sup.get_text()):
                sup.decompose()

        # Extract text from content tags
        text = ""
        for tag in soup.find_all(["title", "p", "h1", "h2", "h3", "h4", "li"]):
            if tag.text:
                tag_text = tag.text.strip()

                # Fallback: remove bracketed numbers from text even if they weren't links
                # Matches [1], [15], etc.
                tag_text = re.sub(r"\[\s*\d+\s*\]", "", tag_text)

                if not tag_text.endswith("."):
                    tag_text += "."
                text += tag_text + "\n"

        if len(text) > 100:  # Only include substantial chapters
            name = (
                item.get_name()
                .replace(".xhtml", "")
                .replace("xhtml/", "")
                .replace(".html", "")
            )
            chapters.append(
                {
                    "index": i,
                    "name": name,
                    "text": text,
                    "length": len(text),
                    "selected": is_likely_chapter(item.get_name(), text),
                }
            )

    return chapters


def is_likely_chapter(name, text):
    """Determine if this is likely a main chapter (for auto-selection)."""
    name_lower = name.lower()
    has_min_len = len(text) > 100
    looks_like_chapter = bool(
        "chapter" in name_lower
        or re.search(r"part_?\d{1,3}", name_lower)
        or re.search(r"ch_?\d{1,3}", name_lower)
    )
    return has_min_len and looks_like_chapter


def find_cover(book):
    """Find cover image in EPUB."""

    def is_image(item):
        return item is not None and item.media_type.startswith("image/")

    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
        if is_image(item):
            return item

    for meta in book.get_metadata("OPF", "cover"):
        if is_image(item := book.get_item_with_id(meta[1]["content"])):
            return item

    if is_image(item := book.get_item_with_id("cover")):
        return item

    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        if "cover" in item.get_name().lower() and is_image(item):
            return item

    return None


def generate_audiobook(
    chapters,
    output_folder,
    ref_audio=None,
    voice_preset=None,
    progress_callback=None,
    book_title="Audiobook",
    book_author="Unknown",
    cover_image=None,
):
    """Generate audiobook from chapters.

    Args:
        chapters: List of chapter dicts with 'text' and 'name' keys
        output_folder: Where to save MP3 files
        ref_audio: Path to reference audio for voice cloning
        ref_text: Transcript of reference audio
        speed: Playback speed multiplier
        progress_callback: Function(percent, status_message) for progress updates
        book_title: Title of the book for metadata
        book_author: Author of the book for metadata
        cover_image: Cover image bytes (optional)

    Returns:
        Path to the generated M4B file or list of MP3s if M4B fails
    """
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    pipeline = PocketTTSPipeline(ref_audio=ref_audio, voice_preset=voice_preset)

    total_chapters = len(chapters)
    mp3_files = []

    # Check for ffmpeg
    ffmpeg = get_ffmpeg_path()
    has_ffmpeg = ffmpeg is not None
    if not has_ffmpeg and progress_callback:
        progress_callback(0, "Warning: ffmpeg not found. M4B creation will be skipped.")

    for i, chapter in enumerate(chapters):
        chapter_name = chapter.get("name", f"chapter_{i + 1}")

        # Prepend intro to the first chapter
        text = chapter["text"]
        if i == 0:
            intro_text = f"{book_title}, by {book_author}.\n\n"
            text = intro_text + text

        # Sanitize filename
        safe_name = "".join(
            c for c in chapter_name if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        mp3_path = output_path / f"{safe_name}.mp3"

        def chapter_progress_callback(p):
            if progress_callback:
                # Calculate global progress: (completed_chapters + current_chapter_progress) / total
                # Scale up to 90% to leave room for M4B creation
                global_percent = ((i + p / 100) / total_chapters) * 90
                progress_callback(
                    percent=global_percent,
                    status=f"Generating {chapter_name} ({int(p)}%)...",
                )

        # Skip empty chapters
        if not text.strip():
            continue

        # Check if already exists
        if mp3_path.exists():
            mp3_files.append(mp3_path)
            continue

        audio = pipeline.generate(text, progress_callback=chapter_progress_callback)

        if audio is not None:
            # Write temp WAV then convert to MP3
            temp_wav = mp3_path.with_suffix(".tmp.wav")
            soundfile.write(temp_wav, audio, sample_rate)

            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(temp_wav),
                    "-codec:a",
                    "libmp3lame",
                    "-qscale:a",
                    "2",
                    str(mp3_path),
                ],
                capture_output=True,
                check=True,
            )

            temp_wav.unlink()

            # Verify audio quality
            is_valid, issues = verify_audio_quality(mp3_path, len(text))
            if not is_valid:
                print(f"Quality issues in {chapter_name}: {issues}")
                # Treat as failure
                if mp3_path.exists():
                    mp3_path.unlink()
                raise RuntimeError(f"Audio verification failed: {'; '.join(issues)}")

            mp3_files.append(mp3_path)

    if mp3_files and has_ffmpeg:
        if progress_callback:
            progress_callback(percent=95, status="Creating M4B audiobook...")

        m4b_path = create_m4b(
            mp3_files,
            f"{book_title} - {book_author}.epub",
            cover_image,
            output_folder,
            title=book_title,
            author=book_author,
        )

        if progress_callback:
            progress_callback(percent=100, status="Complete!")

        if m4b_path:
            # Clean up individual MP3s if M4B was successful?
            # Original kept them, but let's leave them for now or follow user preference.
            # Original: "To regenerate a chapter, delete its MP3 file and run again." -> implies keeping them.
            return m4b_path

    # If we got here but have no files, something went wrong (e.g. empty chapters)
    if not mp3_files:
        raise RuntimeError("No audio files were generated (empty text or errors).")

    if progress_callback:
        progress_callback(percent=100, status="Complete (MP3s only)!")

    return mp3_files
