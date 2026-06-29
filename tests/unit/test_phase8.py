"""Unit tests for Phase 8 (Performance Optimization) changes."""

import time
import warnings


from opusclip.metrics import PipelineMetrics
from opusclip.utils.ffmpeg_utils import build_encoder_args
from opusclip.config import PipelineConfig
from opusclip.clip_selection.llm_selector import LLMClipSelector
from opusclip.transcription.base import TranscriptSegment


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


class TestMaxCharsTruncationWarning:
    def test_no_warning_when_within_limit(self):
        segments = [
            TranscriptSegment(id=i, text="hello world", start=i * 5.0, end=i * 5.0 + 4.0, words=[])
            for i in range(3)
        ]
        selector = LLMClipSelector(api_key="test", base_url="https://test.com", model="test")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = selector._compress_transcript(segments, 100000)
        assert len(w) == 0

    def test_warning_when_truncated_below_50_pct(self):
        segments = [
            TranscriptSegment(id=i, text="A" * 100, start=i * 5.0, end=i * 5.0 + 4.0, words=[])
            for i in range(100)
        ]
        selector = LLMClipSelector(api_key="test", base_url="https://test.com", model="test")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            selector._compress_transcript(segments, 500)
        assert len(w) >= 1
        assert "max_llm_chars" in str(w[0].message)
        assert "coverage" in str(w[0].message)

    def test_no_warning_above_50_pct(self):
        segments = [
            TranscriptSegment(id=i, text="short", start=i * 5.0, end=i * 5.0 + 4.0, words=[])
            for i in range(10)
        ]
        selector = LLMClipSelector(api_key="test", base_url="https://test.com", model="test")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            selector._compress_transcript(segments, 500)
        truncation_warnings = [x for x in w if "max_llm_chars" in str(x.message)]
        assert len(truncation_warnings) == 0
