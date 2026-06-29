"""
Transcription provider contracts and data models.

Defines the abstract interface for all transcription backends and the
dataclasses used to represent transcription results throughout the pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WordInfo:
    """A single word with its timing and confidence from the ASR engine.

    Attributes:
        word: The recognised word text (stripped of surrounding whitespace).
        start: Word start time in seconds.
        end: Word end time in seconds.
        probability: ASR confidence score in [0, 1]. Values below the
            provider's threshold are discarded before this object is created.
    """

    word: str
    start: float
    end: float
    probability: float


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """A contiguous speech segment as produced by the ASR engine.

    Attributes:
        id: 1-based sequential identifier assigned during transcription.
        text: Full segment text as returned by the ASR engine (not cleaned).
        start: Segment start time in seconds.
        end: Segment end time in seconds.
        words: Word-level entries within this segment. May be a subset of the
            segment text when ASR confidence filtering discards low-probability
            tokens.
    """

    id: int
    text: str
    start: float
    end: float
    words: list[WordInfo]


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    """Complete transcription output for a single audio file.

    Attributes:
        segments: All accepted speech segments in chronological order.
        words: Flat, chronologically sorted list of all accepted words across
            all segments.
        language: BCP-47 language code detected or specified (e.g. ``"ar"``).
        duration: Total audio duration in seconds.
    """

    segments: list[TranscriptSegment]
    words: list[WordInfo]
    language: str
    duration: float


class TranscriptionProvider(ABC):
    """Abstract base class for all transcription backends.

    Implementations must be stateful (they hold a loaded model) and must
    release GPU/CPU resources explicitly via :meth:`cleanup`.
    """

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult:
        """Transcribe the audio file at *audio_path*.

        Args:
            audio_path: Path to the audio file (WAV recommended).
            language: BCP-47 language code. Pass an empty string for
                automatic language detection.

        Returns:
            A fully populated :class:`TranscriptResult`.
        """
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Release all resources (GPU memory, file handles, etc.) held by the model."""
        ...
