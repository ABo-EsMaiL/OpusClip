"""Input provider contracts — abstract interface and metadata dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoMetadata:
    """Standardized metadata structure for acquired videos."""

    path: Path
    width: int
    height: int
    fps: float
    duration: float


class InputProvider(ABC):
    """Abstract base class for video input providers."""

    @abstractmethod
    def acquire(self, source: str, output_dir: Path) -> VideoMetadata:
        """
        Acquires the video from the source, saves it to output_dir,
        and returns its metadata.
        """
        pass
