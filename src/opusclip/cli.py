import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Optional

from .config import PipelineConfig
from .pipeline import PipelineResult
from .provider_factory import ProviderFactory
from .exceptions import OpusClipError


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Supports single or multiple video sources, renderer backend selection,
    encoder override, resume flag, and log-level configuration.
    """
    parser = argparse.ArgumentParser(
        prog="opusclip",
        description="AI-powered automatic short-video pipeline from long-form content.",
    )
    parser.add_argument(
        "input", type=str, nargs="+",
        help="Path to input video file(s) or YouTube URL(s).",
    )
    parser.add_argument("--output", "-o", type=str, default=None, help="Output directory.")
    parser.add_argument("--min-clips", type=int, default=None, help="Minimum number of clips.")
    parser.add_argument("--max-clips", type=int, default=None, help="Maximum number of clips.")
    parser.add_argument(
        "--renderer", type=str, default=None, choices=["optimized", "legacy"],
        help="Renderer backend to use.",
    )
    parser.add_argument(
        "--encoder", type=str, default=None,
        help="FFmpeg video encoder (e.g. libx264, h264_nvenc). Default: libx264.",
    )
    parser.add_argument(
        "--resume", action="store_true", default=False,
        help="Resume a previously interrupted pipeline from the last completed step.",
    )
    parser.add_argument(
        "--log-level", type=str, default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level.",
    )
    return parser


def _dictify(result: PipelineResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "error": result.error,
        "output_dir": str(result.output_dir) if result.output_dir else None,
        "source_duration_s": result.duration,
        "total_clips": result.total_clips,
        "successful_clips": result.successful_clips,
        "failed_clips": result.failed_clips,
        "clips": [
            {
                "number": c.number,
                "video": str(c.video_path) if c.video_path else None,
                "thumbnail": str(c.thumbnail_path) if c.thumbnail_path else None,
                "success": c.success,
                "error": c.error,
                "metadata": {
                    "title": c.metadata.title if c.metadata else None,
                    "description": c.metadata.description if c.metadata else None,
                    "hashtags": c.metadata.hashtags if c.metadata else [],
                } if c.metadata else None,
            }
            for c in result.clips
        ],
    }


def run_cli(argv: Optional[List[str]] = None) -> int:
    """Execute the CLI pipeline for one or more video sources.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    overrides: dict[str, Any] = {}
    if args.output is not None:
        overrides["output_dir"] = Path(args.output)
    if args.min_clips is not None:
        overrides["min_clips"] = args.min_clips
    if args.max_clips is not None:
        overrides["max_clips"] = args.max_clips
    if args.renderer is not None:
        overrides["renderer_backend"] = args.renderer
    if args.encoder is not None:
        overrides["encoder"] = args.encoder
    if args.log_level is not None:
        overrides["log_level"] = args.log_level

    config = PipelineConfig.from_env(**overrides)

    factory = ProviderFactory(config)
    sources = args.input

    try:
        if len(sources) == 1:
            pipeline = factory.create_pipeline(sources[0])
            result = pipeline.run(sources[0], resume=args.resume)
            print(json.dumps(_dictify(result), indent=2, ensure_ascii=False))
        else:
            results: list[PipelineResult] = []
            for src in sources:
                pipeline = factory.create_pipeline(src)
                result = pipeline.run(src, resume=args.resume)
                results.append(result)
            print(json.dumps([_dictify(r) for r in results], indent=2, ensure_ascii=False))
    except OpusClipError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


def main() -> None:
    """CLI entry point. Parses arguments and runs the pipeline."""
    sys.exit(run_cli())
