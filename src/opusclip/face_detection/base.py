from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


class VideoFrame(Protocol):
    """Protocol for a video frame, independent of specific matrix libraries."""

    @property
    def shape(self) -> tuple[int, ...]: ...

    def tobytes(self) -> bytes: ...


@dataclass(frozen=True, slots=True)
class FaceResult:
    bbox: tuple[int, int, int, int]
    landmarks: list[tuple[int, int]]
    mouth_open_score: float


class FaceDetector(ABC):
    @abstractmethod
    def detect(self, frame: VideoFrame) -> list[FaceResult]: ...

    @abstractmethod
    def is_speaking(self, face: FaceResult) -> bool: ...
