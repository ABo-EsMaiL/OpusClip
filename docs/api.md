# API Reference

## Core Classes

### `Pipeline` (`src/opusclip/pipeline.py`)

Main orchestrator. Accepts all providers via constructor injection.

```python
class Pipeline:
    def __init__(
        self,
        config: PipelineConfig,
        input_provider: InputProvider,
        transcription_provider: TranscriptionProvider,
        clip_selector: ClipSelector,
        face_detector: FaceDetector,
        subtitle_renderer: SubtitleRenderer,
        video_renderer: VideoRenderer,
        metadata_generator: MetadataGenerator,
    )
```

**Public methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `run(source, resume=False)` | `PipelineResult` | Process a single video source. |
| `run_batch(sources, resume=False)` | `list[PipelineResult]` | Process multiple sources. Errors in one source don't abort the batch. |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `metrics` | `PipelineMetrics` | Metrics from the most recent `run()` call. |

### `PipelineConfig` (`src/opusclip/config.py`)

Central configuration dataclass. See [configuration.md](configuration.md).

```python
class PipelineConfig:
    api_key: str
    llm_base_url: str
    llm_model: str
    # ... 20+ fields

    @classmethod
    def from_env(cls, **cli_overrides) -> PipelineConfig
```

### `PipelineContext` (`src/opusclip/context.py`)

Holds per-run state passed between pipeline stages.

```python
@dataclass
class PipelineContext:
    video_path: Optional[Path]
    video_width: int
    video_height: int
    video_fps: float
    duration: float
    target_width: int  # default 1080
    target_height: int  # default 1920
    src_crop_w: int
    transcript_data: dict
    selected_clips: list
    render_state: dict
    output_dir: Optional[Path]
```

### Result Types

```python
@dataclass
class PipelineResult:
    clips: list[ClipResult]
    output_dir: Optional[Path]
    duration: float
    total_clips: int
    successful_clips: int
    failed_clips: int
    source: str
    error: Optional[str]

@dataclass
class ClipResult:
    number: int
    video_path: Path
    thumbnail_path: Path
    metadata: Optional[ClipMetadata]
    success: bool
    error: Optional[str]
```

## Provider Interfaces

### `InputProvider` (`src/opusclip/input/base.py`)

```python
class InputProvider(ABC):
    def acquire(self, source: str, output_dir: Path) -> VideoMetadata
```

Implementations: `LocalFileProvider`, `YouTubeProvider`.

### `TranscriptionProvider` (`src/opusclip/transcription/base.py`)

```python
class TranscriptionProvider(ABC):
    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult
    def cleanup(self) -> None
```

Implementation: `WhisperProvider`.

### `ClipSelector` (`src/opusclip/clip_selection/base.py`)

```python
class ClipSelector(ABC):
    def select_clips(self, transcript: TranscriptResult, config: PipelineConfig) -> list[ClipCandidate]
```

Implementation: `LLMClipSelector`.

### `FaceDetector` (`src/opusclip/face_detection/base.py`)

```python
class FaceDetector(ABC):
    def detect(self, frame: VideoFrame) -> list[FaceResult]
    def is_speaking(self, face: FaceResult) -> bool
```

Implementation: `MediaPipeFaceDetector`.

### `SubtitleRenderer` (`src/opusclip/subtitle/base.py`)

```python
class SubtitleRenderer(ABC):
    def render(self, words: list[WordTiming], clip_start: float, clip_end: float,
               config: PipelineConfig, output_path: Path, title: str = "") -> Path
```

Implementation: `ASSSubtitleRenderer`.

### `VideoRenderer` (`src/opusclip/rendering/base.py`)

```python
class VideoRenderer(ABC):
    def render_clip(self, context: PipelineContext, clip: ClipCandidate,
                    subtitle_path: Path) -> RenderedClip
```

Implementations: `FFmpegOptimizedRenderer`, `FFmpegLegacyRenderer`.

### `MetadataGenerator` (`src/opusclip/metadata/base.py`)

```python
class MetadataGenerator(ABC):
    def generate(self, clip: ClipCandidate, transcript_excerpt: str,
                 config: PipelineConfig) -> ClipMetadata
```

Implementation: `LLMMetadataGenerator`.

## Utilities

### `CacheManager` (`src/opusclip/cache.py`)

```python
class CacheManager:
    def __init__(self, cache_dir: Path, source: str)
    def is_step_completed(self, step: int) -> bool
    def mark_step_completed(self, step: int)
    def get_completed_step(self) -> int
    def clear(self)
```

### `PipelineMetrics` (`src/opusclip/metrics.py`)

```python
@dataclass
class PipelineMetrics:
    stages: dict[str, float]
    clip_renders: dict[int, float]
    total_duration: float
    api_calls: int
    api_retries: int
    failures: int

    def start(self)
    def finish(self)
    def measure_stage(self, name: str) -> ContextManager
    def record_clip_render(self, clip_num: int, duration: float)
    def report(self) -> str
```

### Error Hierarchy (`src/opusclip/exceptions.py`)

```
Exception
└── OpusClipError
    ├── ConfigurationError
    ├── InputValidationError
    ├── TranscriptionError
    ├── ClipSelectionError
    ├── FaceDetectionError
    ├── RenderingError
    └── MetadataError
```

### Subprocess Utilities (`src/opusclip/subprocess_utils.py`)

```python
def run_ffmpeg(args: list[str]) -> CompletedProcess
def run_ffprobe(args: list[str]) -> CompletedProcess
def run_ytdlp(args: list[str]) -> CompletedProcess
```

### FFmpeg Utilities (`src/opusclip/utils/ffmpeg_utils.py`)

```python
def run_ffmpeg(args: list[str]) -> CompletedProcess
def check_encoder_available(encoder_name: str) -> bool  # LRU-cached
def build_encoder_args(encoder_name: str, crf: int, preset: str = "fast",
                       raw_extract: bool = False) -> list[str]

class FFmpegPipe:
    """Context manager for piping frames into FFmpeg."""
    def __init__(self, args: list[str])
    # Provides .stdin and .process attributes
```

### Security (`src/opusclip/security.py`)

```python
def load_api_key() -> str
# Raises ConfigurationError if OPUSCLIP_API_KEY is not set.
```
