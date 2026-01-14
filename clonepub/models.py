"""ClonEpub Model Manager - Handles model downloading and status checking."""

import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about a required model."""

    id: str
    name: str
    size_mb: int
    type: str  # "tts_main", "tts_dependency", "nlp"


# Registry of all required models
REQUIRED_MODELS: List[ModelInfo] = []

SPACY_MODEL = ModelInfo(
    id="en_core_web_sm", name="spaCy English Model", size_mb=12, type="nlp"
)


def get_huggingface_cache_dir() -> Path:
    """Get the HuggingFace cache directory."""
    return Path.home() / ".cache" / "huggingface" / "hub"


def _model_id_to_cache_name(model_id: str) -> str:
    """Convert model ID to cache directory name format."""
    # HuggingFace format: models--org--name
    return f"models--{model_id.replace('/', '--')}"


def check_model_installed(model_id: str) -> bool:
    """Check if a HuggingFace model is installed."""
    cache_dir = get_huggingface_cache_dir()
    cache_name = _model_id_to_cache_name(model_id)
    model_dir = cache_dir / cache_name

    if not model_dir.exists():
        return False

    # Check for snapshots (actual model files)
    snapshots_dir = model_dir / "snapshots"
    if snapshots_dir.exists() and any(snapshots_dir.iterdir()):
        return True

    return False


def get_model_size_on_disk(model_id: str) -> int:
    """Get the actual size of a model on disk in MB."""
    cache_dir = get_huggingface_cache_dir()
    cache_name = _model_id_to_cache_name(model_id)
    model_dir = cache_dir / cache_name

    if not model_dir.exists():
        return 0

    total_size = 0
    for path in model_dir.rglob("*"):
        if path.is_file():
            total_size += path.stat().st_size

    return total_size // (1024 * 1024)  # Convert to MB


def check_spacy_model_installed() -> bool:
    """Check if the spaCy model is installed."""
    try:
        import spacy

        spacy.load("en_core_web_sm")
        return True
    except (OSError, ImportError):
        return False


def get_bundled_bin_dir() -> Path:
    """Get the bundled binaries directory (for ffmpeg etc)."""
    # When running from source: clonepub/bin/
    # When running from PyInstaller bundle: Contents/Resources/bin/
    import sys

    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        return bundle_dir / "bin"
    else:
        # Running from source
        return Path(__file__).parent / "bin"


def get_ffmpeg_path() -> Optional[str]:
    """Get path to ffmpeg binary, checking bundled first then system."""
    # Check bundled ffmpeg first
    bundled = get_bundled_bin_dir() / "ffmpeg"
    if bundled.exists():
        return str(bundled)

    # Fall back to system ffmpeg
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None


def get_ffprobe_path() -> Optional[str]:
    """Get path to ffprobe binary, checking bundled first then system."""
    # Check bundled ffprobe first
    bundled = get_bundled_bin_dir() / "ffprobe"
    if bundled.exists():
        return str(bundled)

    # Fall back to system ffprobe
    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe

    return None


def check_ffmpeg_installed() -> bool:
    """Check if ffmpeg is available (bundled or system)."""
    return get_ffmpeg_path() is not None


def get_all_dependencies_status() -> Dict[str, Any]:
    """Get status of all required dependencies."""
    models_status = []
    total_size_mb = 0
    all_installed = True

    # Check HuggingFace models
    for model in REQUIRED_MODELS:
        installed = check_model_installed(model.id)
        actual_size = get_model_size_on_disk(model.id) if installed else 0

        models_status.append(
            {
                "id": model.id,
                "name": model.name,
                "type": model.type,
                "size_mb": model.size_mb,
                "actual_size_mb": actual_size,
                "installed": installed,
            }
        )

        if not installed:
            all_installed = False
            total_size_mb += model.size_mb

    # Check spaCy model
    spacy_installed = check_spacy_model_installed()
    models_status.append(
        {
            "id": SPACY_MODEL.id,
            "name": SPACY_MODEL.name,
            "type": SPACY_MODEL.type,
            "size_mb": SPACY_MODEL.size_mb,
            "actual_size_mb": SPACY_MODEL.size_mb if spacy_installed else 0,
            "installed": spacy_installed,
        }
    )

    if not spacy_installed:
        all_installed = False
        total_size_mb += SPACY_MODEL.size_mb

    return {
        "models": models_status,
        "all_installed": all_installed,
        "total_download_mb": total_size_mb,
        "ffmpeg_installed": check_ffmpeg_installed(),
    }


def download_huggingface_model(
    model_id: str, progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """
    Download a model from HuggingFace Hub.

    Args:
        model_id: The model ID (e.g., "mlx-community/chatterbox-turbo-fp16")
        progress_callback: Optional callback(downloaded_bytes, total_bytes)

    Returns:
        True if successful, False otherwise
    """
    try:
        from huggingface_hub import snapshot_download

        # Download the model
        snapshot_download(
            repo_id=model_id,
            # HuggingFace Hub handles progress internally
            # We can add tqdm progress bar integration if needed
        )
        return True
    except Exception as e:
        print(f"Error downloading {model_id}: {e}")
        return False


def download_spacy_model() -> bool:
    """Download the spaCy model."""
    try:
        import spacy.cli

        spacy.cli.download("en_core_web_sm")
        return True
    except Exception as e:
        print(f"Error downloading spaCy model: {e}")
        return False


def download_all_models(
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, bool]:
    """
    Download all required models.

    Args:
        progress_callback: Optional callback(model_name, current_model_index, total_models)

    Returns:
        Dict mapping model IDs to success status
    """
    results = {}
    total_models = len(REQUIRED_MODELS) + 1  # +1 for spaCy

    # Download HuggingFace models
    for i, model in enumerate(REQUIRED_MODELS):
        if progress_callback:
            progress_callback(model.name, i + 1, total_models)

        if not check_model_installed(model.id):
            results[model.id] = download_huggingface_model(model.id)
        else:
            results[model.id] = True  # Already installed

    # Download spaCy model
    if progress_callback:
        progress_callback(SPACY_MODEL.name, total_models, total_models)

    if not check_spacy_model_installed():
        results[SPACY_MODEL.id] = download_spacy_model()
    else:
        results[SPACY_MODEL.id] = True

    return results
