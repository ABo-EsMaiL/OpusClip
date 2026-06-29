import json
from pathlib import Path
from unittest.mock import patch

import pytest

from opusclip.cli import build_parser, run_cli
from opusclip.pipeline import PipelineResult, ClipResult
from opusclip.exceptions import OpusClipError


class TestCliParsing:
    def test_help(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_no_input_errors(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_invalid_renderer(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["input.mp4", "--renderer", "invalid"])

    def test_invalid_log_level(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["input.mp4", "--log-level", "INVALID"])

    def test_multiple_sources(self):
        parser = build_parser()
        args = parser.parse_args(["a.mp4", "b.mp4", "c.mp4"])
        assert args.input == ["a.mp4", "b.mp4", "c.mp4"]

    def test_negative_min_clips(self):
        parser = build_parser()
        args = parser.parse_args(["input.mp4", "--min-clips", "-1"])
        assert args.min_clips == -1


class TestCliRunFailure:
    def test_run_cli_returns_1_on_error(self):
        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_factory.return_value.create_pipeline.side_effect = OpusClipError("test error")
            rc = run_cli(["input.mp4"])
            assert rc == 1

    def test_run_cli_prints_error_to_stderr(self, capsys):
        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_factory.return_value.create_pipeline.side_effect = OpusClipError("something went wrong")
            run_cli(["input.mp4"])
            _stdout, stderr = capsys.readouterr()
            assert "something went wrong" in stderr

    def test_batch_one_failure_does_not_abort(self):
        success_result = PipelineResult(
            source="a.mp4", output_dir=Path("/out/a"), error=None,
            duration=10.0, total_clips=1, successful_clips=1, failed_clips=0,
            clips=[ClipResult(number=1, video_path=Path("a.mp4"), thumbnail_path=Path("a.jpg"), success=True, error=None)],
        )

        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_pipeline = mock_factory.return_value.create_pipeline.return_value
            mock_pipeline.run.side_effect = [
                success_result,
                OpusClipError("second video failed"),
            ]
            rc = run_cli(["a.mp4", "b.mp4"])
            assert rc == 1


class TestCliRunSuccess:
    def test_run_cli_returns_0_on_success(self):
        result = PipelineResult(
            source="input.mp4", output_dir=Path("/out"), error=None,
            duration=10.0, total_clips=1, successful_clips=1, failed_clips=0,
            clips=[ClipResult(number=1, video_path=Path("clip.mp4"), thumbnail_path=Path("clip.jpg"), success=True, error=None)],
        )
        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_factory.return_value.create_pipeline.return_value.run.return_value = result
            rc = run_cli(["input.mp4"])
            assert rc == 0

    def test_single_source_prints_json_object(self, capsys):
        result = PipelineResult(
            source="input.mp4", output_dir=Path("/out"), error=None,
            duration=10.0, total_clips=1, successful_clips=1, failed_clips=0,
            clips=[ClipResult(number=1, video_path=Path("clip.mp4"), thumbnail_path=Path("clip.jpg"), success=True, error=None)],
        )

        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_factory.return_value.create_pipeline.return_value.run.return_value = result
            run_cli(["input.mp4"])
            stdout, _stderr = capsys.readouterr()
            data = json.loads(stdout)
            assert data["source"] == "input.mp4"

    def test_multi_source_prints_json_array(self, capsys):
        results = [
            PipelineResult(source="a.mp4", output_dir=Path("/out/a"), error=None,
                           duration=10.0, total_clips=1, successful_clips=1, failed_clips=0,
                           clips=[ClipResult(number=1, video_path=Path("a.mp4"), thumbnail_path=Path("a.jpg"), success=True, error=None)]),
            PipelineResult(source="b.mp4", output_dir=Path("/out/b"), error=None,
                           duration=15.0, total_clips=2, successful_clips=2, failed_clips=0,
                           clips=[ClipResult(number=1, video_path=Path("b1.mp4"), thumbnail_path=Path("b1.jpg"), success=True, error=None),
                                  ClipResult(number=2, video_path=Path("b2.mp4"), thumbnail_path=Path("b2.jpg"), success=True, error=None)]),
        ]
        with (
            patch("opusclip.cli.ProviderFactory") as mock_factory,
            patch("opusclip.cli.PipelineConfig.from_env"),
        ):
            mock_pipeline = mock_factory.return_value.create_pipeline.return_value
            mock_pipeline.run.side_effect = results
            run_cli(["a.mp4", "b.mp4"])
            stdout, _stderr = capsys.readouterr()
            data = json.loads(stdout)
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["source"] == "a.mp4"
            assert data[1]["source"] == "b.mp4"