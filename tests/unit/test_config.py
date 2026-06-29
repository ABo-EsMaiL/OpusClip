from pathlib import Path

from opusclip.config import PipelineConfig


class TestPipelineConfigDefaults:
    def test_defaults_are_set(self):
        config = PipelineConfig()
        assert config.encoder == "libx264"
        assert config.renderer_backend == "optimized"
        assert config.min_clips == 5
        assert config.max_clips == 12
        assert config.clip_crf == 20
        assert config.api_retry_attempts == 5
        assert config.log_level == "INFO"

    def test_output_dir_defaults_to_opusclip_output(self):
        config = PipelineConfig()
        assert config.output_dir == Path("opusclip_output")

    def test_whisper_defaults(self):
        config = PipelineConfig()
        assert config.whisper_model == "large-v3"
        assert config.whisper_device == "cuda"

    def test_llm_defaults(self):
        config = PipelineConfig()
        assert config.llm_model == "deepseek-v4-flash-free"
        assert config.llm_base_url == "https://opencode.ai/zen/v1"


class TestPipelineConfigFromEnv:
    def test_from_env_empty_uses_defaults(self):
        config = PipelineConfig.from_env()
        assert config.min_clips == 5

    def test_from_env_overrides_clip_bounds(self):
        config = PipelineConfig.from_env(min_clips=1, max_clips=3)
        assert config.min_clips == 1
        assert config.max_clips == 3

    def test_from_env_overrides_renderer(self):
        config = PipelineConfig.from_env(renderer_backend="legacy")
        assert config.renderer_backend == "legacy"

    def test_from_env_overrides_encoder(self):
        config = PipelineConfig.from_env(encoder="h264_nvenc")
        assert config.encoder == "h264_nvenc"

    def test_from_env_overrides_output_dir(self):
        config = PipelineConfig.from_env(output_dir=Path("/tmp/out"))
        assert config.output_dir == Path("/tmp/out")

    def test_from_env_overrides_log_level(self):
        config = PipelineConfig.from_env(log_level="DEBUG")
        assert config.log_level == "DEBUG"

    def test_from_env_ignores_none_values(self):
        config = PipelineConfig.from_env(min_clips=None, max_clips=10)
        assert config.min_clips == 5
        assert config.max_clips == 10

    def test_from_env_ignores_unknown_attrs(self):
        config = PipelineConfig.from_env(nonexistent="value")
        assert not hasattr(config, "nonexistent")


class TestPipelineConfigInvalidValues:

    def test_negative_clip_bounds(self):
        config = PipelineConfig.from_env(min_clips=-1)
        assert config.min_clips == -1

    def test_negative_crf(self):
        config = PipelineConfig.from_env(clip_crf=-1)
        assert config.clip_crf == -1

    def test_zero_duration(self):
        config = PipelineConfig.from_env(min_duration=0)
        assert config.min_duration == 0