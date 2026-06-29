"""Shared fixtures for OpusClip tests."""

from pathlib import Path
from typing import List, Optional

import pytest

from opusclip.config import PipelineConfig
from opusclip.context import PipelineContext
from opusclip.pipeline import Pipeline
from opusclip.input.base import InputProvider, VideoMetadata
from opusclip.transcription.base import TranscriptionProvider, TranscriptResult, TranscriptSegment, WordInfo
from opusclip.clip_selection.base import ClipSelector, ClipCandidate
from opusclip.face_detection.base import FaceDetector, FaceResult
from opusclip.subtitle.base import SubtitleRenderer, WordTiming
from opusclip.rendering.base import VideoRenderer, RenderedClip
from opusclip.metadata.base import MetadataGenerator, ClipMetadata


@pytest.fixture
def sample_config() -> PipelineConfig:
    return PipelineConfig(
        api_key="test-key",
        llm_base_url="https://api.test.com",
        llm_model="test-model",
        output_dir=Path("/tmp/opusclip_test"),
        min_clips=1,
        max_clips=3,
    )


@pytest.fixture
def sample_context() -> PipelineContext:
    return PipelineContext(
        video_path=Path("/tmp/test.mp4"),
        video_width=1920,
        video_height=1080,
        video_fps=30.0,
        duration=120.0,
        target_width=1080,
        target_height=1920,
        src_crop_w=1080,
    )


@pytest.fixture
def sample_transcript() -> TranscriptResult:
    return TranscriptResult(
        segments=[
            TranscriptSegment(id=1, text="Hello world", start=0.0, end=2.0, words=[]),
            TranscriptSegment(id=2, text="This is a test", start=2.5, end=5.0, words=[]),
        ],
        words=[
            WordInfo(word="Hello", start=0.0, end=0.5, probability=0.9),
            WordInfo(word="world", start=0.6, end=1.0, probability=0.85),
        ],
        language="en",
        duration=5.0,
    )


@pytest.fixture
def sample_clips() -> List[ClipCandidate]:
    return [
        ClipCandidate(clip_number=1, start=0.0, end=5.0, score=85.0, title="Clip 1", summary="First clip"),
        ClipCandidate(clip_number=2, start=10.0, end=15.0, score=90.0, title="Clip 2", summary="Second clip"),
    ]


class MockInputProvider(InputProvider):
    def __init__(self, meta: Optional[VideoMetadata] = None) -> None:
        self.meta = meta

    def acquire(self, source: str, output_dir: Path) -> VideoMetadata:
        src_path = Path(source).resolve() if Path(source).exists() else self.meta.path if self.meta else Path(source)
        if self.meta is not None:
            return VideoMetadata(
                path=src_path,
                width=self.meta.width,
                height=self.meta.height,
                fps=self.meta.fps,
                duration=self.meta.duration,
            )
        return VideoMetadata(path=src_path, width=1920, height=1080, fps=30.0, duration=120.0)


class MockTranscriptionProvider(TranscriptionProvider):
    def __init__(self, result: Optional[TranscriptResult] = None) -> None:
        self.result = result or TranscriptResult(segments=[], words=[], language="en", duration=0.0)

    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult:
        return self.result

    def cleanup(self) -> None:
        pass


class MockClipSelector(ClipSelector):
    def __init__(self, clips: Optional[List[ClipCandidate]] = None) -> None:
        self.clips = clips or []

    def select_clips(self, transcript: TranscriptResult, config: PipelineConfig) -> List[ClipCandidate]:
        return self.clips


class MockFaceDetector(FaceDetector):
    def detect(self, frame) -> List[FaceResult]:
        return []

    def is_speaking(self, face: FaceResult) -> bool:
        return False


class MockSubtitleRenderer(SubtitleRenderer):
    def render(self, words: List[WordTiming], clip_start: float, clip_end: float, config: PipelineConfig, output_path: Optional[Path] = None) -> Path:
        p = output_path or Path("/tmp/test.ass")
        p.write_text("[Script Info]\n", encoding="utf-8")
        return p


class MockVideoRenderer(VideoRenderer):
    def __init__(self) -> None:
        self.last_context = None
        self.last_clip = None
        self.last_subtitle_path = None

    def render_clip(self, context: PipelineContext, clip: ClipCandidate, subtitle_path: Path) -> RenderedClip:
        self.last_context = context
        self.last_clip = clip
        self.last_subtitle_path = subtitle_path
        clips_dir = context.output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        video = clips_dir / f"clip_{clip.clip_number:02d}_FINAL.mp4"
        thumb = clips_dir / f"clip_{clip.clip_number:02d}_thumb.jpg"
        video.touch()
        return RenderedClip(path=video, thumbnail_path=thumb, duration=5.0, resolution=(1080, 1920))


class MockMetadataGenerator(MetadataGenerator):
    def generate(self, clip: ClipCandidate, transcript_excerpt: str, config: PipelineConfig) -> ClipMetadata:
        return ClipMetadata(
            title=clip.title,
            description=f"Description for {clip.title}",
            hashtags=["#test", "#opusclip"],
            category="Education",
        )


@pytest.fixture
def mock_pipeline(sample_config, sample_transcript, sample_clips, tmp_path) -> Pipeline:
    sample_config.output_dir = tmp_path
    input_provider = MockInputProvider()
    transcription_provider = MockTranscriptionProvider(sample_transcript)
    clip_selector = MockClipSelector(sample_clips)
    face_detector = MockFaceDetector()
    subtitle_renderer = MockSubtitleRenderer()
    video_renderer = MockVideoRenderer()
    metadata_generator = MockMetadataGenerator()

    return Pipeline(
        config=sample_config,
        input_provider=input_provider,
        transcription_provider=transcription_provider,
        clip_selector=clip_selector,
        face_detector=face_detector,
        subtitle_renderer=subtitle_renderer,
        video_renderer=video_renderer,
        metadata_generator=metadata_generator,
    )


@pytest.fixture
def sample_word_timings() -> list[WordTiming]:
    return [
        WordTiming(word="Hello", start=0.0, end=0.5),
        WordTiming(word="world", start=0.6, end=1.0),
        WordTiming(word="مرحبا", start=2.0, end=2.5),
        WordTiming(word="بالعالم", start=2.6, end=3.0),
    ]


@pytest.fixture
def sample_face_results() -> list[FaceResult]:
    return [
        FaceResult(bbox=(100, 50, 200, 300), landmarks=[(200, 200)], mouth_open_score=0.0),
        FaceResult(bbox=(400, 100, 180, 280), landmarks=[(490, 240)], mouth_open_score=0.0),
        FaceResult(bbox=(800, 60, 190, 290), landmarks=[(895, 205)], mouth_open_score=0.8),
    ]


@pytest.fixture
def sample_clip_metadata() -> ClipMetadata:
    return ClipMetadata(
        title="Test Clip",
        description="A test clip description",
        hashtags=["#test", "#opusclip"],
        category="Education",
    )
