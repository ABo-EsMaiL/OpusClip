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
    """Detected face with bounding box, landmarks, and activity score.

    Attributes:
        bbox: Bounding box as (x, y, width, height) in pixel coordinates.
        landmarks: List of (x, y) facial landmark pixel coordinates.
        mouth_open_score: Normalised mouth openness (0.0-1.0) from MediaPipe jawOpen blendshape.
    """
    bbox: tuple[int, int, int, int]
    landmarks: list[tuple[int, int]]
    mouth_open_score: float


class FaceDetector(ABC):
    """Abstract interface for face detection and speaking-state classification.

    Implementations must detect faces in a video frame and determine whether
    each detected face is currently speaking (mouth open).
    """

    @abstractmethod
    def detect(self, frame: VideoFrame) -> list[FaceResult]: ...

    @abstractmethod
    def is_speaking(self, face: FaceResult) -> bool: ...
