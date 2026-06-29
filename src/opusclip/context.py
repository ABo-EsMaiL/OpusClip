"""PipelineContext dataclass — shared state across pipeline stages."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    """Holds state and metadata as the video progresses through the pipeline."""

    # Video metadata
    video_path: Optional[Path] = None
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0.0
    duration: float = 0.0

    # Target output dimensions (vertical 9:16)
    target_width: int = 1080
    target_height: int = 1920

    # Source crop width (derived from target aspect ratio)
    src_crop_w: int = 0

    # Pipeline data
    transcript_data: Dict[str, Any] = field(default_factory=dict)
    selected_clips: List[Dict[str, Any]] = field(default_factory=list)
    render_state: Dict[str, Any] = field(default_factory=dict)

    # Output
    output_dir: Optional[Path] = None
    metadata_output_dir: Optional[Path] = None
