"""
Whisper-based transcription provider.

Implements TranscriptionProvider using the faster-whisper library.
"""

import gc
from pathlib import Path

from faster_whisper import WhisperModel

from .base import TranscriptionProvider, TranscriptResult, TranscriptSegment, WordInfo


def _is_hallucination(words: list[WordInfo]) -> bool:
    """Detect if a segment is likely a hallucination based on excessive word repetition.
    
    Args:
        words: List of words in the segment.
        
    Returns:
        True if the segment appears to be a hallucination, False otherwise.
    """
    if len(words) < _MIN_SEGMENT_LENGTH_FOR_CHECK:
        return False
    
    # Count word frequency (case-insensitive, normalized)
    word_counts: dict[str, int] = {}
    for w in words:
        normalized = w.word.lower().strip()
        if not normalized:
            continue
        word_counts[normalized] = word_counts.get(normalized, 0) + 1
    
    if not word_counts:
        return False
    
    # Calculate repetition ratio (most common word / total words)
    max_count = max(word_counts.values())
    total_count = len(words)
    repetition_ratio = max_count / total_count
    
    # If more than 50% of words are the same, it's likely hallucination
    return repetition_ratio > _MAX_REPETITION_RATIO

# Minimum word probability accepted from Whisper output. Words below this
# threshold are typically hallucinations or low-confidence tokens.
_MIN_WORD_PROBABILITY: float = 0.55

# Default quantisation mode passed to CTranslate2 for the Whisper model.
# Using float16 significantly reduces VRAM usage with negligible accuracy loss.
_COMPUTE_TYPE: str = "float16"

# Minimum silence duration in milliseconds required for VAD to segment audio.
_VAD_MIN_SILENCE_MS: int = 400

# Maximum ratio of repeated words to total words before considering segment as hallucination.
_MAX_REPETITION_RATIO: float = 0.5

# Minimum segment length (in words) required to perform repetition check.
_MIN_SEGMENT_LENGTH_FOR_CHECK: int = 5

# Bilingual initial prompt for Arabic-English content.
# Arabic text biases Whisper toward Arabic output for Arabic audio.
# Uses Egyptian dialect examples to improve accuracy for common content.
_ARABIC_INITIAL_PROMPT: str = (
    "هذا برنامج أو بودكاست بالعامية المصرية. "
    "يتحدث المتحدثون بشكل طبيعي ويستخدمون كلمات "
    "عامية مثل: مش، بقى، دلوقتي، كمان، بتاع، "
    "عشان، إزيك، عايز، بيقول، بيعمل، هيجي، أهو، يعني."
)


class WhisperProvider(TranscriptionProvider):
    """Transcription provider wrapping the faster-whisper library.

    Args:
        model_size: Whisper model variant (e.g. ``"large-v3"``).
        device: Torch device string (e.g. ``"cuda"`` or ``"cpu"``).
        compute_type: Quantisation mode passed to CTranslate2 (e.g. ``"float16"``).
    """

    def __init__(self, model_size: str, device: str, compute_type: str = _COMPUTE_TYPE) -> None:
        """Loads the Whisper model. Heavy GPU allocation happens here."""
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_path: Path, language: str) -> TranscriptResult:
        """Transcribes the audio file at *audio_path*.

        Args:
            audio_path: Path to the WAV/MP3 file to transcribe.
            language: BCP-47 language code (e.g. ``"ar"``, ``"en"``).
                      Pass an empty string to enable automatic detection.

        Returns:
            A fully populated :class:`TranscriptResult` dataclass.
        """
        # Single-pass transcription mimicking v2.1 behavior.
        # v2.1 passed language=None (auto-detect) + Arabic initial prompt in ONE call.
        # The Arabic prompt biases auto-detection toward Arabic for Arabic audio.
        whisper_lang = None if not language else language
        initial_prompt: str | None = None
        if whisper_lang is None or whisper_lang == "ar":
            initial_prompt = _ARABIC_INITIAL_PROMPT

        seg_iter, info = self.model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language=whisper_lang,
            initial_prompt=initial_prompt,
            temperature=0.0,
            condition_on_previous_text=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=_VAD_MIN_SILENCE_MS),
        )

        segments: list[TranscriptSegment] = []
        all_words: list[WordInfo] = []
        seg_id = 1

        for i, seg in enumerate(seg_iter):
            # Debug: print first 10 raw segments before filtering
            if i < 10:
                print(seg.text)

            seg_words: list[WordInfo] = []
            for w in seg.words or []:
                prob = getattr(w, "probability", 1.0)
                if prob < _MIN_WORD_PROBABILITY:
                    continue
                wd = WordInfo(
                    word=w.word.strip(),
                    start=round(w.start, 3),
                    end=round(w.end, 3),
                    probability=round(prob, 3),
                )
                seg_words.append(wd)
                all_words.append(wd)

            # Detect and skip hallucinated segments with excessive repetition
            if seg_words:
                if _is_hallucination(seg_words):
                    # Log warning but continue processing
                    import warnings
                    warnings.warn(
                        f"Skipped hallucinated segment at {seg.start:.1f}s-{seg.end:.1f}s "
                        f"(excessive repetition detected)"
                    )
                else:
                    segments.append(
                        TranscriptSegment(
                            id=seg_id,
                            text=seg.text.strip(),
                            start=round(seg.start, 3),
                            end=round(seg.end, 3),
                            words=seg_words,
                        )
                    )
                    seg_id += 1

        return TranscriptResult(
            segments=segments,
            words=all_words,
            language=info.language,
            duration=round(info.duration, 2),
        )

    def cleanup(self) -> None:
        """Releases GPU memory held by the Whisper model.

        Must be called after transcription is complete to free VRAM before
        subsequent GPU-intensive stages (e.g. face detection).
        """
        import torch  # noqa: PLC0415 — torch is optional; imported here to avoid

        # a hard dependency at module scope when CUDA is not available.
        del self.model
        torch.cuda.empty_cache()
        gc.collect()
