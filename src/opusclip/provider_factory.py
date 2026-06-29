"""Provider factory — wires all pipeline dependencies via dependency injection."""

import urllib.parse

from .config import PipelineConfig
from .pipeline import Pipeline
from .input.base import InputProvider
from .input.local import LocalFileProvider
from .input.youtube import YouTubeProvider
from .transcription.base import TranscriptionProvider
from .transcription.whisper_provider import WhisperProvider
from .clip_selection.base import ClipSelector
from .clip_selection.llm_selector import LLMClipSelector
from .face_detection.base import FaceDetector
from .face_detection.mediapipe_detector import MediaPipeFaceDetector
from .subtitle.base import SubtitleRenderer
from .subtitle.ass_builder import ASSSubtitleRenderer
from .rendering.base import VideoRenderer
from .rendering.ffmpeg_optimized_renderer import FFmpegOptimizedRenderer
from .rendering.ffmpeg_legacy_renderer import FFmpegLegacyRenderer
from .metadata.base import MetadataGenerator
from .metadata.llm_metadata import LLMMetadataGenerator
from .fonts import FontManager
from .security import load_api_key


class ProviderFactory:
    """Creates and wires together all pipeline providers via dependency injection."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def create_input_provider(self, source: str) -> InputProvider:
        """Resolve the input provider based on the source string.

        Returns a :class:`YouTubeProvider` for YouTube URLs and a
        :class:`LocalFileProvider` for everything else.
        """
        parsed = urllib.parse.urlparse(source)
        netloc = parsed.netloc.lower()
        if parsed.scheme in ("http", "https") and ("youtube.com" in netloc or "youtu.be" in netloc):
            return YouTubeProvider()
        return LocalFileProvider()

    def create_transcription_provider(self) -> TranscriptionProvider:
        """Create a WhisperProvider configured from PipelineConfig."""
        return WhisperProvider(
            model_size=self.config.whisper_model,
            device=self.config.whisper_device,
        )

    def create_clip_selector(self) -> ClipSelector:
        """Create an LLM-based clip selector using the configured API credentials."""
        api_key = load_api_key()
        return LLMClipSelector(
            api_key=api_key,
            base_url=self.config.llm_base_url,
            model=self.config.llm_model,
        )

    def create_face_detector(self) -> FaceDetector:
        """Create a MediaPipe face detector with the configured model path."""
        return MediaPipeFaceDetector(
            model_asset_path=self.config.mediapipe_model_path,
        )

    def create_subtitle_renderer(self) -> SubtitleRenderer:
        """Create an ASS subtitle renderer using the bundled fonts."""
        font_manager = FontManager()
        return ASSSubtitleRenderer(font_manager=font_manager)

    def create_video_renderer(self, face_detector: FaceDetector) -> VideoRenderer:
        """Create a video renderer (optimized or legacy) based on PipelineConfig."""
        if self.config.renderer_backend == "legacy":
            return FFmpegLegacyRenderer(face_detector=face_detector, config=self.config)
        return FFmpegOptimizedRenderer(face_detector=face_detector, config=self.config)

    def create_metadata_generator(self) -> MetadataGenerator:
        """Create an LLM-based metadata generator using the configured API credentials."""
        api_key = load_api_key()
        return LLMMetadataGenerator(
            api_key=api_key,
            base_url=self.config.llm_base_url,
            model=self.config.llm_model,
            language="ar",
        )

    def create_pipeline(self, source: str) -> Pipeline:
        """Wire all providers and return a fully configured Pipeline.

        Args:
            source: Video source path or URL (used to select the input provider).

        Returns:
            A :class:`Pipeline` ready to call ``.run()``.
        """
        input_provider = self.create_input_provider(source)
        transcription_provider = self.create_transcription_provider()
        clip_selector = self.create_clip_selector()
        face_detector = self.create_face_detector()
        subtitle_renderer = self.create_subtitle_renderer()
        video_renderer = self.create_video_renderer(face_detector)
        metadata_generator = self.create_metadata_generator()

        return Pipeline(
            config=self.config,
            input_provider=input_provider,
            transcription_provider=transcription_provider,
            clip_selector=clip_selector,
            face_detector=face_detector,
            subtitle_renderer=subtitle_renderer,
            video_renderer=video_renderer,
            metadata_generator=metadata_generator,
        )
