"""ClonEpub - PyWebView Entry Point."""

import os
import webview
from pathlib import Path

from clonepub.api import ClonEpubAPI


def get_ui_path():
    """Get the path to UI files."""
    return Path(__file__).parent / "ui"


def main():
    """Launch the ClonEpub application."""
    api = ClonEpubAPI()
    ui_path = get_ui_path()

    window = webview.create_window(
        "ClonEpub",
        url=str(ui_path / "index.html"),
        js_api=api,
        width=1200,
        height=800,
        min_size=(900, 700),
    )

    # Store window reference for API access
    api.window = window

    webview.start(debug=False)


if __name__ == "__main__":
    main()
