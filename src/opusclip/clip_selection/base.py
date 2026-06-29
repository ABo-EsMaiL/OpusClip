from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..transcription.base import TranscriptResult
from ..config import PipelineConfig


@dataclass(frozen=True, slots=True)
class ClipCandidate:
    start: float
    end: float
    score: float
    title: str
    summary: str


class ClipSelector(ABC):
    @abstractmethod
    def select_clips(
        self, transcript: TranscriptResult, config: PipelineConfig
    ) -> list[ClipCandidate]: ...
