from pathlib import Path
from .base import InputProvider, VideoMetadata
from ..input_validator import validate_youtube_url
from ..subprocess_utils import run_ytdlp
from ..exceptions import InputValidationError


class YouTubeProvider(InputProvider):
    def acquire(self, source: str, output_dir: Path) -> VideoMetadata:
        validate_youtube_url(source)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_template = str(output_dir / "%(title)s.%(ext)s")
        run_ytdlp([
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "--merge-output-format", "mp4",
            "-o", out_template,
            source,
        ])
        list_result = run_ytdlp([
            "--print", "%(filename)s",
            "-o", out_template,
            source,
        ])
        expected_name = list_result.stdout.strip().split("\n")[-1].strip()
        video_path = output_dir / expected_name
        if not video_path.exists():
            candidates = sorted(
                [f for f in output_dir.iterdir() if f.suffix.lower() in (".mp4", ".mkv", ".mov")],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if candidates:
                video_path = candidates[0]
            else:
                raise InputValidationError(f"Could not locate downloaded video in {output_dir}")
        probe = run_ytdlp(["--print", "%(width)s", "--print", "%(height)s", "--print", "%(fps)s", "--print", "%(duration)s", source])
        parts = probe.stdout.strip().split("\n")
        w = int(parts[0]) if len(parts) > 0 else 0
        h = int(parts[1]) if len(parts) > 1 else 0
        fps = float(parts[2]) if len(parts) > 2 else 30.0
        duration = float(parts[3]) if len(parts) > 3 else 0.0
        return VideoMetadata(path=video_path, width=w, height=h, fps=fps, duration=duration)
