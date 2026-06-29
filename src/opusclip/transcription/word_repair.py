"""
Word-timestamp repair utility.

Whisper occasionally omits word-level timestamps for the first one or two
words of a segment (usually very short words such as Arabic particles).
``fill_missing_words`` reconstructs those timestamps by linear interpolation
over the available silence before the first timestamped word.
"""

from .base import TranscriptResult, WordInfo

# A segment is considered adequately covered when the number of timestamped
# words reaches at least this fraction of the total words in the segment text.
_COVERAGE_RATIO: float = 0.70

# Minimum silence required per missing word before attempting interpolation.
# Below this threshold the gap is too small to distribute reliably.
_MIN_SILENCE_PER_WORD_S: float = 0.05

# Probability assigned to reconstructed word entries. This value is lower than
# real ASR probabilities to signal that the timing was inferred, not measured.
_INFERRED_PROBABILITY: float = 0.60


def fill_missing_words(transcript: TranscriptResult) -> list[WordInfo]:
    """Recover word-level timestamps that Whisper omits from segment output.

    For each segment, if the ratio of timestamped words to total segment-text
    words falls below :data:`_COVERAGE_RATIO`, the function identifies missing
    words and assigns them interpolated timestamps within the pre-first-word gap.

    Args:
        transcript: The raw :class:`TranscriptResult` from the transcription
            provider. Only ``segments`` are read; the top-level ``words`` list
            is rebuilt and returned.

    Returns:
        A flat, chronologically sorted list of :class:`WordInfo` objects
        combining both original and reconstructed entries.
    """
    result: list[WordInfo] = []

    for seg in transcript.segments:
        ts_words = seg.words
        txt_words = [w for w in seg.text.strip().split() if w]

        # Segment is adequately covered — use timestamped words as-is.
        if not txt_words or len(ts_words) >= len(txt_words) * _COVERAGE_RATIO:
            result.extend(ts_words)
            continue

        ts_texts = {w.word.strip() for w in ts_words}
        missing = [w for w in txt_words if w not in ts_texts]

        if not missing:
            result.extend(ts_words)
            continue

        # Time available before the first known word in this segment.
        first_known_start = ts_words[0].start if ts_words else seg.end
        gap = first_known_start - seg.start

        if gap >= _MIN_SILENCE_PER_WORD_S * len(missing):
            dt = gap / len(missing)
            for i, mw in enumerate(missing):
                clean_mw = mw.strip()
                if not clean_mw:
                    continue
                result.append(
                    WordInfo(
                        word=clean_mw,
                        start=round(seg.start + i * dt, 3),
                        end=round(seg.start + (i + 1) * dt, 3),
                        probability=_INFERRED_PROBABILITY,
                    )
                )

        result.extend(ts_words)

    return sorted(result, key=lambda w: w.start)
