"""ClonEpub - EPUB to Audiobook with Voice Cloning."""

from clonepub.core import (
    PocketTTSPipeline,
    generate_audiobook,
    load_epub,
)

__version__ = "1.3.1"
__all__ = [
    "PocketTTSPipeline",
    "load_epub",
    "generate_audiobook",
]
