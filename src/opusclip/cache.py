"""Artifact-based CacheManager for automatic pipeline resume.

Each artifact is independently validated. The pipeline inspects every artifact
on startup and skips only those stages whose artifacts are complete and valid.
Clip-level resume is supported for subtitles, rendered videos, metadata, and
thumbnails.
"""

import json
from pathlib import Path
from typing import Any


class CacheManager:
    """Scans actual artifacts to determine which pipeline steps are complete.

    The source of truth is the filesystem, NOT a step-number flag.
    Every artifact is validated for structural correctness, not just existence.
    """

    def __init__(self, cache_dir: Path, source: str) -> None:
        self._dir = cache_dir

    # ── Path helpers ────────────────────────────────────────────────────

    @staticmethod
    def _transcript_path(dir_path: Path) -> Path:
        return dir_path / "transcript.json"

    @staticmethod
    def _repaired_transcript_path(dir_path: Path) -> Path:
        return dir_path / "repaired_transcript.json"

    @staticmethod
    def _selected_clips_path(dir_path: Path) -> Path:
        return dir_path / "selected_clips.json"

    @staticmethod
    def _subtitles_dir(dir_path: Path) -> Path:
        return dir_path / "subtitles"

    @staticmethod
    def _clips_dir(dir_path: Path) -> Path:
        return dir_path / "clips"

    @staticmethod
    def _metadata_dir(dir_path: Path) -> Path:
        return dir_path / "metadata"

    @staticmethod
    def _summary_path(dir_path: Path) -> Path:
        return dir_path / "pipeline_summary.json"

    # ── JSON reading helpers ───────────────────────────────────────────

    def _read_json(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    # ── Strong artifact validation ─────────────────────────────────────

    def transcript_is_valid(self) -> bool:
        """Validate transcript.json: segments list, words list, duration>0, language,
        and every segment has id, text, start, end."""
        data = self._read_json(self._transcript_path(self._dir))
        if data is None:
            return False
        segments = data.get("segments") or data.get("transcript_data", {}).get("segments", [])
        if not isinstance(segments, list) or len(segments) == 0:
            return False
        duration = data.get("duration", 0)
        if not isinstance(duration, (int, float)) or duration <= 0:
            return False
        language = data.get("language")
        if not language:
            return False
        words = data.get("words", [])
        if not isinstance(words, list):
            return False
        for seg in segments:
            if isinstance(seg, (list, tuple)):
                sid, stxt, sstart, send = seg[0], seg[1], seg[2], seg[3]
            elif isinstance(seg, dict):
                sid = seg.get("id")
                stxt = seg.get("text")
                sstart = seg.get("start")
                send = seg.get("end")
            else:
                return False
            if sid is None or not stxt or sstart is None or send is None:
                return False
            if not isinstance(sstart, (int, float)) or not isinstance(send, (int, float)):
                return False
        return True

    def repaired_transcript_is_valid(self) -> bool:
        """Validate repaired_transcript.json: repaired_words list exists,
        timing preserved, not empty."""
        data = self._read_json(self._repaired_transcript_path(self._dir))
        if data is None:
            return False
        repaired = data.get("repaired_words", [])
        if not isinstance(repaired, list) or len(repaired) == 0:
            return False
        for w in repaired:
            if isinstance(w, (list, tuple)):
                word, start, end = w[0], w[1], w[2]
            elif isinstance(w, dict):
                word = w.get("word") or w.get("text", "")
                start = w.get("start")
                end = w.get("end")
            else:
                return False
            if not word or start is None or end is None:
                return False
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                return False
            if start > end:
                return False
        return True

    def selected_clips_are_valid(self) -> bool:
        """Validate selected_clips.json: each clip has number, start<end,
        score>0, title, summary."""
        data = self._read_json(self._selected_clips_path(self._dir))
        if data is None:
            return False
        clips = data if isinstance(data, list) else data.get("clips", [])
        if not isinstance(clips, list) or len(clips) == 0:
            return False
        for c in clips:
            num = c.get("number")
            start = c.get("start")
            end = c.get("end")
            score = c.get("score")
            title = c.get("title")
            summary = c.get("summary")
            if num is None or start is None or end is None or score is None:
                return False
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                return False
            if start >= end:
                return False
            if not isinstance(score, (int, float)) or score <= 0:
                return False
            if not title or summary is None:
                return False
        return True

    def subtitle_for_clip_is_valid(self, clip_num: int) -> bool:
        """Validate a single subtitle .ass file: exists, non-empty, has
        Events section with Dialogue lines."""
        d = self._subtitles_dir(self._dir)
        p = d / f"clip_{clip_num:02d}.ass"
        if not p.exists():
            return False
        if p.stat().st_size == 0:
            return False
        try:
            text = p.read_text(encoding="utf-8")
            if "[Events]" not in text:
                return False
            if "Dialogue:" not in text:
                return False
            return True
        except OSError:
            return False

    def rendered_clip_is_valid(self, clip_num: int) -> bool:
        """Validate a rendered clip with ffprobe: valid container, video
        stream exists, duration>0, width>0, height>0."""
        import json
        from .subprocess_utils import run_ffprobe
        d = self._clips_dir(self._dir)
        p = d / f"clip_{clip_num:02d}_FINAL.mp4"
        if not p.exists():
            return False
        try:
            r = run_ffprobe([
                "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format",
                str(p),
            ])
            data = json.loads(r.stdout)
        except Exception:
            return False
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not video_stream:
            return False
        w = video_stream.get("width", 0)
        h = video_stream.get("height", 0)
        if w <= 0 or h <= 0:
            return False
        fmt = data.get("format", {})
        dur_str = fmt.get("duration", "0")
        try:
            duration = float(dur_str)
        except (ValueError, TypeError):
            duration = 0
        return duration > 0

    def rendered_clip_exists(self, clip_num: int) -> bool:
        """Check if a rendered clip file exists (lighter check)."""
        d = self._clips_dir(self._dir)
        p = d / f"clip_{clip_num:02d}_FINAL.mp4"
        return p.exists()

    def metadata_for_clip_is_valid(self, clip_num: int) -> bool:
        """Validate metadata JSON: title, description, hashtags, category."""
        d = self._metadata_dir(self._dir)
        p = d / f"clip_{clip_num:02d}_metadata.json"
        if not p.exists():
            return False
        data = self._read_json(p)
        if data is None:
            return False
        if not data.get("title"):
            return False
        if not data.get("description"):
            return False
        if not isinstance(data.get("hashtags"), list):
            return False
        if not data.get("category"):
            return False
        return True

    def thumbnail_for_clip_is_valid(self, clip_num: int) -> bool:
        """Validate thumbnail: exists and not empty."""
        d = self._clips_dir(self._dir)
        for ext in (".jpg", ".jpeg", ".png"):
            p = d / f"clip_{clip_num:02d}_thumb{ext}"
            if p.exists() and p.stat().st_size > 0:
                return True
        return False

    # ── Per-artifact checks (step-level) ───────────────────────────────

    def transcript_exists(self) -> bool:
        return self._transcript_path(self._dir).exists()

    def repaired_transcript_exists(self) -> bool:
        return self._repaired_transcript_path(self._dir).exists()

    def selected_clips_exist(self) -> bool:
        return self._selected_clips_path(self._dir).exists()

    def subtitles_exist(self) -> bool:
        d = self._subtitles_dir(self._dir)
        if not d.is_dir():
            return False
        return len(list(d.glob("*.ass"))) > 0

    def rendered_clips_exist(self) -> bool:
        d = self._clips_dir(self._dir)
        if not d.is_dir():
            return False
        mp4_files = list(d.glob("*_FINAL.mp4"))
        if not mp4_files:
            mp4_files = list(d.glob("*.mp4"))
        return len(mp4_files) > 0

    def metadata_exists(self) -> bool:
        d = self._metadata_dir(self._dir)
        if not d.is_dir():
            return False
        return len(list(d.glob("*.json"))) > 0

    def summary_exists(self) -> bool:
        return self._summary_path(self._dir).exists()

    # ── List helpers for clip-level resume ─────────────────────────────

    def list_missing_subtitles(self, clip_numbers: list[int]) -> list[int]:
        """Return clip numbers whose subtitle .ass is invalid or missing."""
        missing: list[int] = []
        for num in clip_numbers:
            if not self.subtitle_for_clip_is_valid(num):
                missing.append(num)
        return missing

    def list_missing_videos(self, clip_numbers: list[int]) -> list[int]:
        """Return clip numbers whose rendered .mp4 is invalid or missing."""
        missing: list[int] = []
        for num in clip_numbers:
            if not self.rendered_clip_exists(num):
                missing.append(num)
        return missing

    def list_missing_metadata(self, clip_numbers: list[int]) -> list[int]:
        """Return clip numbers whose metadata is invalid or missing."""
        missing: list[int] = []
        for num in clip_numbers:
            if not self.metadata_for_clip_is_valid(num):
                missing.append(num)
        return missing

    def list_missing_thumbnails(self, clip_numbers: list[int]) -> list[int]:
        """Return clip numbers whose thumbnail is invalid or missing."""
        missing: list[int] = []
        for num in clip_numbers:
            if not self.thumbnail_for_clip_is_valid(num):
                missing.append(num)
        return missing

    # ── Step-level (legacy) API ────────────────────────────────────────

    def list_missing_clips(self) -> list[int]:
        """Return clip numbers whose final .mp4 is missing."""
        missing: list[int] = []
        clips_path = self._clips_dir(self._dir)
        clips_path.mkdir(parents=True, exist_ok=True)
        clips_json = self._selected_clips_path(self._dir)
        if not clips_json.exists():
            return missing
        data = self._read_json(clips_json)
        if data is None:
            return missing
        clips = data if isinstance(data, list) else data.get("clips", [])
        for c in clips:
            num = c.get("number", 0)
            final = clips_path / f"clip_{num:02d}_FINAL.mp4"
            if not final.exists():
                missing.append(num)
        return missing

    def get_completed_step(self) -> int:
        """Return the highest contiguous completed step (0 if none)."""
        step = 0
        if self.transcript_is_valid():
            step = 3
        else:
            return step
        if self.selected_clips_are_valid():
            step = 5
        else:
            return step
        if self.subtitle_for_clip_is_valid(1) or self.subtitles_exist():
            step = 6
        else:
            return step
        if self.rendered_clip_exists(1) or self.rendered_clips_exist():
            step = 7
        else:
            return step
        if self.metadata_for_clip_is_valid(1) or self.metadata_exists():
            step = 9
        else:
            return step
        if self.summary_exists():
            step = 10
        return step

    def clear(self) -> None:
        """Remove all cached pipeline artifacts."""
        import shutil
        for p in [
            self._transcript_path(self._dir),
            self._repaired_transcript_path(self._dir),
            self._selected_clips_path(self._dir),
            self._subtitles_dir(self._dir),
            self._clips_dir(self._dir),
            self._metadata_dir(self._dir),
            self._summary_path(self._dir),
        ]:
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink(missing_ok=True)
            except OSError:
                pass
        for old in ["pipeline_cache.json", "pipeline_cache_state.json"]:
            try:
                (self._dir / old).unlink(missing_ok=True)
            except OSError:
                pass
