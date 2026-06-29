from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..clip_selection.base import ClipCandidate
from ..config import PipelineConfig


@dataclass(frozen=True, slots=True)
class ClipMetadata:
    title: str
    description: str
    hashtags: list[str]
    category: str


class MetadataGenerator(ABC):
    @abstractmethod
    def generate(
        self, clip: ClipCandidate, transcript_excerpt: str, config: PipelineConfig
    ) -> ClipMetadata: ...
