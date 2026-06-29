# OpusClip

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ABo-EsMaiL/OpusClip/blob/main/notebooks/opusclip_demo.ipynb)

AI-powered automatic short-video pipeline — transform long-form video into
vertical karaoke-subtitled clips with smart cropping, at zero cost.

## Features

- **100% Free & Open Source** — No paid APIs, SaaS, or commercial SDKs.
- **Offline Transcription** — `faster-whisper` with `large-v3` model.
- **Smart Face Tracking** — MediaPipe-based crop director follows speakers.
- **Bilingual Karaoke Subtitles** — ASS format with word-level highlighting.
- **Single-Pass Rendering** — Subtitles, audio, and fades merged in one pipe.
- **GPU Acceleration** — CUDA for Whisper, NVENC for encoding.
- **Batch Processing** — Multiple videos with isolated outputs and error recovery.
- **Resume Support** — `--resume` flag continues from the last completed step.

## Requirements

| Dependency | Required | Notes |
|-----------|----------|-------|
| Python | >= 3.10 | |
| FFmpeg | Yes | Include `ffmpeg` and `ffprobe` on `PATH` |
| yt-dlp | YouTube only | `pip install yt-dlp` |
| NVIDIA GPU + CUDA | Recommended | Speeds up Whisper (CUDA) and encoding (NVENC) |

## Installation

### Linux / macOS

```bash
git clone https://github.com/ABo-EsMaiL/OpusClip.git
cd OpusClip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -r requirements.txt
```

### Windows

```powershell
git clone https://github.com/ABo-EsMaiL/OpusClip.git
cd OpusClip
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pip install -r requirements.txt
```

### FFmpeg Installation

- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/) and add to `PATH`.

Verify: `ffmpeg -version && ffprobe -version`

## Configuration

Set your LLM API key (required for clip selection and metadata generation):

```bash
export OPUSCLIP_API_KEY="sk-..."           # Get yours at https://opencode.ai/zen
export LLM_BASE_URL="https://opencode.ai/zen/v1"   # optional, default: opencode.ai
export LLM_MODEL="deepseek-v4-flash-free"  # optional, default: deepseek-v4-flash-free
```

All configuration fields are documented in [docs/configuration.md](docs/configuration.md).
Architecture and API details are in [docs/architecture.md](docs/architecture.md) and
[docs/api.md](docs/api.md).

## Usage

### Single Video

```bash
python -m opusclip input.mp4 --output ./output
```

### YouTube Video

```bash
python -m opusclip "https://youtube.com/watch?v=..." --output ./output
```

### Batch Processing

```bash
python -m opusclip video1.mp4 video2.mp4 "https://youtube.com/watch?v=..." --output ./output
```

### Resume Interrupted Run

```bash
python -m opusclip input.mp4 --output ./output --resume
```

### GPU Encoding

```bash
python -m opusclip input.mp4 --encoder h264_nvenc --output ./output
```

Falls back to `libx264` automatically if NVENC is unavailable (with a warning).

### Legacy Renderer

```bash
python -m opusclip input.mp4 --renderer legacy --output ./output
```

### Additional Options

```bash
python -m opusclip input.mp4 \
  --output ./output \
  --min-clips 3 \
  --max-clips 8 \
  --log-level DEBUG
```

See [docs/api.md](docs/api.md) for the complete CLI reference and
[docs/configuration.md](docs/configuration.md) for all configuration options.

## Output Structure

After a successful run, the output directory contains:

```
output/
└── input_video_a1b2c3/          # Per-source directory (hash suffix prevents collisions)
    ├── pipeline_summary.json     # Top-level results
    ├── clips/
    │   ├── clip_01_FINAL.mp4     # Rendered video
    │   ├── clip_01_thumb.jpg     # Thumbnail
    │   ├── clip_02_FINAL.mp4
    │   └── clip_02_thumb.jpg
    └── metadata/
        ├── clip_01_metadata.json # Per-clip social metadata
        └── clip_02_metadata.json
```

### pipeline_summary.json

```json
{
  "source": "input.mp4",
  "source_duration_s": 3600.0,
  "total_clips": 8,
  "successful_clips": 8,
  "failed_clips": 0,
  "clips": [
    {
      "number": 1,
      "video": "output/.../clips/clip_01_FINAL.mp4",
      "thumbnail": "output/.../clips/clip_01_thumb.jpg",
      "success": true,
      "metadata": {
        "title": "Key Insight: ...",
        "description": "...",
        "hashtags": ["#AI", "#tutorial"]
      }
    }
  ]
}
```

## GPU Acceleration

### NVIDIA NVENC (Hardware Encoding)

1. Verify your GPU supports NVENC: `ffmpeg -encoders | grep nvenc`
2. Run with: `python -m opusclip input.mp4 --encoder h264_nvenc`
3. If NVENC is unavailable, the pipeline automatically falls back to `libx264`.

### CUDA for Whisper

Ensure PyTorch is installed with CUDA support:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

The pipeline uses CUDA by default (`WHISPER_DEVICE=cuda`). Set
`WHISPER_DEVICE=cpu` to force CPU inference.

## Troubleshooting

### "OPUSCLIP_API_KEY environment variable is missing"

Set your API key before running:

```bash
export OPUSCLIP_API_KEY="your-key-here"
```

### "FFmpeg failed" or "ffmpeg not found"

Install FFmpeg and ensure it's on your `PATH`. Verify with `ffmpeg -version`.

### "MediaPipe model not found"

The face landmarker model is downloaded automatically on first use.
Ensure internet access for the initial download.

### "Whisper model download fails"

Whisper models are cached to `~/.cache/whisper/`. If the download fails
due to network issues, pre-download:

```python
from faster_whisper import WhisperModel
WhisperModel("large-v3", download_root="/path/to/cache")
```

Then set `WHISPER_MODEL=large-v3` as usual — the cached path is resolved
automatically.

### "CUDA out of memory" (Whisper)

Reduce GPU memory usage by switching to a smaller model:

```bash
export WHISPER_MODEL=medium
```

Or use CPU: `export WHISPER_DEVICE=cpu` (slower but stable).

### "yt-dlp not found"

Install yt-dlp: `pip install yt-dlp`

### "Encoder h264_nvenc not available"

The pipeline falls back to `libx264` automatically. To suppress the warning,
either install NVIDIA drivers with NVENC support or use the default encoder.

### Pipeline produces 0 clips

The LLM may have rejected all candidates. Check:
- Your transcript has sufficient content (long enough video).
- Your API key has access to the configured model.
- `max_llm_chars` is large enough for the full transcript.

## Performance Tuning

| Setting | Recommendation | Effect |
|---------|---------------|--------|
| `--encoder h264_nvenc` | If GPU supports NVENC | 2-4x faster encoding |
| `WHISPER_MODEL=medium` | If VRAM < 8GB | Reduces memory, slight accuracy loss |
| `max_llm_chars=40000` | For long transcripts | More context, higher API cost |
| `--renderer legacy` | If optimized renderer has issues | Matches original notebook behavior |

## Batch Processing Behavior

- Each source gets an isolated output directory with a stable hash suffix.
- `--resume` is per-source and source-verified (cache from a different video
  is ignored).
- Errors in one source do not abort the batch; per-source errors are reported
  in the JSON output.

## Project Status

See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for implementation progress,
[CHANGELOG.md](CHANGELOG.md) for a complete history of changes, and
[CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

MIT
