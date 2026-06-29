import subprocess
from typing import List


def run_ffmpeg(args: List[str]) -> subprocess.CompletedProcess[bytes]:
    """
    Runs an FFmpeg command safely using list-based subprocess.run without shell=True.
    """
    cmd = ["ffmpeg"] + args
    return subprocess.run(cmd, check=True, capture_output=True)


def run_ytdlp(args: List[str]) -> subprocess.CompletedProcess[bytes]:
    """
    Runs a yt-dlp command safely using list-based subprocess.run without shell=True.
    """
    cmd = ["yt-dlp"] + args
    return subprocess.run(cmd, check=True, capture_output=True)


def run_ffprobe(args: List[str]) -> subprocess.CompletedProcess[bytes]:
    """
    Runs an ffprobe command safely using list-based subprocess.run without shell=True.
    """
    cmd = ["ffprobe"] + args
    return subprocess.run(cmd, check=True, capture_output=True)
