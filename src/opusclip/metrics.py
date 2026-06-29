import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class PipelineMetrics:
    """Collects timing and counter metrics for a single pipeline run.

    Attributes:
        stages: Map of stage name to elapsed wall-clock time in seconds.
        clip_renders: Map of clip number to render duration in seconds.
        total_duration: Total pipeline wall-clock time in seconds.
        api_calls: Number of LLM API calls made.
        api_retries: Number of LLM API retries attempted.
        failures: Number of stage/clip failures encountered.
    """
    stages: dict[str, float] = field(default_factory=dict)
    clip_renders: dict[int, float] = field(default_factory=dict)
    total_duration: float = 0.0
    api_calls: int = 0
    api_retries: int = 0
    failures: int = 0
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

    def report(self) -> str:
        lines = []
        lines.append(f"Total duration: {self.total_duration:.2f}s")
        more = []
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
