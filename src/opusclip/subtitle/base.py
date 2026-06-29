from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from ..config import PipelineConfig


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


class SubtitleRenderer(ABC):
    @abstractmethod
    def render(
        self, words: list[WordTiming], clip_start: float, clip_end: float, config: PipelineConfig, output_path: Path | None = None
    ) -> Path: ...
