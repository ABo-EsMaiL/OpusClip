from .config import PipelineConfig
from .context import PipelineContext
from .input.base import InputProvider
from .transcription.base import TranscriptionProvider
from .clip_selection.base import ClipSelector
from .face_detection.base import FaceDetector
from .subtitle.base import SubtitleRenderer
from .rendering.base import VideoRenderer
from .metadata.base import MetadataGenerator
from abc import ABC, abstractmethod


class Pipeline(ABC):
    """Orchestrates the OpusClip processing pipeline."""

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
    ) -> None:
        self.config = config
        self.input_provider = input_provider
        self.transcription_provider = transcription_provider
        self.clip_selector = clip_selector
        self.face_detector = face_detector
        self.subtitle_renderer = subtitle_renderer
        self.video_renderer = video_renderer
        self.metadata_generator = metadata_generator

    @abstractmethod
    def run(self, source: str) -> PipelineContext:
        """
        Executes the full pipeline:
        input -> transcription -> clip selection -> face detection -> rendering -> subtitle -> metadata -> output.
        """
        ...
