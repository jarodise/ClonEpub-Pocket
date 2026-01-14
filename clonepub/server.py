"""ClonEpub HTTP Server - Flask wrapper for Electron integration.

This server exposes the ClonEpubAPI as HTTP endpoints, allowing
the Electron frontend to communicate with the Python backend.
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

from clonepub.api import ClonEpubAPI

app = Flask(__name__)
CORS(app)  # Allow requests from Electron renderer

# Global API instance
api = ClonEpubAPI()


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Electron to verify server is ready."""
    return jsonify({"status": "ok"})


# ─────────────────────────────────────────────────────────────────────────────
# Model Management
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/api/check_models", methods=["GET"])
def check_models():
    """Check if required models are installed."""
    return jsonify(api.check_models())


@app.route("/api/dependencies", methods=["GET"])
def get_dependencies():
    """Get status of all required dependencies."""
    return jsonify(api.get_all_dependencies())


@app.route("/api/start_download", methods=["POST"])
def start_download():
    """Start downloading all missing models in background."""
    return jsonify(api.start_model_download())


@app.route("/api/download_progress", methods=["GET"])
def download_progress():
    """Get current download progress."""
    return jsonify(api.get_download_progress())


@app.route("/api/downloads_dir", methods=["GET"])
def downloads_dir():
    """Get the system Downloads directory."""
    return jsonify({"path": api.get_downloads_dir()})


# ─────────────────────────────────────────────────────────────────────────────
# EPUB Handling
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/api/load_epub", methods=["POST"])
def load_epub():
    """Load an EPUB file and return metadata."""
    data = request.get_json()
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"success": False, "error": "file_path is required"})
    return jsonify(api.load_epub(file_path))


@app.route("/api/chapter/<int:index>", methods=["GET"])
def get_chapter(index):
    """Get content of a specific chapter."""
    return jsonify(api.get_chapter_content(index))


@app.route("/api/chapter/<int:index>/update", methods=["POST"])
def update_chapter(index):
    """Update content of a specific chapter."""
    data = request.get_json()
    text = data.get("text", "")
    return jsonify(api.update_chapter_content(index, text))


@app.route("/api/chapter/<int:index>/toggle", methods=["POST"])
def toggle_chapter(index):
    """Toggle selection state of a chapter."""
    return jsonify(api.toggle_chapter_selection(index))


@app.route("/api/selected_chapters", methods=["GET"])
def selected_chapters():
    """Get list of selected chapters."""
    return jsonify(api.get_selected_chapters())


# ─────────────────────────────────────────────────────────────────────────────
# Voice Cloning
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/api/preview_voice", methods=["POST"])
def preview_voice():
    """Generate a voice preview."""
    data = request.get_json()
    text = data.get("text", "")
    ref_audio = data.get("ref_audio")
    ref_text = data.get("ref_text")
    return jsonify(api.preview_voice(text, ref_audio, ref_text))


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/api/start_synthesis", methods=["POST"])
def start_synthesis():
    """Start audiobook synthesis in background thread."""
    data = request.get_json()
    output_folder = data.get("output_folder")
    ref_audio = data.get("ref_audio")
    ref_text = data.get("ref_text")
    speed = data.get("speed", 1.0)

    if not output_folder:
        return jsonify({"success": False, "error": "output_folder is required"})

    return jsonify(api.start_synthesis(output_folder, ref_audio, ref_text, speed))


@app.route("/api/synthesis_progress", methods=["GET"])
def synthesis_progress():
    """Get current synthesis progress."""
    return jsonify(api.get_synthesis_progress())


@app.route("/api/stop_synthesis", methods=["POST"])
def stop_synthesis():
    """Request synthesis to stop."""
    return jsonify(api.stop_synthesis())


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main():
    """Run the Flask server."""
    port = int(os.environ.get("CLONEPUB_PORT", 8765))
    print(f"Starting ClonEpub server on http://127.0.0.1:{port}")

    # Disable Flask's default reloader and debugger for production
    # threaded=True allows handling multiple requests concurrently
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
