# Configuration Reference

All pipeline behaviour is controlled via `PipelineConfig`. Configuration
resolution follows this precedence (highest wins):

**CLI flags > constructor arguments > environment variables > defaults**

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPUSCLIP_API_KEY` | — | API key for the LLM provider (required). |
| `LLM_BASE_URL` | `https://opencode.ai/zen/v1` | Custom endpoint for the LLM API (e.g. Groq, OpenAI compatibles). |
| `LLM_MODEL` | `deepseek-v4-flash-free` | Model identifier for clip selection and metadata generation. |
| `WHISPER_MODEL` | `large-v3` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`). |
| `WHISPER_DEVICE` | `cuda` | Device for Whisper inference (`cuda` or `cpu`). |
| `ENCODER` | `libx264` | FFmpeg video encoder (e.g. `h264_nvenc` for NVIDIA GPUs). |
| `RENDERER` | `optimized` | Renderer backend (`optimized` or `legacy`). |
| `OUTPUT_DIR` | `opusclip_output` | Default output directory for pipeline results. |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

## PipelineConfig Fields

### API & Models

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | `str` | `""` | LLM API key (loaded from `OPUSCLIP_API_KEY` env). |
| `llm_base_url` | `str` | `"https://opencode.ai/zen/v1"` | Custom LLM API endpoint. |
| `llm_model` | `str` | `"deepseek-v4-flash-free"` | LLM model name. |
| `whisper_model` | `str` | `"large-v3"` | Faster-Whisper model size. |
| `whisper_device` | `str` | `"cuda"` | Device for Whisper. |

### Render Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `encoder` | `str` | `"libx264"` | FFmpeg encoder. Falls back to `libx264` if specified encoder unavailable. |
| `renderer_backend` | `str` | `"optimized"` | `"optimized"` (single-pass) or `"legacy"` (two-pass). |
| `output_dir` | `Path` | `"opusclip_output"` | Root output path. |
| `log_level` | `str` | `"INFO"` | Console log level. |

### Clip Quality

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_llm_chars` | `int` | `28000` | Max characters sent to LLM per call. Warns if coverage < 50%. |
| `clip_crf` | `int` | `20` | CRF for final clip encoding (lower = higher quality). |
| `raw_clip_crf` | `int` | `22` | CRF for intermediate raw extract before subtitle burn. |
| `broll_border` | `int` | `5` | Border width in pixels for blurred-background (b-roll) frames. |

### Clip Constraints

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_clips` | `int` | `5` | Minimum number of clips to extract. |
| `max_clips` | `int` | `12` | Maximum number of clips to extract. |
| `min_duration` | `int` | `40` | Minimum clip duration in seconds. |
| `max_duration` | `int` | `120` | Maximum clip duration in seconds. |
| `min_virality` | `int` | `65` | Minimum virality score (0-100) for a clip to be included. |

### API Retry Policy

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_retry_attempts` | `int` | `3` | Number of LLM API retry attempts. |
| `api_retry_delay_s` | `float` | `2.0` | Initial retry delay in seconds. |
| `api_retry_backoff_factor` | `float` | `2.0` | Exponential backoff multiplier. |

### Face Detection

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mediapipe_model_path` | `str` | `"face_landmarker.task"` | Path to MediaPipe FaceLandmarker model. |
| `speaking_mar` | `float` | `0.05` | Mouth-open score threshold to consider face "speaking". |
| `min_face_area` | `float` | `0.003` | Minimum face area as fraction of frame to be tracked. |
| `state_debounce_s` | `float` | `0.6` | Seconds a crop state must persist before switching. |

## CLI Flags

| Flag | Maps to Config Field |
|------|---------------------|
| `--output`, `-o` | `output_dir` |
| `--min-clips` | `min_clips` |
| `--max-clips` | `max_clips` |
| `--renderer` | `renderer_backend` (choices: `optimized`, `legacy`) |
| `--encoder` | `encoder` |
| `--log-level` | `log_level` |
| `--resume` | Resume via `CacheManager` (no config field) |

## Using PipelineConfig Programmatically

```python
from opusclip.config import PipelineConfig

# With defaults
config = PipelineConfig()

# With environment-aware overrides
config = PipelineConfig.from_env(
    min_clips=3,
    max_clips=8,
    encoder="h264_nvenc",
)
```
