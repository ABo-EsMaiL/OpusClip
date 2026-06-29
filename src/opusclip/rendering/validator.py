"""
Validation utilities for checking final rendered output using ffprobe.
"""

import json
from pathlib import Path
from ..exceptions import RenderingError


def validate_rendered_video(path: Path, expected_width: int, expected_height: int) -> None:
    """
    Runs ffprobe to ensure the output video exists, is valid, and matches expectations.

    Args:
        path: Path to the output video.
        expected_width: Target width.
        expected_height: Target height.

    Raises:
        RenderingError: If the video is invalid, unreadable, or doesn't match dimensions.
    """
    if not path.exists():
        raise RenderingError(f"Output video missing at {path}")

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]

    # We use subprocess directly here since run_ffmpeg expects ffmpeg binary.
    import subprocess

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RenderingError(f"ffprobe validation failed for {path}: {e.stderr}")

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RenderingError(f"Could not parse ffprobe output for {path}")

    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

    if not video_stream:
        raise RenderingError(f"No video stream found in {path}")

    w = video_stream.get("width")
    h = video_stream.get("height")

    if w != expected_width or h != expected_height:
        raise RenderingError(
            f"Resolution mismatch: expected {expected_width}x{expected_height}, got {w}x{h}"
        )
