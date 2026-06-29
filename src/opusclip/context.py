from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    """Holds state and metadata as the video progresses through the pipeline."""

    # Video metadata
    video_path: Optional[Path] = None
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0

    # Pipeline data
    transcript_data: Dict[str, Any] = field(default_factory=dict)
    selected_clips: List[Dict[str, Any]] = field(default_factory=list)
    render_state: Dict[str, Any] = field(default_factory=dict)

    # Environment
    output_dir: Optional[Path] = None
