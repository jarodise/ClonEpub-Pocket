# ClonEpub 🎧

Convert EPUB e-books to high-quality audiobooks with voice cloning. Optimized for Apple Silicon Macs.

![UI Mockup](docs/imgs/pywebview_ui_mockup.png)

## Features

- 🎤 **Voice Cloning** - Clone any voice from a 5-15 second audio sample
- 📚 **EPUB Support** - Load and convert standard EPUB files
- ⚡ **Apple Silicon Optimized** - Uses MLX for fast inference on M1/M2/M3 Macs
- 🖥️ **Modern UI** - Beautiful dark-themed interface with PyWebView
- 📥 **Easy Setup** - Models download automatically on first run

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.10-3.12
- ffmpeg (for audio encoding)

## Installation

> **Note**: This project uses [uv](https://docs.astral.sh/uv/) for Python environment management. If you don't have uv installed:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

```bash
# Clone the repository
git clone https://github.com/jarodise/ClonEpub.git
cd ClonEpub

# Create virtual environment and install dependencies (uv handles everything)
uv venv
source .venv/bin/activate
uv pip install -e .

# Download spaCy model
uv run python -m spacy download en_core_web_sm
```

## Usage

```bash
# Launch the GUI
uv run clonepub
```

### Voice Cloning

For best results with voice cloning:
- Use a 5-15 second clear audio sample
- Single speaker, no background noise
- Optionally provide a transcript for better accuracy

## First Run

On first launch, ClonEpub will download:
- **Chatterbox Turbo** (~800 MB) - The TTS model
- **spaCy en_core_web_sm** (~12 MB) - For sentence detection

Models are stored in `~/Library/Application Support/ClonEpub/`

## Tech Stack

- **TTS Engine**: Chatterbox Turbo (MLX optimized)
- **UI Framework**: PyWebView
- **ML Framework**: MLX (Apple Silicon)
- **Audio Processing**: soundfile, ffmpeg

## Credits

Based on [audiblez](https://github.com/santinic/audiblez) by Claudio Santini.

## License

MIT License
