"""Integration tests for the full pipeline orchestration."""

import json
from pathlib import Path
from unittest.mock import patch


from opusclip.config import PipelineConfig
from opusclip.pipeline import Pipeline, PipelineResult
from opusclip.cli import build_parser
from opusclip.provider_factory import ProviderFactory


class TestPipelineEndToEnd:
    """Verifies the pipeline runs through all 10 steps with mock providers."""

    def _create_video_stub(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write a minimal valid mp4 header so ffprobe doesn't crash
        # (ffprobe is not called by mock providers, but the file must exist
        #  for input_validator.validate_video_path).
        path.write_bytes(b"\x00\x00\x00\x00\x00\x00\x00\x00")

    def test_full_pipeline_execution(self, mock_pipeline, tmp_path):
        video_path = tmp_path / "input.mp4"
        self._create_video_stub(video_path)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            result = mock_pipeline.run(str(video_path))

        assert isinstance(result, PipelineResult)
        assert result.output_dir == tmp_path
        assert result.total_clips == 2
        assert result.successful_clips == 2
        assert result.failed_clips == 0
        assert result.duration == 120.0

        clips_dir = tmp_path / "clips"
        assert clips_dir.exists()
        clip_files = list(clips_dir.glob("*_FINAL.mp4"))
        assert len(clip_files) == 2

        summary_path = tmp_path / "pipeline_summary.json"
        assert summary_path.exists()
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        assert data["total_clips"] == 2
        assert data["successful_clips"] == 2
        assert data["failed_clips"] == 0

        meta_dir = tmp_path / "metadata"
        assert meta_dir.exists()
        meta_files = list(meta_dir.glob("*_metadata.json"))
        assert len(meta_files) == 2

    def test_pipeline_handles_no_transcript_words(self, sample_config, tmp_path):
        from tests.conftest import (
            MockInputProvider, MockTranscriptionProvider, MockClipSelector,
            MockFaceDetector, MockSubtitleRenderer, MockVideoRenderer,
            MockMetadataGenerator,
        )
        from opusclip.transcription.base import TranscriptResult

        sample_config.output_dir = tmp_path
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)

        pipeline = Pipeline(
            config=sample_config,
            input_provider=MockInputProvider(),
            transcription_provider=MockTranscriptionProvider(
                TranscriptResult(segments=[], words=[], language="en", duration=0.0)
            ),
            clip_selector=MockClipSelector([]),
            face_detector=MockFaceDetector(),
            subtitle_renderer=MockSubtitleRenderer(),
            video_renderer=MockVideoRenderer(),
            metadata_generator=MockMetadataGenerator(),
        )
        pipeline._skip_health_checks = True
        with patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value.returncode = 0
            result = pipeline.run(str(video_path))
        assert result.total_clips == 0


class TestCli:
    """Tests CLI argument parsing and config mapping."""

    def test_build_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["input.mp4"])
        assert args.input == ["input.mp4"]
        assert args.output is None
        assert args.min_clips is None
        assert args.max_clips is None
        assert args.renderer is None
        assert args.encoder is None
        assert args.fresh is False
        assert args.log_level is None

    def test_build_parser_all_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "input.mp4", "--output", "out/", "--min-clips", "6",
            "--max-clips", "10", "--renderer", "legacy",
            "--encoder", "h264_nvenc", "--fresh", "--log-level", "DEBUG",
        ])
        assert args.input == ["input.mp4"]
        assert args.output == "out/"
        assert args.min_clips == 6
        assert args.max_clips == 10
        assert args.renderer == "legacy"
        assert args.encoder == "h264_nvenc"
        assert args.fresh is True
        assert args.log_level == "DEBUG"

    def test_renderer_maps_to_renderer_backend(self):
        config = PipelineConfig.from_env(renderer_backend="optimized")
        assert config.renderer_backend == "optimized"

        config2 = PipelineConfig.from_env(renderer_backend="legacy")
        assert config2.renderer_backend == "legacy"

        config3 = PipelineConfig.from_env()
        assert config3.renderer_backend == "optimized"

    def test_cli_override_mapping(self):
        """Verify CLI --renderer maps to renderer_backend, not encoder."""
        overrides = {"renderer_backend": "legacy"}
        config = PipelineConfig.from_env(**overrides)
        assert config.renderer_backend == "legacy"
        assert config.encoder == "libx264"  # unchanged

        overrides2 = {"renderer_backend": "optimized"}
        config2 = PipelineConfig.from_env(**overrides2)
        assert config2.renderer_backend == "optimized"
        assert config2.encoder == "libx264"

    def test_encoder_cli_mapping(self):
        """Verify CLI --encoder maps to encoder config."""
        overrides = {"encoder": "h264_nvenc"}
        config = PipelineConfig.from_env(**overrides)
        assert config.encoder == "h264_nvenc"
        assert config.renderer_backend == "optimized"  # unchanged


class TestProviderFactory:
    """Tests the ProviderFactory creates correct implementations."""

    def test_creates_local_provider_for_file(self):
        factory = ProviderFactory(PipelineConfig())
        provider = factory.create_input_provider("video.mp4")
        assert provider.__class__.__name__ == "LocalFileProvider"

    def test_creates_youtube_provider_for_url(self):
        factory = ProviderFactory(PipelineConfig())
        provider = factory.create_input_provider("https://youtube.com/watch?v=test")
        assert provider.__class__.__name__ == "YouTubeProvider"

    def test_creates_youtube_provider_for_short_url(self):
        factory = ProviderFactory(PipelineConfig())
        provider = factory.create_input_provider("https://youtu.be/test123")
        assert provider.__class__.__name__ == "YouTubeProvider"

    def test_creates_optimized_renderer_by_default(self):
        from opusclip.face_detection.base import FaceDetector

        class _StubDetector(FaceDetector):
            def detect(self, frame): return []
            def is_speaking(self, face): return False

        factory = ProviderFactory(PipelineConfig())
        renderer = factory.create_video_renderer(_StubDetector())
        assert renderer.__class__.__name__ == "FFmpegOptimizedRenderer"

    def test_creates_legacy_renderer_when_configured(self):
        from opusclip.face_detection.base import FaceDetector

        class _StubDetector(FaceDetector):
            def detect(self, frame): return []
            def is_speaking(self, face): return False

        config = PipelineConfig(renderer_backend="legacy")
        factory = ProviderFactory(config)
        renderer = factory.create_video_renderer(_StubDetector())
        assert renderer.__class__.__name__ == "FFmpegLegacyRenderer"


class TestPipelineContext:
    """Tests the PipelineContext data model."""

    def test_default_dimensions(self):
        from opusclip.context import PipelineContext
        ctx = PipelineContext()
        assert ctx.target_width == 1080
        assert ctx.target_height == 1920
        assert ctx.video_width == 0
        assert ctx.video_height == 0
        assert ctx.video_fps == 0.0

    def test_no_duplicate_fields(self):
        from opusclip.context import PipelineContext
        ctx = PipelineContext()
        assert not hasattr(ctx, "width")
        assert not hasattr(ctx, "height")
        assert not hasattr(ctx, "fps")
        assert hasattr(ctx, "video_width")
        assert hasattr(ctx, "video_height")
        assert hasattr(ctx, "video_fps")


class TestPipelineMetrics:
    """Tests pipeline metrics collection during execution."""

    def test_pipeline_collects_metrics(self, mock_pipeline, tmp_path):
        from opusclip.metrics import PipelineMetrics
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            mock_pipeline.run(str(video_path))

        assert isinstance(mock_pipeline.metrics, PipelineMetrics)
        assert mock_pipeline.metrics.total_duration > 0
        assert mock_pipeline.metrics.stages != {}
        stage_names = list(mock_pipeline.metrics.stages.keys())
        assert "render_videos" in stage_names
        assert "validate_input" in stage_names
        assert len(mock_pipeline.metrics.clip_renders) > 0

    def test_metrics_report_output(self, mock_pipeline, tmp_path):
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            _ = mock_pipeline.run(str(video_path))

        report = mock_pipeline.metrics.report()
        assert "Total duration:" in report
        assert "Clip renders" in report
        assert "Stage timing" in report
