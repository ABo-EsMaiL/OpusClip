"""
Whisper-based transcription provider.

Implements TranscriptionProvider using the faster-whisper library.
"""

import gc
from pathlib import Path

from faster_whisper import WhisperModel

from .base import TranscriptionProvider, TranscriptResult, TranscriptSegment, WordInfo

# Minimum word probability accepted from Whisper output. Words below this
# threshold are typically hallucinations or low-confidence tokens.
_MIN_WORD_PROBABILITY: float = 0.55

# Default quantisation mode passed to CTranslate2 for the Whisper model.
# Using float16 significantly reduces VRAM usage with negligible accuracy loss.
_COMPUTE_TYPE: str = "float16"

# Minimum silence duration in milliseconds required for VAD to segment audio.
_VAD_MIN_SILENCE_MS: int = 400

# Bilingual initial prompt for Arabic-English content.
# Instructs Whisper to keep English words in English and Arabic in Arabic,
# never transliterating between the two.
_ARABIC_INITIAL_PROMPT: str = (
    "This is a bilingual Arabic and English podcast or program. "
    "The speakers mix Arabic and English naturally. "
    "IMPORTANT: Keep English words in English. Keep Arabic words in Arabic. "
    "Never transliterate English into Arabic. "
    "Preserve proper nouns, company names, product names, people's names, "
    "URLs, and technical terms exactly as spoken. "
    "Examples: 'Python', 'OpenAI', 'ChatGPT', 'How are you', 'Google', 'Apple' "
    "must remain in English, not Arabic transliteration. "
    "Normalize all numbers to digits (0-9). "
    "Use clean punctuation. Remove repeated filler words when obvious."
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
        initial_prompt: str | None = None
        if language == "ar" or not language:
            initial_prompt = _ARABIC_INITIAL_PROMPT

        seg_iter, info = self.model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language=language if language else None,
            initial_prompt=initial_prompt,
            temperature=0.0,
            condition_on_previous_text=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=_VAD_MIN_SILENCE_MS),
        )

        segments: list[TranscriptSegment] = []
        all_words: list[WordInfo] = []
        seg_id = 1

        for seg in seg_iter:
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

            if seg_words:
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
