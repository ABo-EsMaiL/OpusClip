from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..transcription.base import TranscriptResult
from ..config import PipelineConfig


@dataclass
class ClipCandidate:
    clip_number: int = 1
    start: float = 0.0
    end: float = 0.0
    score: float = 0.0
    title: str = ""
    summary: str = ""


class ClipSelector(ABC):
    @abstractmethod
    def select_clips(
        self, transcript: TranscriptResult, config: PipelineConfig
    ) -> list[ClipCandidate]: ...
