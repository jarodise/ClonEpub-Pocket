"""ClonEpub API - Bridge between PyWebView and core functionality."""

import webview

import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from clonepub.core import (
    load_epub,
    generate_audiobook,
    PocketTTSPipeline,
)
from clonepub.models import (
    get_all_dependencies_status,
    download_huggingface_model,
    download_spacy_model,
    check_ffmpeg_installed,
    REQUIRED_MODELS,
    SPACY_MODEL,
)


class ClonEpubAPI:
    """API class exposed to JavaScript via PyWebView."""

    def __init__(self):
        self.window = None
        self._current_book = None
        self._chapters = []
        self._synthesis_thread = None
        self._synthesis_progress = {"percent": 0, "status": "Idle", "running": False}
        self._stop_requested = False
        self._download_thread = None
        self._download_progress = {
            "current_model": "",
            "model_index": 0,
            "total_models": 0,
            "status": "idle",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Model Management
    # ─────────────────────────────────────────────────────────────────────────

    def get_all_dependencies(self) -> Dict[str, Any]:
        """Get status of all required dependencies."""
        return get_all_dependencies_status()

    def check_models(self) -> Dict[str, Any]:
        """Check if required models are installed (legacy, use get_all_dependencies)."""
        status = get_all_dependencies_status()
        return {
            "all_installed": status["all_installed"],
            "ffmpeg_installed": status["ffmpeg_installed"],
            "total_download_mb": status["total_download_mb"],
            "models": status["models"],
        }

    def start_model_download(self) -> Dict[str, Any]:
        """Start downloading all missing models in background."""
        if self._download_thread and self._download_thread.is_alive():
            return {"success": False, "error": "Download already in progress"}

        self._download_progress = {
            "current_model": "",
            "model_index": 0,
            "total_models": len(REQUIRED_MODELS) + 1,
            "status": "starting",
        }

        def run_download():
            total = len(REQUIRED_MODELS) + 1

            # Download HuggingFace models
            for i, model in enumerate(REQUIRED_MODELS):
                self._download_progress = {
                    "current_model": model.name,
                    "model_index": i + 1,
                    "total_models": total,
                    "status": "downloading",
                }
                download_huggingface_model(model.id)

            # Download spaCy model
            self._download_progress = {
                "current_model": SPACY_MODEL.name,
                "model_index": total,
                "total_models": total,
                "status": "downloading",
            }
            download_spacy_model()

            self._download_progress["status"] = "complete"

        self._download_thread = threading.Thread(target=run_download, daemon=True)
        self._download_thread.start()

        return {"success": True, "message": "Download started"}

    def get_download_progress(self) -> Dict[str, Any]:
        """Get current download progress."""
        return self._download_progress

    def get_downloads_dir(self) -> str:
        """Get the system Downloads directory."""
        return str(Path.home() / "Downloads")

    # ─────────────────────────────────────────────────────────────────────────
    # EPUB Handling
    # ─────────────────────────────────────────────────────────────────────────

    def open_file_dialog(self) -> Optional[str]:
        """Open file dialog to select EPUB file."""
        if not self.window:
            return None

        if hasattr(webview, "FileDialog"):
            dialog_type = webview.FileDialog.OPEN
        else:
            dialog_type = webview.OPEN_DIALOG

        result = self.window.create_file_dialog(
            dialog_type=dialog_type,
            file_types=("EPUB Files (*.epub)",),
        )

        if result and len(result) > 0:
            return result[0]
        return None

    def load_epub(self, file_path: str) -> Dict[str, Any]:
        """Load an EPUB file and return metadata."""
        try:
            book_data = load_epub(file_path)
            self._current_book = book_data
            self._chapters = book_data["chapters"]

            # Convert cover bytes to base64 for display
            cover_b64 = None
            if book_data.get("cover"):
                import base64

                cover_b64 = base64.b64encode(book_data["cover"]).decode("utf-8")

            return {
                "success": True,
                "title": book_data["title"],
                "author": book_data["author"],
                "total_chars": book_data["total_chars"],
                "cover": cover_b64,
                "chapters": [
                    {
                        "index": c["index"],
                        "name": c["name"],
                        "length": c["length"],
                        "selected": c["selected"],
                    }
                    for c in self._chapters
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_chapter_content(self, index: int) -> Dict[str, Any]:
        """Get content of a specific chapter."""
        for chapter in self._chapters:
            if chapter["index"] == index:
                return {
                    "success": True,
                    "text": chapter["text"],
                    "name": chapter["name"],
                }
        return {"success": False, "error": "Chapter not found"}

    def update_chapter_content(self, index: int, text: str) -> Dict[str, Any]:
        """Update content of a specific chapter."""
        for chapter in self._chapters:
            if chapter["index"] == index:
                chapter["text"] = text
                chapter["length"] = len(text)
                return {"success": True}
        return {"success": False, "error": "Chapter not found"}

    def toggle_chapter_selection(self, index: int) -> Dict[str, Any]:
        """Toggle selection state of a chapter."""
        for chapter in self._chapters:
            if chapter["index"] == index:
                chapter["selected"] = not chapter["selected"]
                return {"success": True, "selected": chapter["selected"]}
        return {"success": False, "error": "Chapter not found"}

    def get_selected_chapters(self) -> List[Dict[str, Any]]:
        """Get list of selected chapters."""
        return [c for c in self._chapters if c.get("selected", False)]

    # ─────────────────────────────────────────────────────────────────────────
    # Voice Cloning
    # ─────────────────────────────────────────────────────────────────────────

    def select_reference_audio(self) -> Optional[str]:
        """Open file dialog to select reference audio for voice cloning."""
        if not self.window:
            return None

        if hasattr(webview, "FileDialog"):
            dialog_type = webview.FileDialog.OPEN
        else:
            dialog_type = webview.OPEN_DIALOG

        result = self.window.create_file_dialog(
            dialog_type=dialog_type,
            file_types=("Audio Files (*.mp3;*.wav;*.m4a)",),
        )

        if result and len(result) > 0:
            return result[0]
        return None

    def preview_voice(
        self,
        text: str,
        ref_audio: Optional[str] = None,
        voice_preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a voice preview."""
        try:
            pipeline = PocketTTSPipeline(ref_audio=ref_audio, voice_preset=voice_preset)
            audio = pipeline.generate(text[:500])  # Limit preview length

            if audio is not None:
                import io
                import base64
                import soundfile

                # Save to memory buffer and encode to base64
                buffer = io.BytesIO()
                soundfile.write(buffer, audio, 24000, format="WAV")
                buffer.seek(0)
                audio_b64 = base64.b64encode(buffer.read()).decode("utf-8")

                return {"success": True, "audio_base64": audio_b64}

            return {"success": False, "error": "Failed to generate audio"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────────
    # Synthesis
    # ─────────────────────────────────────────────────────────────────────────

    def select_output_folder(self) -> Optional[str]:
        """Open folder dialog to select output folder."""
        if not self.window:
            return None

        if hasattr(webview, "FolderDialog"):
            dialog_type = webview.FolderDialog.OPEN
        elif hasattr(webview, "FOLDER_DIALOG"):
            dialog_type = webview.FOLDER_DIALOG
        else:
            # Fallback for older versions if needed, though FOLDER_DIALOG is standard
            dialog_type = 20  # standard constant usually

        result = self.window.create_file_dialog(
            dialog_type=dialog_type,
        )

        if result and len(result) > 0:
            return result[0]
        return None

    def start_synthesis(
        self,
        output_folder: str,
        ref_audio: Optional[str] = None,
        voice_preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start audiobook synthesis in background thread."""
        if self._synthesis_thread and self._synthesis_thread.is_alive():
            return {"success": False, "error": "Synthesis already in progress"}

        selected_chapters = self.get_selected_chapters()
        if not selected_chapters:
            return {"success": False, "error": "No chapters selected"}

        self._stop_requested = False
        self._synthesis_progress = {
            "percent": 0,
            "status": "Starting...",
            "running": True,
        }

        def run_synthesis():
            try:

                def progress_callback(percent, status):
                    if self._stop_requested:
                        raise InterruptedError("Synthesis stopped by user")
                    self._synthesis_progress = {
                        "percent": percent,
                        "status": status,
                        "running": True,
                    }

                # Prepare metadata
                # Prepare metadata and output directory
                book_title = (
                    self._current_book.get("title", "Audiobook")
                    if self._current_book
                    else "Audiobook"
                )
                book_author = (
                    self._current_book.get("author", "Unknown")
                    if self._current_book
                    else "Unknown"
                )
                cover_image = (
                    self._current_book.get("cover") if self._current_book else None
                )

                # Create book-specific output directory
                # Sanitize title for filesystem
                safe_title = "".join(
                    c for c in book_title if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                book_output_dir = Path(output_folder) / safe_title
                book_output_dir.mkdir(parents=True, exist_ok=True)

                result = generate_audiobook(
                    chapters=selected_chapters,
                    output_folder=str(book_output_dir),
                    ref_audio=ref_audio,
                    voice_preset=voice_preset,
                    progress_callback=progress_callback,
                    book_title=book_title,
                    book_author=book_author,
                    cover_image=cover_image,
                )

                if isinstance(result, str):
                    status_msg = f"Complete! Saved to {Path(result).name}"
                else:
                    status_msg = f"Complete! Generated {len(result)} chapters."

                self._synthesis_progress = {
                    "percent": 100,
                    "status": status_msg,
                    "running": False,
                }
            except InterruptedError:
                self._synthesis_progress = {
                    "percent": self._synthesis_progress["percent"],
                    "status": "Stopped",
                    "running": False,
                }
            except Exception as e:
                self._synthesis_progress = {
                    "percent": self._synthesis_progress["percent"],
                    "status": f"Error: {str(e)}",
                    "running": False,
                }

        self._synthesis_thread = threading.Thread(target=run_synthesis, daemon=True)
        self._synthesis_thread.start()

        return {"success": True, "message": "Synthesis started"}

    def get_synthesis_progress(self) -> Dict[str, Any]:
        """Get current synthesis progress."""
        return self._synthesis_progress

    def stop_synthesis(self) -> Dict[str, Any]:
        """Request synthesis to stop."""
        self._stop_requested = True
        return {"success": True, "message": "Stop requested"}
