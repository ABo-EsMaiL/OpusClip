"""
FFmpeg utilities for safe, isolated process management.
"""

import functools
import subprocess
from ..exceptions import RenderingError


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    """Run FFmpeg command synchronously."""
    try:
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode != 0:
            raise RenderingError(f"FFmpeg failed: {r.stderr[-500:]}")
        return r
    except OSError as e:
        raise RenderingError(f"Failed to execute FFmpeg: {e}") from e


class FFmpegPipe:
    """Context manager for piping frames safely into FFmpeg."""

    def __init__(self, args: list[str]):
        self.args = args
        self.process = None

    def __enter__(self):
        try:
            self.process = subprocess.Popen(
                self.args, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            self.stdin = self.process.stdin
            return self
        except OSError as e:
            raise RenderingError(f"Failed to open FFmpeg pipe: {e}") from e

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            if self.process.stdin:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()

            if (
                self.process.returncode is not None
                and self.process.returncode != 0
                and exc_type is None
            ):
                raise RenderingError(f"FFmpeg pipe failed with exit code {self.process.returncode}")


@functools.lru_cache(maxsize=1)
def check_encoder_available(encoder_name: str) -> bool:
    """Check if ffmpeg has the given encoder available on this system.

    Results are cached via ``lru_cache`` so ``ffmpeg -encoders`` is
    only invoked once per process lifetime.
    """
    try:
        r = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True, text=True, timeout=30,
        )
        return encoder_name in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_encoder_args(
    encoder_name: str,
    crf: int,
    preset: str = "fast",
    raw_extract: bool = False,
) -> list[str]:
    """Build encoder-specific FFmpeg arguments.

    Args:
        encoder_name: ffmpeg encoder (libx264, h264_nvenc, etc.)
        crf: Quality/CRF value (or CQ value for NVENC).
        preset: Encoding preset (fast, ultrafast, p4, etc.).
        raw_extract: If True, use fastest possible settings.

    Returns:
        List of encoder arguments suitable for an FFmpeg command line.
    """
    if encoder_name == "h264_nvenc":
        nvenc_preset = "p1" if raw_extract else "p4"
        return [
            "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-cq", str(crf),
            "-rc", "vbr_hq",
            "-b:v", "0",
        ]
    return [
        "-c:v", encoder_name,
        "-preset", preset,
        "-crf", str(crf),
    ]
