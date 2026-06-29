from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from ..context import PipelineContext
from ..clip_selection.base import ClipCandidate


@dataclass
class RenderedClip:
    path: Path
    thumbnail_path: Path
    duration: float
    resolution: tuple[int, int]


class VideoRenderer(ABC):
    @abstractmethod
    def render_clip(
        self, context: PipelineContext, clip: ClipCandidate, subtitle_path: Path
    ) -> RenderedClip: ...
