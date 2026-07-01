"""Unit tests for Phase 9 (CLI & Batch Processing) changes."""

from pathlib import Path
from unittest.mock import patch

from opusclip.cache import CacheManager
from opusclip.pipeline import PipelineResult, _sanitize_source_name
from opusclip.cli import build_parser, _dictify


class TestCacheManager:
    def _make_artifact(self, base: Path, path: str, content: object = None) -> None:
        p = base / path
        p.parent.mkdir(parents=True, exist_ok=True)
        if content is not None:
            import json
            p.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        else:
            p.write_text("{}", encoding="utf-8")

    def test_fresh_cache_returns_zero(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert cache.get_completed_step() == 0

    def _valid_transcript(self) -> dict:
        return {
            "segments": [[1, "hello world", 0.0, 2.0]],
            "words": [["hello", 0.0, 0.5, 0.95], ["world", 0.6, 1.0, 0.85]],
            "language": "en",
            "duration": 120.0,
        }

    def _valid_clips(self) -> list:
        return [
            {"number": 1, "start": 0.0, "end": 5.0, "score": 85.0, "title": "Clip 1", "summary": "First clip"},
        ]

    def _valid_ass(self, p: Path) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\nDialogue: 0,0:00:01,0:00:02,Default,,0,0,0,,Hello\n", encoding="utf-8")

    def _valid_metadata(self, p: Path) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"title": "T", "description": "D", "hashtags": ["#t"], "category": "C"}', encoding="utf-8")

    def test_transcript_only_returns_step_3(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        assert cache.get_completed_step() == 3

    def test_transcript_and_clips_returns_step_5(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", self._valid_clips())
        assert cache.get_completed_step() == 5

    def test_empty_transcript_returns_zero(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", {"segments": []})
        assert cache.get_completed_step() == 0

    def test_empty_clips_returns_3_not_5(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", [])
        assert cache.get_completed_step() == 3

    def test_subtitles_advances_to_step_6(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", self._valid_clips())
        self._valid_ass(tmp_path / "subtitles" / "clip_01.ass")
        assert cache.get_completed_step() == 6

    def test_rendered_clips_advances_to_step_7(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", self._valid_clips())
        self._valid_ass(tmp_path / "subtitles" / "clip_01.ass")
        (tmp_path / "clips" / "clip_01_FINAL.mp4").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "clips" / "clip_01_FINAL.mp4").write_bytes(b"\x00" * 100)
        assert cache.get_completed_step() == 7

    def test_all_artifacts_returns_10(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", self._valid_clips())
        self._valid_ass(tmp_path / "subtitles" / "clip_01.ass")
        (tmp_path / "clips" / "clip_01_FINAL.mp4").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "clips" / "clip_01_FINAL.mp4").write_bytes(b"\x00" * 100)
        self._valid_metadata(tmp_path / "metadata" / "clip_01_metadata.json")
        self._make_artifact(tmp_path, "pipeline_summary.json", {"total_clips": 1})
        assert cache.get_completed_step() == 10

    def test_clear_removes_all_artifacts(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", self._valid_transcript())
        self._make_artifact(tmp_path, "selected_clips.json", self._valid_clips())
        assert cache.get_completed_step() == 5
        cache.clear()
        assert cache.get_completed_step() == 0

    def test_list_missing_clips(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "selected_clips.json", [
            {"number": 1, "start": 0.0, "end": 5.0, "score": 85.0, "title": "C1", "summary": "S1"},
            {"number": 2, "start": 5.0, "end": 10.0, "score": 90.0, "title": "C2", "summary": "S2"},
        ])
        (tmp_path / "clips" / "clip_01_FINAL.mp4").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "clips" / "clip_01_FINAL.mp4").write_bytes(b"\x00" * 100)
        missing = cache.list_missing_clips()
        assert missing == [2]

    # ── Strong validation tests ────────────────────────────────────────

    def test_transcript_invalid_no_duration(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", {
            "segments": [[1, "test", 0.0, 2.0]], "words": [], "language": "en",
        })
        assert not cache.transcript_is_valid()

    def test_transcript_invalid_no_language(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", {
            "segments": [[1, "test", 0.0, 2.0]], "words": [], "duration": 120.0,
        })
        assert not cache.transcript_is_valid()

    def test_transcript_invalid_segment_missing_field(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "transcript.json", {
            "segments": [{"id": 1}], "words": [], "language": "en", "duration": 120.0,
        })
        assert not cache.transcript_is_valid()

    def test_repaired_transcript_valid(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "repaired_transcript.json", {
            "repaired_words": [["hello", 0.0, 0.5, 0.9], ["world", 0.6, 1.0, 0.8]],
        })
        assert cache.repaired_transcript_is_valid()

    def test_repaired_transcript_empty(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "repaired_transcript.json", {"repaired_words": []})
        assert not cache.repaired_transcript_is_valid()

    def test_repaired_transcript_bad_timing(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "repaired_transcript.json", {
            "repaired_words": [["hello", 0.5, 0.3, 0.9]],
        })
        assert not cache.repaired_transcript_is_valid()

    def test_clips_invalid_no_score(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "selected_clips.json", [
            {"number": 1, "start": 0.0, "end": 5.0},
        ])
        assert not cache.selected_clips_are_valid()

    def test_clips_invalid_start_ge_end(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "selected_clips.json", [
            {"number": 1, "start": 5.0, "end": 5.0, "score": 85.0, "title": "T", "summary": "S"},
        ])
        assert not cache.selected_clips_are_valid()

    def test_clips_invalid_no_title(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._make_artifact(tmp_path, "selected_clips.json", [
            {"number": 1, "start": 0.0, "end": 5.0, "score": 85.0, "summary": "S"},
        ])
        assert not cache.selected_clips_are_valid()

    def test_subtitle_for_clip_valid(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._valid_ass(tmp_path / "subtitles" / "clip_01.ass")
        assert cache.subtitle_for_clip_is_valid(1)

    def test_subtitle_for_clip_missing(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.subtitle_for_clip_is_valid(1)

    def test_subtitle_for_clip_empty(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        p = tmp_path / "subtitles" / "clip_01.ass"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
        assert not cache.subtitle_for_clip_is_valid(1)

    def test_subtitle_for_clip_no_events(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        p = tmp_path / "subtitles" / "clip_01.ass"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[Script Info]\n", encoding="utf-8")
        assert not cache.subtitle_for_clip_is_valid(1)

    def test_metadata_for_clip_valid(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._valid_metadata(tmp_path / "metadata" / "clip_01_metadata.json")
        assert cache.metadata_for_clip_is_valid(1)

    def test_metadata_for_clip_missing_title(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        p = tmp_path / "metadata" / "clip_01_metadata.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"description": "D", "hashtags": ["#t"], "category": "C"}', encoding="utf-8")
        assert not cache.metadata_for_clip_is_valid(1)

    def test_metadata_for_clip_missing(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.metadata_for_clip_is_valid(1)

    def test_thumbnail_for_clip_valid(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        p = tmp_path / "clips" / "clip_01_thumb.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00" * 100)
        assert cache.thumbnail_for_clip_is_valid(1)

    def test_thumbnail_for_clip_missing(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.thumbnail_for_clip_is_valid(1)

    def test_list_missing_subtitles(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._valid_ass(tmp_path / "subtitles" / "clip_01.ass")
        missing = cache.list_missing_subtitles([1, 2, 3])
        assert missing == [2, 3]

    def test_list_missing_videos(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        (tmp_path / "clips" / "clip_01_FINAL.mp4").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "clips" / "clip_01_FINAL.mp4").write_bytes(b"\x00" * 100)
        missing = cache.list_missing_videos([1, 2])
        assert missing == [2]

    def test_list_missing_metadata(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        self._valid_metadata(tmp_path / "metadata" / "clip_01_metadata.json")
        missing = cache.list_missing_metadata([1, 2])
        assert missing == [2]

    def test_list_missing_thumbnails(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        p = tmp_path / "clips" / "clip_01_thumb.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00" * 100)
        missing = cache.list_missing_thumbnails([1, 2])
        assert missing == [2]

    def test_transcript_exists(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.transcript_exists()
        self._make_artifact(tmp_path, "transcript.json", {})
        assert cache.transcript_exists()

    def test_repaired_transcript_exists(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.repaired_transcript_exists()
        self._make_artifact(tmp_path, "repaired_transcript.json", {})
        assert cache.repaired_transcript_exists()

    def test_selected_clips_exist(self, tmp_path):
        cache = CacheManager(tmp_path, "video.mp4")
        assert not cache.selected_clips_exist()
        self._make_artifact(tmp_path, "selected_clips.json", [])
        assert cache.selected_clips_exist()


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
    def _make_artifact(self, base: Path, path: str, content: object = None) -> None:
        p = base / path
        p.parent.mkdir(parents=True, exist_ok=True)
        import json
        if content is not None:
            p.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        else:
            p.write_text("{}", encoding="utf-8")

    def test_resume_skips_completed_steps(self, mock_pipeline, tmp_path):
        video_path = tmp_path / "input.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"\x00" * 100)
        src = str(video_path)

        # Create artifacts to simulate step 5 completion
        cache_dir = mock_pipeline.config.output_dir
        self._make_artifact(cache_dir, "transcript.json", {
            "segments": [[1, "test", 0.0, 5.0]],
            "words": [["test", 0.0, 5.0, 0.9]],
            "language": "en",
            "duration": 120.0,
        })
        self._make_artifact(cache_dir, "selected_clips.json", [
            {"number": 1, "start": 0.0, "end": 5.0, "score": 85.0, "title": "Clip 1", "summary": "First clip"},
            {"number": 2, "start": 10.0, "end": 15.0, "score": 90.0, "title": "Clip 2", "summary": "Second clip"},
        ])

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            result = mock_pipeline.run(src)

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

        # Simulate interruption after step 5 with artifacts
        cache_dir = mock_pipeline.config.output_dir
        self._make_artifact(cache_dir, "transcript.json", {
            "segments": [[1, "test", 0.0, 5.0]],
            "words": [["test", 0.0, 5.0, 0.9]],
            "language": "en",
            "duration": 120.0,
        })
        self._make_artifact(cache_dir, "selected_clips.json", [
            {"number": 1, "start": 0.0, "end": 5.0, "score": 85.0, "title": "Clip 1", "summary": "First clip"},
            {"number": 2, "start": 10.0, "end": 15.0, "score": 90.0, "title": "Clip 2", "summary": "Second clip"},
        ])
        # Remove artifacts from steps beyond 5 to simulate mid-run interruption
        import shutil
        for d in [cache_dir / "subtitles", cache_dir / "clips", cache_dir / "metadata", cache_dir / "pipeline_summary.json"]:
            try:
                if d.is_dir():
                    shutil.rmtree(d)
                else:
                    d.unlink(missing_ok=True)
            except OSError:
                pass

        with (
            patch("opusclip.subprocess_utils.run_ffmpeg") as mock_ffmpeg,
            patch("opusclip.rendering.validator.run_ffprobe") as mock_ffprobe,
        ):
            mock_ffmpeg.return_value.returncode = 0
            mock_ffprobe.return_value.returncode = 0
            mock_ffprobe.return_value.stdout = b'{"streams": [{"codec_type": "video", "width": 1080, "height": 1920}], "format": {"duration": "5.0"}}'
            resumed_result = mock_pipeline.run(src)

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
