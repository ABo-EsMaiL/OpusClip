from unittest.mock import patch

import pytest

from opusclip.config import PipelineConfig
from opusclip.provider_factory import ProviderFactory


class TestProviderFactoryCreatePipeline:
    """Tests that ProviderFactory.create_pipeline() wires providers correctly.

    Uses mocking at the import level to avoid loading real models/GPUs.
    """

    def test_create_pipeline_returns_pipeline_with_mocks(self):
        with (
            patch("opusclip.provider_factory.WhisperProvider"),
            patch("opusclip.provider_factory.MediaPipeFaceDetector"),
            patch("opusclip.provider_factory.LLMClipSelector"),
            patch("opusclip.provider_factory.LLMMetadataGenerator"),
            patch("opusclip.provider_factory.FFmpegOptimizedRenderer"),
            patch("opusclip.provider_factory.load_api_key", return_value="test-key"),
        ):
            config = PipelineConfig(api_key="test-key")
            factory = ProviderFactory(config)
            pipeline = factory.create_pipeline("video.mp4")

        from opusclip.pipeline import Pipeline
        assert isinstance(pipeline, Pipeline)
        assert pipeline.config is config

    def test_input_provider_local_for_file(self):
        factory = ProviderFactory(PipelineConfig())
        provider = factory.create_input_provider("/path/to/video.mp4")
        assert provider.__class__.__name__ == "LocalFileProvider"

    def test_input_provider_youtube_for_url(self):
        factory = ProviderFactory(PipelineConfig())
        provider = factory.create_input_provider("https://youtube.com/watch?v=test")
        assert provider.__class__.__name__ == "YouTubeProvider"

    def test_create_pipeline_youtube_source(self):
        with (
            patch("opusclip.provider_factory.WhisperProvider"),
            patch("opusclip.provider_factory.MediaPipeFaceDetector"),
            patch("opusclip.provider_factory.LLMClipSelector"),
            patch("opusclip.provider_factory.LLMMetadataGenerator"),
            patch("opusclip.provider_factory.FFmpegOptimizedRenderer"),
            patch("opusclip.provider_factory.load_api_key", return_value="test-key"),
        ):
            config = PipelineConfig(api_key="test-key")
            factory = ProviderFactory(config)
            pipeline = factory.create_pipeline("https://youtube.com/watch?v=test123")

        from opusclip.pipeline import Pipeline
        assert isinstance(pipeline, Pipeline)

    def test_create_pipeline_legacy_renderer(self):
        with (
            patch("opusclip.provider_factory.WhisperProvider"),
            patch("opusclip.provider_factory.MediaPipeFaceDetector"),
            patch("opusclip.provider_factory.LLMClipSelector"),
            patch("opusclip.provider_factory.LLMMetadataGenerator"),
            patch("opusclip.provider_factory.FFmpegLegacyRenderer"),
            patch("opusclip.provider_factory.load_api_key", return_value="test-key"),
        ):
            config = PipelineConfig(api_key="test-key", renderer_backend="legacy")
            factory = ProviderFactory(config)
            pipeline = factory.create_pipeline("video.mp4")

        assert pipeline is not None


class TestProviderFactoryFailure:
    def test_missing_api_key_for_factory(self):
        with (
            patch("opusclip.provider_factory.WhisperProvider"),
            patch("opusclip.provider_factory.MediaPipeFaceDetector"),
            patch("opusclip.provider_factory.LLMClipSelector"),
            patch("opusclip.provider_factory.LLMMetadataGenerator"),
            patch("opusclip.provider_factory.FFmpegOptimizedRenderer"),
            patch("opusclip.provider_factory.load_api_key", side_effect=ValueError("API key not set")),
        ):
            config = PipelineConfig(api_key="")
            factory = ProviderFactory(config)
            with pytest.raises(ValueError, match="API key not set"):
                factory.create_pipeline("video.mp4")