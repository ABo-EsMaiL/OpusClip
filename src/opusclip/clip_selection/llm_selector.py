"""
LLM-based viral clip selector.

Implements :class:`~opusclip.clip_selection.base.ClipSelector` using an
OpenAI-compatible API to identify the most viral segments from a transcript.
"""

import json
from typing import Literal

from openai import OpenAI, OpenAIError

from .base import ClipSelector, ClipCandidate
from ..transcription.base import TranscriptResult, TranscriptSegment
from ..config import PipelineConfig
from ..utils.json_utils import extract_json_array
from ..utils.retry_utils import with_retry
from ..exceptions import ClipSelectionError
from .prompts import get_clip_selection_prompt

# Maximum time in seconds allowed to snap a generated timestamp to a real segment.
_MAX_SNAP_WINDOW_S: float = 4.0

# Temperature used for the LLM API call. Kept low to ensure structured JSON formatting.
_LLM_TEMPERATURE: float = 0.20


class LLMClipSelector(ClipSelector):
    """Selects viral clips from a transcript using a large language model.

    The selector compresses the transcript to fit within the LLM context
    window, sends it to the configured API, and parses the structured JSON
    response into :class:`ClipCandidate` objects.

    Args:
        api_key: API key for the OpenAI-compatible endpoint.
        base_url: Base URL of the API (e.g. Groq, Gemini, or opencode.ai).
        model: Model identifier string.
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _snap_boundary(
        self,
        ts: float,
        segments: list[TranscriptSegment],
        direction: Literal["start", "end"] = "start",
        window: float = _MAX_SNAP_WINDOW_S,
    ) -> float:
        """Snap a raw LLM timestamp to the nearest real segment boundary.

        Args:
            ts: Raw timestamp from the LLM response (seconds).
            segments: Segment list from the transcript.
            direction: Whether to snap to a segment ``"start"`` or ``"end"``.
            window: Maximum allowed snap distance in seconds.

        Returns:
            The snapped timestamp (seconds), rounded to 3 decimal places.
        """
        best, best_d = float(ts), float("inf")
        for seg in segments:
            cand = seg.start if direction == "start" else seg.end
            d = abs(cand - ts)
            if d < best_d and d <= window:
                best, best_d = cand, d
        return round(best, 3)

    def _compress_transcript(self, segments: list[TranscriptSegment], max_chars: int) -> str:
        """Uniformly sample transcript lines to fit within *max_chars*.

        Args:
            segments: Full segment list.
            max_chars: Character budget for the compressed output.

        Returns:
            A newline-joined string of sampled transcript lines.
        """
        all_lines = [f"[{s.start:.1f}s-{s.end:.1f}s]: {s.text}" for s in segments]
        total = sum(len(line) for line in all_lines)
        if total <= max_chars:
            return "\n".join(all_lines)
        step = max(1, round(total / max_chars))
        out: list[str] = []
        budget = 0
        for i, (seg, line) in enumerate(zip(segments, all_lines)):
            if i % step != 0:
                continue
            if budget + len(line) + 1 > max_chars:
                out.append(f"[… {segments[-1].end:.0f}s total …]")
                break
            out.append(line)
            budget += len(line) + 1
        return "\n".join(out)

    def select_clips(
        self, transcript: TranscriptResult, config: PipelineConfig
    ) -> list[ClipCandidate]:
        """Analyse a transcript and return a ranked list of clip candidates.

        Args:
            transcript: Full transcription result including all segments.
            config: Pipeline configuration supplying clip constraints and
                API retry policy.

        Returns:
            A list of :class:`ClipCandidate` objects sorted by score
            (highest first).

        Raises:
            RuntimeError: If the API returns no parsable clips after all
                retry attempts.
        """
        lang_hint = transcript.language or "ar"
        clip_system = get_clip_selection_prompt(
            min_clips=config.min_clips,
            max_clips=config.max_clips,
            min_duration=config.min_duration,
            max_duration=config.max_duration,
            min_virality=config.min_virality,
            lang_hint=lang_hint,
        )
        tx_text = self._compress_transcript(transcript.segments, config.max_llm_chars)

        @with_retry(
            attempts=config.api_retry_attempts,
            delay_s=config.api_retry_delay_s,
            backoff_factor=config.api_retry_backoff_factor,
            exceptions=(OpenAIError, json.JSONDecodeError, ValueError),
        )
        def _fetch_clips() -> list[dict[str, object]]:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": clip_system},
                    {"role": "user", "content": f"Transcript:\n\n{tx_text}"},
                ],
                temperature=_LLM_TEMPERATURE,
            )
            raw_json = resp.choices[0].message.content or ""
            parsed = extract_json_array(raw_json)
            if parsed is None:
                raise ValueError("Failed to parse JSON array from LLM response.")
            return parsed  # type: ignore[return-value]

        try:
            clips_raw = _fetch_clips()
        except Exception as exc:
            raise ClipSelectionError(
                f"Clip selection failed after {config.api_retry_attempts} attempts."
            ) from exc

        required = {
            "clip_number",
            "title",
            "start",
            "end",
            "virality_score",
            "score_breakdown",
            "hook_line",
            "reason",
        }
        selected_clips: list[ClipCandidate] = []

        for c in clips_raw:
            if not required.issubset(c.keys()):
                continue
            try:
                v_score = float(c["virality_score"])  # type: ignore[arg-type]
                c_start_raw = float(c["start"])  # type: ignore[arg-type]
                c_end_raw = float(c["end"])  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue

            if v_score < config.min_virality:
                continue

            c_start = self._snap_boundary(c_start_raw, transcript.segments, "start")
            c_end = self._snap_boundary(c_end_raw, transcript.segments, "end")
            duration = round(c_end - c_start, 1)

            if not (config.min_duration <= duration <= config.max_duration):
                continue

            selected_clips.append(
                ClipCandidate(
                    start=c_start,
                    end=c_end,
                    score=v_score,
                    title=str(c["title"]),
                    summary=str(c["reason"]),
                )
            )

        if not selected_clips:
            raise ClipSelectionError(
                "No valid clips remain after applying virality and duration constraints."
            )

        selected_clips.sort(key=lambda x: x.score, reverse=True)
        return selected_clips
