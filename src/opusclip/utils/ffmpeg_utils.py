"""
FFmpeg utilities for safe, isolated process management.
"""

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
            return self.process.stdin
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
