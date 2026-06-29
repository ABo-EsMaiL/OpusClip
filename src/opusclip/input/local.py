import json
from pathlib import Path
from ..subprocess_utils import run_ffprobe
from .base import InputProvider, VideoMetadata
from ..input_validator import validate_video_path
from ..exceptions import InputValidationError


class LocalFileProvider(InputProvider):
    """Acquires a video from a local file path.

    Validates the path, copies the file to the output directory, and extracts
    metadata via ffprobe.
    """

    def acquire(self, source: str, output_dir: Path) -> VideoMetadata:
        """Copy the local video to output_dir and extract metadata via ffprobe."""
        src = validate_video_path(source)
        dest = output_dir / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            import shutil
            shutil.copy2(str(src), str(dest))
        probe = run_ffprobe([
            "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", str(dest),
        ])
        data = json.loads(probe.stdout.decode("utf-8"))
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
        )
        if not video_stream:
            raise InputValidationError(f"No video stream found in {source}")
        w = int(video_stream.get("width", 0))
        h = int(video_stream.get("height", 0))
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 0.0
        else:
            fps = float(fps_str)
        duration = float(data.get("format", {}).get("duration", 0))
        return VideoMetadata(path=dest, width=w, height=h, fps=fps, duration=duration)
