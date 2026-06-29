from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..clip_selection.base import ClipCandidate
from ..config import PipelineConfig


@dataclass(frozen=True, slots=True)
class ClipMetadata:
    """Social media metadata generated for a single clip.

    Attributes:
        title: Engaging title for the clip.
        description: Full description with context.
        hashtags: List of relevant hashtags.
        category: Content category (Education, Entertainment, etc.).
    """
    title: str
    description: str
    hashtags: list[str]
    category: str


class MetadataGenerator(ABC):
    """Abstract interface for generating social-media metadata from clip content."""

    @abstractmethod
    def generate(
        self, clip: ClipCandidate, transcript_excerpt: str, config: PipelineConfig
    ) -> ClipMetadata: ...
