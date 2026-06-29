from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from ..context import PipelineContext
from ..clip_selection.base import ClipCandidate


@dataclass
class RenderedClip:
    """Result of rendering a single clip.

    Attributes:
        path: Filesystem path to the rendered video file.
        thumbnail_path: Filesystem path to the clip thumbnail image.
        duration: Clip duration in seconds.
        resolution: (width, height) tuple in pixels.
    """
    path: Path
    thumbnail_path: Path
    duration: float
    resolution: tuple[int, int]


class VideoRenderer(ABC):
    """Abstract interface for video rendering.

    Implementations use FFmpeg to compose the final clip with subtitles,
    smart cropping, and audio.
    """

    @abstractmethod
    def render_clip(
        self, context: PipelineContext, clip: ClipCandidate, subtitle_path: Path
    ) -> RenderedClip: ...
