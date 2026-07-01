import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class PipelineMetrics:
    """Collects timing, counter, and memory metrics for a single pipeline run."""

    stages: dict[str, float] = field(default_factory=dict)
    clip_renders: dict[int, float] = field(default_factory=dict)
    total_duration: float = 0.0
    api_calls: int = 0
    api_retries: int = 0
    failures: int = 0
    peak_ram_mb: float = 0.0
    peak_vram_mb: float = 0.0
    _start_time: float = 0.0

    def start(self) -> None:
        self._start_time = time.monotonic()

    def finish(self) -> None:
        self.total_duration = time.monotonic() - self._start_time

    @contextmanager
    def measure_stage(self, name: str):
        t0 = time.monotonic()
        try:
            yield
        finally:
            self.stages[name] = time.monotonic() - t0

    def record_clip_render(self, clip_num: int, duration: float) -> None:
        self.clip_renders[clip_num] = duration

    def record_memory(self) -> None:
        """Capture peak RAM and (optionally) VRAM usage."""
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            self.peak_ram_mb = proc.memory_info().rss / (1024 * 1024)
        except ImportError:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                self.peak_vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
                torch.cuda.reset_peak_memory_stats()
        except ImportError:
            pass

    def report(self) -> str:
        lines = []
        lines.append(f"Total duration: {self.total_duration:.2f}s")
        more = []
        if self.peak_ram_mb:
            more.append(f"Peak RAM: {self.peak_ram_mb:.0f} MB")
        if self.peak_vram_mb:
            more.append(f"Peak VRAM: {self.peak_vram_mb:.0f} MB")
        if self.api_calls:
            more.append(f"API calls: {self.api_calls}")
        if self.api_retries:
            more.append(f"Retries: {self.api_retries}")
        if self.failures:
            more.append(f"Failures: {self.failures}")
        if more:
            lines.append(" | ".join(more))
        if self.stages:
            lines.append("")
            lines.append("Stage timing:")
            for name, elapsed in sorted(self.stages.items(), key=lambda x: x[1], reverse=True):
                pct = (elapsed / self.total_duration * 100) if self.total_duration else 0
                lines.append(f"  {name}: {elapsed:.2f}s ({pct:.1f}%)")
        if self.clip_renders:
            lines.append("")
            lines.append(f"Clip renders ({len(self.clip_renders)} total):")
            for num, elapsed in sorted(self.clip_renders.items()):
                lines.append(f"  Clip {num}: {elapsed:.2f}s")
        return "\n".join(lines)
