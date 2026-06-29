"""Unit tests for Phase 9 (CLI & Batch Processing) changes."""

from pathlib import Path
from unittest.mock import patch

from opusclip.cache import CacheManager
from opusclip.pipeline import PipelineResult, _sanitize_source_name
from opusclip.cli import build_parser, _dictify


class TestCacheManager:
    def test_fresh_cache_returns_zero(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert cache.get_completed_step() == 0
        assert not cache.is_step_completed(1)

    def test_mark_and_check(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        cache.mark_step_completed(3)
        assert cache.is_step_completed(1)
        assert cache.is_step_completed(2)
        assert cache.is_step_completed(3)
        assert not cache.is_step_completed(4)
        assert cache.get_completed_step() == 3

    def test_ignores_cache_from_different_source(self, tmp_path):
        cache_a = CacheManager(tmp_path, "video_a.mp4")
        cache_a.mark_step_completed(5)
        cache_b = CacheManager(tmp_path, "video_b.mp4")
        assert cache_b.get_completed_step() == 0
        assert not cache_b.is_step_completed(1)

    def test_clear_removes_cache(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        cache.mark_step_completed(5)
        assert (tmp_path / "pipeline_cache.json").exists()
        cache.clear()
        assert not (tmp_path / "pipeline_cache.json").exists()
        assert cache.get_completed_step() == 0

    def test_is_step_completed_after_clear(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        cache.mark_step_completed(5)
        cache.clear()
        assert not cache.is_step_completed(1)

    def test_multiple_mark_updates(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        cache.mark_step_completed(2)
        cache.mark_step_completed(7)
        assert cache.is_step_completed(7)
        assert not cache.is_step_completed(8)

    def test_malformed_cache_returns_zero(self, tmp_path):
        p = tmp_path / "pipeline_cache.json"
        p.write_text("not json", encoding="utf-8")
        cache = CacheManager(tmp_path, "video.mp4")
        assert cache.get_completed_step() == 0
        assert not cache.is_step_completed(1)


class TestSanitizeSourceName:
    def test_local_file_includes_stem_and_hash(self):
        name = _sanitize_source_name("my_video.mp4")
        assert "my_video" in name
        assert "_" in name
        suffix = name.split("_")[-1]
        assert len(suffix) == 6
        assert suffix.isalnum()

    def test_url_uses_url_prefix_and_hash(self):
        name = _sanitize_source_name("https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert name.startswith("url_")
        suffix = name.split("_")[-1]
        assert len(suffix) == 6

    def test_different_extensions_produce_different_names(self):
        n1 = _sanitize_source_name("/path/video.mp4")
        n2 = _sanitize_source_name("/path/video.mov")
        assert n1 != n2

    def test_path_with_special_chars(self):
        name = _sanitize_source_name("video 123 (test).mp4")
        assert " " not in name
        assert "(" not in name


class TestRunBatch:
    def _make_sources(self, tmp_path, names):
        sources = []
        for name in names:
            p = tmp_path / name
            p.write_bytes(b"\x00" * 100)
            sources.append(str(p))
        return sources

    def test_batch_processes_all_sources(self, mock_pipeline, tmp_path):
        sources = self._make_sources(tmp_path, ["video1.mp4", "video2.mp4", "video3.mp4"])

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            results = mock_pipeline.run_batch(sources)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, PipelineResult)
            assert r.successful_clips > 0

    def test_batch_isolated_output_dirs(self, mock_pipeline, tmp_path):
        sources = self._make_sources(tmp_path, ["a.mp4", "b.mp4"])

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            results = mock_pipeline.run_batch(sources)

        dirs = [r.output_dir for r in results]
        assert dirs[0] != dirs[1]
        assert all(d is not None for d in dirs)


class TestResume:
    def test_resume_skips_completed_steps(self, mock_pipeline, tmp_path):
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)
        src = str(video_path)

        # Create a cache marking step 5 as completed
        cache_dir = mock_pipeline.config.output_dir / _sanitize_source_name(src)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = CacheManager(cache_dir, src)
        cache.mark_step_completed(5)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            result = mock_pipeline.run(src, resume=True)

        assert isinstance(result, PipelineResult)
        assert result.successful_clips == 2

    def test_resume_produces_same_output_as_clean_run(self, mock_pipeline, tmp_path):
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)
        src = str(video_path)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            clean_result = mock_pipeline.run(src)

        # Simulate interruption after step 5, then resume
        cache_dir = mock_pipeline.config.output_dir / _sanitize_source_name(src)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = CacheManager(cache_dir, src)
        cache.mark_step_completed(5)

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            resumed_result = mock_pipeline.run(src, resume=True)

        assert clean_result.total_clips == resumed_result.total_clips
        assert clean_result.successful_clips == resumed_result.successful_clips
        assert clean_result.failed_clips == resumed_result.failed_clips


class TestBatchCLI:
    def test_parser_accepts_multiple_inputs(self):
        parser = build_parser()
        args = parser.parse_args(["a.mp4", "b.mp4", "c.mp4"])
        assert args.input == ["a.mp4", "b.mp4", "c.mp4"]

    def test_parser_single_input(self):
        parser = build_parser()
        args = parser.parse_args(["video.mp4"])
        assert args.input == ["video.mp4"]

    def test_parser_resume_flag(self):
        parser = build_parser()
        args = parser.parse_args(["video.mp4", "--fresh"])
        assert args.fresh is True

    def test_parser_resume_default(self):
        parser = build_parser()
        args = parser.parse_args(["video.mp4"])
        assert args.fresh is False


class TestDictifyBatch:
    def test_dictify_pipeline_result(self):
        from opusclip.pipeline import ClipResult
        from opusclip.metadata.base import ClipMetadata
        r = PipelineResult(
            source="test.mp4", output_dir=Path("/out"),
            duration=120.0, total_clips=2, successful_clips=2,
        )
        r.clips = [
            ClipResult(number=1, video_path=Path("/out/clip_01.mp4"),
                       thumbnail_path=Path("/out/thumb.jpg"),
                       metadata=ClipMetadata(title="T1", description="D1",
                                             hashtags=["#a"], category="C")),
            ClipResult(number=2, video_path=Path("/out/clip_02.mp4"),
                       thumbnail_path=Path("/out/thumb2.jpg"),
                       metadata=None),
        ]
        d = _dictify(r)
        assert d["source"] == "test.mp4"
        assert d["total_clips"] == 2
        assert d["clips"][0]["metadata"]["title"] == "T1"
        assert d["clips"][1]["metadata"] is None
