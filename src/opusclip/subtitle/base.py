from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from ..config import PipelineConfig


@dataclass
class WordTiming:
    """A single word with its start and end timing within the video.

    Attributes:
        word: The word text.
        start: Start time in seconds.
        end: End time in seconds.
    """
    word: str
    start: float
    end: float


class SubtitleRenderer(ABC):
    """Abstract interface for rendering subtitle files from word-level timing."""

    @abstractmethod
    def render(
        self, words: list[WordTiming], clip_start: float, clip_end: float, config: PipelineConfig, output_path: Path | None = None
    ) -> Path: ...
