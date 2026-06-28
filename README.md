# OpusClip Production Pipeline

![OpusClip Architecture Placeholder](docs/architecture.md)

A production-grade, modular, and 100% Free and Open-Source (FOSS) pipeline for automating the creation of short-form, karaoke-subtitled videos (like YouTube Shorts, TikToks, and Reels) from long-form video content.

## Features
- **100% Zero-Cost Policy**: Runs on free tools only. No paid APIs, SaaS platforms, or commercial SDKs.
- **Robust AI Integration**: Uses `faster-whisper` for offline transcription, `MediaPipe` for face tracking, and FOSS LLM endpoints for smart clip selection.
- **Professional Rendering**: Uses FFmpeg and `libass` to render 1080×1920 (CRF 18–22) videos with accurate bilingual karaoke-style subtitles.
- **Smart Cropping**: AI-driven face tracking ensures the primary speaker is always centered in the vertical frame.
- **Batch Processing Capable**: Designed to handle multiple videos up to 4 hours in length efficiently.

## Architecture
See [docs/architecture.md](docs/architecture.md) for the detailed pipeline architecture.

## Installation

```bash
git clone https://github.com/yourusername/OpusClip.git
cd OpusClip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration
Configuration is handled via environment variables and a dedicated configuration file (TBD in Phase 3). 

### Environment Variables
- `OPUSCLIP_API_KEY`: API key for the LLM provider (e.g., Groq, Gemini)
- `LLM_BASE_URL`: (Optional) Custom endpoint for the LLM provider

## Usage Examples

### CLI Example (TBD in Phase 8)
```bash
python -m opusclip process "https://youtube.com/watch?v=..." --output-dir ./outputs
```

## Folder Structure
- `src/` - Core business logic and modules
- `docs/` - Architecture and planning documentation
- `tests/` - Unit and integration tests
- `examples/` - Sample scripts and data
- `fonts/` - Bundled TTF fonts for subtitle rendering

## Development Workflow
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on our strict 11-phase implementation workflow and pull request guidelines.

## Future Roadmap
- Phase 1-10: Complete modularization and stabilization.
- Phase 11: Release the standalone demonstration Google Colab notebook.

## License
MIT License. See [LICENSE](LICENSE) for details.

## Credits
Built with FOSS: FFmpeg, MediaPipe, Faster-Whisper, OpenCV, and yt-dlp.
