from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..transcription.base import TranscriptResult
from ..config import PipelineConfig


@dataclass
class ClipCandidate:
    """A candidate clip identified by the selector for inclusion in the output.

    Attributes:
        clip_number: 1-based index in the final clip list.
        start: Start time in seconds within the source video.
        end: End time in seconds within the source video.
        score: Virality/quality score (0-100) from the LLM.
        title: Suggested title for the clip.
        summary: Brief textual summary of the clip content.
    """
    clip_number: int = 1
    start: float = 0.0
    end: float = 0.0
    score: float = 0.0
    title: str = ""
    summary: str = ""


class ClipSelector(ABC):
    """Abstract interface for AI-powered clip selection.

    Implementations use a transcript to identify the most engaging segments
    of a video for short-form output.
    """

    @abstractmethod
    def select_clips(
        self, transcript: TranscriptResult, config: PipelineConfig
    ) -> list[ClipCandidate]: ...
