import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineConfig:
    """Central configuration for the OpusClip pipeline."""
    
    # API & Models
    api_key: str = field(default_factory=lambda: os.getenv("OPUSCLIP_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-3.5-turbo"))
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "large-v3"))
    whisper_device: str = field(default_factory=lambda: os.getenv("WHISPER_DEVICE", "cuda"))
    
    # Render Settings
    encoder: str = field(default_factory=lambda: os.getenv("ENCODER", "libx264"))
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "opusclip_output"))
    )
    
    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    
    # Magic Numbers / Tunables
    max_llm_chars: int = 28000
    clip_crf: int = 20
    broll_border: int = 5
    
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
