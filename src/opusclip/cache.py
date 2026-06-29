"""Minimal CacheManager for step-level pipeline resume."""

import json
from pathlib import Path


class CacheManager:
    """Tracks completed pipeline steps in a JSON file for resume support.

    Stores the source identifier and the highest completed step number.
    Before considering a step completed, verifies the cache belongs to
    the same source — a cache from a different video is silently ignored.

    Only stores metadata; no intermediate Python objects are cached.
    If a skipped step requires data no longer in memory, the step is
    re-executed.
    """

    def __init__(self, cache_dir: Path, source: str) -> None:
        self._path = cache_dir / "pipeline_cache.json"
        self._source = source

    def is_step_completed(self, step: int) -> bool:
        return self.get_completed_step() >= step

    def mark_step_completed(self, step: int) -> None:
        try:
            data = {"source": self._source, "completed_step": step}
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get_completed_step(self) -> int:
        if not self._path.exists():
            return 0
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("source") != self._source:
                return 0
            return data.get("completed_step", 0)
        except (json.JSONDecodeError, OSError):
            return 0

    def clear(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass
