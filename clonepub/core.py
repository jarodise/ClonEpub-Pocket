#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClonEpub - Convert EPUB e-books to audiobooks using Chatterbox Turbo TTS
with voice cloning capability. Optimized for Apple Silicon with MLX.

Based on audiblez by Claudio Santini 2025 - https://claudio.uk
"""

import os
import json
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
    from pocket_tts import TTSModel, export_model_state
except ImportError:
    TTSModel = None
    export_model_state = None

sample_rate = 24000

# Singleton for TTS model
_tts_model_instance = None
_best_aac_encoder = None


def get_best_aac_encoder() -> str:
    """Return the fastest available AAC encoder ('aac_at' on macOS, else 'aac')."""
    global _best_aac_encoder
    if _best_aac_encoder is not None:
        return _best_aac_encoder

    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        _best_aac_encoder = "aac"
        return _best_aac_encoder

    try:
        proc = subprocess.run([ffmpeg, "-encoders"], capture_output=True, text=True, check=True)
        if "aac_at" in proc.stdout:
            _best_aac_encoder = "aac_at"
        else:
            _best_aac_encoder = "aac"
    except Exception:
        _best_aac_encoder = "aac"

    return _best_aac_encoder

# Built-in voice presets from Pocket TTS (full catalog of 26 voices)
BUILTIN_VOICES = [
    # English voices (Default: Alba)
    {"id": "alba",           "name": "Alba (Default)",      "type": "builtin"},
    {"id": "marius",         "name": "Marius",              "type": "builtin"},
    {"id": "javert",         "name": "Javert",              "type": "builtin"},
    {"id": "jean",           "name": "Jean",                "type": "builtin"},
    {"id": "fantine",        "name": "Fantine",             "type": "builtin"},
    {"id": "cosette",        "name": "Cosette",             "type": "builtin"},
    {"id": "eponine",        "name": "Eponine",             "type": "builtin"},
    {"id": "azelma",         "name": "Azelma",              "type": "builtin"},
    {"id": "anna",           "name": "Anna",                "type": "builtin"},
    {"id": "vera",           "name": "Vera",                "type": "builtin"},
    {"id": "charles",        "name": "Charles",             "type": "builtin"},
    {"id": "paul",           "name": "Paul",                "type": "builtin"},
    {"id": "george",         "name": "George",              "type": "builtin"},
    {"id": "mary",           "name": "Mary",                "type": "builtin"},
    {"id": "jane",           "name": "Jane",                "type": "builtin"},
    {"id": "michael",        "name": "Michael",             "type": "builtin"},
    {"id": "eve",            "name": "Eve",                 "type": "builtin"},
    {"id": "bill_boerst",    "name": "Bill Boerst",         "type": "builtin"},
    {"id": "peter_yearsley", "name": "Peter Yearsley",      "type": "builtin"},
    {"id": "stuart_bell",    "name": "Stuart Bell",         "type": "builtin"},
    {"id": "caro_davy",      "name": "Caro Davy",           "type": "builtin"},
    # International voices
    {"id": "giovanni",       "name": "Giovanni (Italian)",  "type": "builtin"},
    {"id": "lola",           "name": "Lola (Spanish)",      "type": "builtin"},
    {"id": "juergen",        "name": "Juergen (German)",    "type": "builtin"},
    {"id": "rafael",         "name": "Rafael (Portuguese)", "type": "builtin"},
    {"id": "estelle",        "name": "Estelle (French)",    "type": "builtin"},
]


def get_tts_model(quantize: bool = True):
    global _tts_model_instance
    if _tts_model_instance is None:
        if TTSModel is None:
            raise ImportError("pocket-tts not found. Please install it.")
        print(f"Loading Pocket TTS model (quantize={quantize})...")
        try:
            # Use load_model factory method which handles config and weights
            _tts_model_instance = TTSModel.load_model(quantize=quantize)
        except Exception as e:
            print(f"Failed to load Pocket TTS model: {e}")
            raise
    return _tts_model_instance


def get_voices_dir():
    """Get the custom voices directory, creating it if needed."""
    voices_dir = get_app_support_dir() / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    return voices_dir


def list_voices():
    """Return all available voices: saved custom voices first, then built-in presets."""
    voices = []

    # Custom voices (from saved .safetensors files)
    voices_dir = get_voices_dir()
    for meta_file in sorted(voices_dir.glob("*.json")):
        try:
            with open(meta_file, "r") as f:
                meta = json.load(f)
            voice_id = meta_file.stem
            safetensors_path = voices_dir / f"{voice_id}.safetensors"
            if safetensors_path.exists():
                voices.append({
                    "id": f"custom:{voice_id}",
                    "name": meta.get("name", voice_id),
                    "type": "custom",
                })
        except (json.JSONDecodeError, KeyError):
            continue

    # Built-in voices
    voices.extend(BUILTIN_VOICES)

    return voices


def save_custom_voice(audio_path, name):
    """Save a custom voice as a reusable preset using export_model_state.

    Args:
        audio_path: Path to the audio file to extract voice from.
        name: Display name for the voice preset.

    Returns:
        dict with voice_id on success, or error on failure.
    """
    if export_model_state is None:
        return {"success": False, "error": "pocket-tts export_model_state not available"}

    try:
        model = get_tts_model()

        # Ensure compatible audio
        compatible_path = ensure_compatible_audio(audio_path)
        if not compatible_path:
            return {"success": False, "error": "Could not process audio file"}

        # Extract voice state
        model_state = model.get_state_for_audio_prompt(compatible_path)

        # Generate a filesystem-safe voice ID from the name
        voice_id = "".join(
            c for c in name.lower().replace(" ", "_") if c.isalnum() or c == "_"
        ).strip("_")
        if not voice_id:
            voice_id = "custom_voice"

        # Ensure unique ID
        voices_dir = get_voices_dir()
        base_id = voice_id
        counter = 1
        while (voices_dir / f"{voice_id}.safetensors").exists():
            voice_id = f"{base_id}_{counter}"
            counter += 1

        # Save the voice state as .safetensors
        safetensors_path = voices_dir / f"{voice_id}.safetensors"
        export_model_state(model_state, str(safetensors_path))

        # Save metadata
        meta_path = voices_dir / f"{voice_id}.json"
        with open(meta_path, "w") as f:
            json.dump({
                "name": name,
                "source_audio": str(audio_path),
            }, f, indent=2)

        return {"success": True, "voice_id": f"custom:{voice_id}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_custom_voice(voice_id):
    """Delete a saved custom voice.

    Args:
        voice_id: The voice ID (with or without 'custom:' prefix).

    Returns:
        dict with success status.
    """
    # Strip the custom: prefix if present
    if voice_id.startswith("custom:"):
        voice_id = voice_id[len("custom:"):]

    voices_dir = get_voices_dir()
    safetensors_path = voices_dir / f"{voice_id}.safetensors"
    meta_path = voices_dir / f"{voice_id}.json"

    if not safetensors_path.exists() and not meta_path.exists():
        return {"success": False, "error": "Voice not found"}

    if safetensors_path.exists():
        safetensors_path.unlink()
    if meta_path.exists():
        meta_path.unlink()

    return {"success": True}


def resolve_voice_preset(voice_preset):
    """Resolve a voice preset ID to the appropriate argument for get_state_for_audio_prompt.

    For custom voices (prefixed with 'custom:'), returns the .safetensors path.
    For built-in voices, returns the voice name string as-is.
    """
    if voice_preset and voice_preset.startswith("custom:"):
        voice_id = voice_preset[len("custom:"):]
        safetensors_path = get_voices_dir() / f"{voice_id}.safetensors"
        if safetensors_path.exists():
            return str(safetensors_path)
        else:
            print(f"Warning: Custom voice '{voice_id}' not found, falling back to 'alba'")
            return "alba"
    return voice_preset


def load_voice_state(model, voice_target):
    """Load model state for a voice target (built-in name or .safetensors path).

    If loading a .safetensors file fails (e.g. due to model architecture or dimension
    changes across Pocket TTS versions), attempts automatic recovery by re-extracting
    the voice state from the source audio file saved in the accompanying .json metadata.

    Args:
        model: Loaded TTSModel instance.
        voice_target: Built-in voice name string or Path/string to a .safetensors file.

    Returns:
        Model state dict ready for generation.
    """
    target_str = str(voice_target)
    if target_str.endswith(".safetensors"):
        path = Path(voice_target)
        try:
            return model.get_state_for_audio_prompt(target_str)
        except Exception as e:
            print(f"Warning: Failed to load voice state from {path.name}: {e}")
            # Check for matching .json metadata to auto-recover
            json_path = path.with_suffix(".json")
            if json_path.exists():
                try:
                    with open(json_path, "r") as f:
                        meta = json.load(f)
                    source_audio = meta.get("source_audio")
                    if source_audio and Path(source_audio).exists():
                        print(f"Auto-migrating legacy voice '{path.stem}' from source audio...")
                        compat_path = ensure_compatible_audio(source_audio)
                        if compat_path:
                            new_state = model.get_state_for_audio_prompt(compat_path)
                            if export_model_state:
                                export_model_state(new_state, str(path))
                                print(f"Successfully migrated voice '{path.stem}' to new model format.")
                            return new_state
                except Exception as recovery_err:
                    print(f"Voice auto-recovery failed for {path.stem}: {recovery_err}")
            raise
    else:
        return model.get_state_for_audio_prompt(voice_target)


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
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Conversion failed ({e}), falling back to original file for native Pocket TTS decoding.")
        # Pocket TTS 3.x natively decodes MP3/WAV/FLAC and resamples to 24kHz
        return str(path)


class PocketTTSPipeline:
    """TTS Pipeline using Pocket TTS for voice cloning."""

    # Silence duration between sentences and paragraphs (in seconds)
    SENTENCE_PAUSE_DURATION = 0.5  # 500ms pause between sentences
    PARAGRAPH_PAUSE_DURATION = 0.9  # 900ms pause between paragraphs

    def __init__(self, ref_audio=None, voice_preset=None, quantize=True):
        self.ref_audio = ensure_compatible_audio(ref_audio) if ref_audio else None
        self.voice_preset = voice_preset
        self._nlp = None
        self._cached_model_state = None
        # Pre-load model
        self.model = get_tts_model(quantize=quantize)

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

        try:
            # Prepare audio prompt — use cached model state if available
            if self._cached_model_state is None:
                if self.ref_audio:
                    # Use provided reference audio (Custom voice cloning)
                    self._cached_model_state = self.model.get_state_for_audio_prompt(self.ref_audio)
                elif self.voice_preset:
                    # Resolve custom: prefix to .safetensors path
                    resolved = resolve_voice_preset(self.voice_preset)
                    try:
                        self._cached_model_state = load_voice_state(self.model, resolved)
                    except Exception as e:
                        print(
                            f"Warning: Preset '{resolved}' failed ({e}). Falling back to 'alba'."
                        )
                        self._cached_model_state = self.model.get_state_for_audio_prompt("alba")
                else:
                    # Default fallback
                    self._cached_model_state = self.model.get_state_for_audio_prompt("alba")

            audio = self.model.generate_audio(
                model_state=self._cached_model_state,
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

    ext = Path(chapter_files[0]).suffix if chapter_files else ".m4a"
    concat_file_path = Path(output_folder) / filename.replace(".epub", f".tmp{ext}")
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

        # If chapter files are already AAC/M4A, stream-copy without re-encoding
        is_aac = False
        if chapter_files and Path(chapter_files[0]).suffix.lower() in (".m4a", ".aac"):
            is_aac = True

        audio_codec_args = (
            ["-c:a", "copy"]
            if is_aac
            else ["-c:a", get_best_aac_encoder(), "-b:a", "64k"]
        )

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
            ]
            + audio_codec_args
            + [
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


def verify_audio_quality(audio_file_path, text_length, audio_data=None):
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

    # Check 2 & 3: Duration and loudness
    try:
        if audio_data is not None and len(audio_data) > 0:
            duration = len(audio_data) / sample_rate
            rms = float(np.sqrt(np.mean(audio_data**2)))
        else:
            try:
                data, sr = soundfile.read(path)
                duration = len(data) / sr
                rms = float(np.sqrt(np.mean(data**2)))
            except Exception:
                duration = probe_duration(path)
                rms = 0.01  # Fallback for formats not supported by soundfile

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
    chapter_files = []

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
        m4a_path = output_path / f"{safe_name}.m4a"
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

        # Check if already exists (check m4a first, fallback to mp3)
        if m4a_path.exists():
            chapter_files.append(m4a_path)
            continue
        elif mp3_path.exists():
            chapter_files.append(mp3_path)
            continue

        audio = pipeline.generate(text, progress_callback=chapter_progress_callback)

        if audio is not None:
            # Write temp WAV then convert to M4A (AAC)
            temp_wav = m4a_path.with_suffix(".tmp.wav")
            soundfile.write(temp_wav, audio, sample_rate)

            encoder = get_best_aac_encoder()
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(temp_wav),
                    "-c:a",
                    encoder,
                    "-b:a",
                    "64k",
                    str(m4a_path),
                ],
                capture_output=True,
                check=True,
            )

            temp_wav.unlink()

            # Verify audio quality using in-memory audio array
            is_valid, issues = verify_audio_quality(m4a_path, len(text), audio_data=audio)
            if not is_valid:
                print(f"Quality issues in {chapter_name}: {issues}")
                # Treat as failure
                if m4a_path.exists():
                    m4a_path.unlink()
                raise RuntimeError(f"Audio verification failed: {'; '.join(issues)}")

            chapter_files.append(m4a_path)

    if chapter_files and has_ffmpeg:
        if progress_callback:
            progress_callback(percent=95, status="Creating M4B audiobook...")

        m4b_path = create_m4b(
            chapter_files,
            f"{book_title} - {book_author}.epub",
            cover_image,
            output_folder,
            title=book_title,
            author=book_author,
        )

        if progress_callback:
            progress_callback(percent=100, status="Complete!")

        if m4b_path:
            return m4b_path

    # If we got here but have no files, something went wrong (e.g. empty chapters)
    if not chapter_files:
        raise RuntimeError("No audio files were generated (empty text or errors).")

    if progress_callback:
        progress_callback(percent=100, status="Complete (Chapters only)!")

    return chapter_files
