from opusclip.transcription.base import TranscriptResult, TranscriptSegment, WordInfo
from opusclip.transcription.word_repair import fill_missing_words


def _make_seg(id: int, text: str, start: float, end: float, words: list[WordInfo]) -> TranscriptSegment:
    return TranscriptSegment(id=id, text=text, start=start, end=end, words=words)


class TestFillMissingWordsSuccess:
    def test_all_words_timestamped_no_change(self):
        seg = _make_seg(1, "Hello world", 0.0, 2.0, [
            WordInfo(word="Hello", start=0.0, end=0.5, probability=0.9),
            WordInfo(word="world", start=0.6, end=1.0, probability=0.85),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=2.0)
        result = fill_missing_words(transcript)
        assert len(result) == 2
        assert result[0].word == "Hello"

    def test_fills_missing_first_word(self):
        seg = _make_seg(1, "Hello world", 0.0, 2.0, [
            WordInfo(word="world", start=0.5, end=1.0, probability=0.85),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=2.0)
        result = fill_missing_words(transcript)
        assert len(result) == 2
        assert result[0].word == "Hello"
        assert result[0].start < result[1].start
        assert result[0].probability == 0.60

    def test_fills_multiple_missing_words(self):
        seg = _make_seg(1, "the quick brown fox", 0.0, 4.0, [
            WordInfo(word="fox", start=0.9, end=1.2, probability=0.85),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=4.0)
        result = fill_missing_words(transcript)
        assert len(result) == 4
        assert result[0].word == "the"
        assert result[1].word == "quick"
        assert result[2].word == "brown"
        assert result[3].word == "fox"

    def test_interpolation_timestamps_increase(self):
        seg = _make_seg(1, "a b c d", 0.0, 4.0, [
            WordInfo(word="d", start=0.9, end=1.2, probability=0.85),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=4.0)
        result = fill_missing_words(transcript)
        for i in range(len(result) - 1):
            assert result[i].start < result[i + 1].start

    def test_multiple_segments(self):
        segs = [
            _make_seg(1, "Hello world", 0.0, 2.0, [
                WordInfo(word="world", start=0.5, end=1.0, probability=0.85),
            ]),
            _make_seg(2, "Goodbye moon", 3.0, 5.0, [
                WordInfo(word="moon", start=3.5, end=4.0, probability=0.9),
            ]),
        ]
        transcript = TranscriptResult(segments=segs, words=[], language="en", duration=5.0)
        result = fill_missing_words(transcript)
        assert len(result) == 4

    def test_segment_with_no_timestamped_words(self):
        seg = _make_seg(1, "Hello world", 0.0, 2.0, [])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=2.0)
        result = fill_missing_words(transcript)
        assert len(result) == 2

    def test_empty_segment_text_skipped(self):
        seg = _make_seg(1, "", 0.0, 2.0, [])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=2.0)
        result = fill_missing_words(transcript)
        assert len(result) == 0

    def test_no_segments_returns_empty(self):
        transcript = TranscriptResult(segments=[], words=[], language="en", duration=0.0)
        result = fill_missing_words(transcript)
        assert result == []


class TestFillMissingWordsEdgeCases:
    def test_gap_too_small_skips_interpolation(self):
        seg = _make_seg(1, "a b", 0.0, 0.04, [
            WordInfo(word="b", start=0.03, end=0.04, probability=0.85),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=0.04)
        result = fill_missing_words(transcript)
        assert len(result) == 1
        assert result[0].word == "b"

    def test_words_already_covered_uses_existing(self):
        seg = _make_seg(1, "a b c", 0.0, 3.0, [
            WordInfo(word="a", start=0.0, end=0.3, probability=0.9),
            WordInfo(word="b", start=0.4, end=0.7, probability=0.85),
            WordInfo(word="c", start=0.8, end=1.2, probability=0.88),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=3.0)
        result = fill_missing_words(transcript)
        assert len(result) == 3
        for w in result:
            assert w.probability > 0.6

    def test_does_not_duplicate_existing_words(self):
        seg = _make_seg(1, "the the the", 0.0, 3.0, [
            WordInfo(word="the", start=0.0, end=0.3, probability=0.9),
            WordInfo(word="the", start=0.8, end=1.2, probability=0.88),
        ])
        transcript = TranscriptResult(segments=[seg], words=[], language="en", duration=3.0)
        result = fill_missing_words(transcript)
        assert len(result) == 2