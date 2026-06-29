"""Unit tests for Phase 8 (Performance Optimization) changes."""

import time


from opusclip.metrics import PipelineMetrics
from opusclip.utils.ffmpeg_utils import build_encoder_args
from opusclip.config import PipelineConfig


class TestPipelineMetrics:
    def test_start_finish_records_duration(self):
        m = PipelineMetrics()
        m.start()
        time.sleep(0.01)
        m.finish()
        assert m.total_duration > 0.0
        assert m.total_duration < 5.0

    def test_measure_stage(self):
        m = PipelineMetrics()
        with m.measure_stage("test_stage"):
            time.sleep(0.01)
        assert "test_stage" in m.stages
        assert m.stages["test_stage"] > 0.0

    def test_record_clip_render(self):
        m = PipelineMetrics()
        m.record_clip_render(1, 5.2)
        m.record_clip_render(2, 3.1)
        assert m.clip_renders == {1: 5.2, 2: 3.1}

    def test_report_contains_stages(self):
        m = PipelineMetrics()
        m.start()
        with m.measure_stage("a"):
            pass
        m.finish()
        report = m.report()
        assert "a:" in report
        assert "Total duration:" in report

    def test_report_no_data(self):
        m = PipelineMetrics()
        report = m.report()
        assert "Total duration:" in report

    def test_failures_counter(self):
        m = PipelineMetrics()
        m.failures = 3
        report = m.report()
        assert "Failures: 3" in report

    def test_api_calls_counter(self):
        m = PipelineMetrics()
        m.api_calls = 5
        report = m.report()
        assert "API calls: 5" in report


class TestBuildEncoderArgs:
    def test_libx264_defaults(self):
        args = build_encoder_args("libx264", 20, "fast")
        assert "-c:v" in args
        assert "libx264" in args
        assert "-preset" in args
        assert "fast" in args
        assert "-crf" in args
        assert "20" in args

    def test_libx264_ultrafast_raw(self):
        args = build_encoder_args("libx264", 22, "ultrafast", raw_extract=True)
        assert "ultrafast" in args
        assert "-crf" in args
        assert "22" in args

    def test_h264_nvenc_quality(self):
        args = build_encoder_args("h264_nvenc", 20, "fast")
        assert "h264_nvenc" in args
        assert "-preset" in args
        assert "p4" in args
        assert "-cq" in args
        assert "20" in args
        assert "-rc" in args
        assert "vbr_hq" in args

    def test_h264_nvenc_raw_extract(self):
        args = build_encoder_args("h264_nvenc", 22, "ultrafast", raw_extract=True)
        assert "h264_nvenc" in args
        assert "-preset" in args
        assert "p1" in args
        assert "-cq" in args
        assert "22" in args


class TestEncoderCLI:
    def test_encoder_default_is_libx264(self):
        config = PipelineConfig()
        assert config.encoder == "libx264"

    def test_encoder_from_env_override(self):
        config = PipelineConfig(encoder="h264_nvenc")
        assert config.encoder == "h264_nvenc"

    def test_encoder_independent_of_renderer(self):
        config = PipelineConfig(encoder="h264_nvenc", renderer_backend="legacy")
        assert config.encoder == "h264_nvenc"
        assert config.renderer_backend == "legacy"


