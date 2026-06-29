"""Pipeline configuration dataclass with environment-aware defaults."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineConfig:
    """Central configuration for the OpusClip pipeline."""

    # API & Models
    api_key: str = field(default_factory=lambda: os.getenv("OPUSCLIP_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://opencode.ai/zen/v1"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-v4-flash-free"))
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "large-v3"))
    whisper_device: str = field(default_factory=lambda: os.getenv("WHISPER_DEVICE", "cuda"))

    # Render Settings
    encoder: str = field(default_factory=lambda: os.getenv("ENCODER", "libx264"))
    renderer_backend: str = field(default_factory=lambda: os.getenv("RENDERER", "optimized"))
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "opusclip_output"))
    )

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Output Resolution
    target_width: int = 1080
    target_height: int = 1920

    # Magic Numbers / Tunables
    clip_crf: int = 20
    raw_clip_crf: int = 22  # CRF for the intermediate raw extract (ultrafast preset)
    broll_border: int = 5

    # Clip Constraints
    min_clips: int = 5
    max_clips: int = 12
    min_duration: int = 40
    max_duration: int = 120
    min_virality: int = 65

    # API Retry Policy
    api_retry_attempts: int = 3
    api_retry_delay_s: float = 2.0
    api_retry_backoff_factor: float = 2.0

    # Face Detection Tunables
    mediapipe_model_path: str = "face_landmarker.task"
    speaking_mar: float = 0.05
    min_face_area: float = 0.003
    state_debounce_s: float = 0.6

    @classmethod
    def from_env(cls, **cli_overrides: Any) -> "PipelineConfig":
        """
        Creates a PipelineConfig resolving defaults -> .env -> CLI args.
        CLI overrides take highest precedence.
        """
        config = cls()

        # Apply CLI overrides
        for key, value in cli_overrides.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)

        return config
