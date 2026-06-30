"""
LLM-based viral clip selector.

Implements :class:`~opusclip.clip_selection.base.ClipSelector` using an
OpenAI-compatible API to identify the most viral segments from a transcript.
"""

import json
import traceback
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

    The selector sends the transcript (optionally compressed) to the configured API
    and parses the structured JSON response into :class:`ClipCandidate` objects.

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

    @staticmethod
    def _compress_transcript(
        segments: list[TranscriptSegment], max_chars: int = 28000
    ) -> str:
        """Sample evenly across the full video within char budget.

        Matches the behaviour of the original ``compress_transcript()``
        in the legacy notebook — uniform sampling if the transcript exceeds
        *max_chars* characters.

        Args:
            segments: List of transcript segments.
            max_chars: Maximum allowed character count for the output string.

        Returns:
            A single string with one ``[start-end]: text`` line per retained
            segment, joined by newlines.
        """
        all_lines = [
            f"[{s.start:.1f}s-{s.end:.1f}s]: {s.text}" for s in segments
        ]
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
        print(f"    Sampled {len(out)}/{len(segments)} segments "
              f"({budget:,}/{total:,} chars)")
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
        tx_text = self._compress_transcript(
            transcript.segments, config.max_llm_chars
        )
        print("=" * 80)
        print("Transcript chars:", len(tx_text))
        print("Prompt chars:", len(tx_text) + len(clip_system))
        print("=" * 80)

        @with_retry(
            attempts=config.api_retry_attempts,
            delay_s=config.api_retry_delay_s,
            backoff_factor=config.api_retry_backoff_factor,
            exceptions=(OpenAIError, json.JSONDecodeError, ValueError),
        )
        def _fetch_clips() -> list[dict[str, object]]:
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": clip_system},
                        {"role": "user", "content": f"Transcript:\n\n{tx_text}"},
                    ],
                    temperature=_LLM_TEMPERATURE,
                )
            except OpenAIError as e:
                status = getattr(e, "status_code", None)
                if status is None:
                    status = getattr(e, "status", None)
                body = getattr(e, "body", None)
                request_id = getattr(e, "request_id", None)
                print("  [OpenAI Error]")
                if status is not None:
                    print(f"    status_code : {status}")
                if request_id is not None:
                    print(f"    request_id  : {request_id}")
                if body is not None:
                    import json as _json
                    print(f"    body        : {_json.dumps(body, indent=2, ensure_ascii=False)}")
                raise

            raw_json = resp.choices[0].message.content or ""
            parsed = extract_json_array(raw_json)
            if parsed is None:
                print("  [JSON Parse Error] Failed to extract JSON array from LLM response.")
                print(f"    Raw response ({len(raw_json)} chars):")
                print(f"    {raw_json[:2000]}")
                if len(raw_json) > 2000:
                    print(f"    ... ({len(raw_json) - 2000} more chars)")
                try:
                    failed_path = config.output_dir / "llm_failed_response.txt"
                    failed_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(failed_path, "w", encoding="utf-8") as f:
                        f.write(raw_json)
                    print(f"    Full response saved to: {failed_path}")
                except Exception:
                    pass
                raise ValueError("Failed to parse JSON array from LLM response.")
            return parsed  # type: ignore[return-value]

        try:
            clips_raw = _fetch_clips()
        except Exception as exc:
            print("\n  [Clip Selection Failed]")
            print(f"    Type  : {type(exc).__name__}")
            print(f"    Reason: {exc}")
            cause = exc.__cause__
            while cause is not None:
                print(f"    Caused by: {type(cause).__name__}: {cause}")
                cause = cause.__cause__
            traceback.print_exception(type(exc), exc, exc.__traceback__)
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
