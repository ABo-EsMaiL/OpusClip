"""
Text cleaning
"""

from opusclip.subtitle.text_cleaner import clean_for_subtitle, is_arabic_text


class TestCleanForSubtitleSuccess:
    def test_english_text_preserved(self):
        assert clean_for_subtitle("Hello world") == "Hello world"

    def test_arabic_text_preserved(self):
        assert clean_for_subtitle("مرحبا بالعالم") == "مرحبا بالعالم"

    def test_bilingual_text(self):
        result = clean_for_subtitle("Hello مرحبا world بالعالم")
        assert "Hello" in result
        assert "مرحبا" in result

    def test_punctuation_preserved(self):
        result = clean_for_subtitle("Hello, world! How are you?")
        assert result == "Hello, world! How are you?"

    def test_arabic_punctuation_preserved(self):
        result = clean_for_subtitle("مرحبا، كيف حالك؟")
        assert "،" in result
        assert "؟" in result

    def test_quotes_preserved(self):
        result = clean_for_subtitle('He said "hello"')
        assert '"' in result

    def test_ellipsis_preserved(self):
        result = clean_for_subtitle("waiting...")
        assert "..." in result

    def test_dashes_preserved(self):
        result = clean_for_subtitle("well-known – example — indeed")
        assert "–" in result or "-" in result

    def test_whitespace_collapsed(self):
        result = clean_for_subtitle("hello    world")
        assert result == "hello world"

    def test_empty_string(self):
        assert clean_for_subtitle("") == ""

    def test_nfc_normalized(self):
        composed = "\u00e9"
        decomposed = "\u0065\u0301"
        assert clean_for_subtitle(decomposed) == composed


class TestCleanForSubtitleFiltering:
    def test_emoji_removed(self):
        result = clean_for_subtitle("Hello 😊 world")
        assert result == "Hello world"

    def test_arrows_removed(self):
        result = clean_for_subtitle("hello ← world")
        assert result == "hello world"

    def test_mathematical_symbols_removed(self):
        result = clean_for_subtitle("hello ± world")
        assert result == "hello world"

    def test_box_drawing_removed(self):
        result = clean_for_subtitle("hello ─ world")
        assert result == "hello world"

    def test_control_chars_removed(self):
        result = clean_for_subtitle("hello\x00world\x01")
        assert result == "helloworld"

    def test_only_emoji_returns_blank(self):
        result = clean_for_subtitle("😊😊😊")
        assert result == ""


class TestIsArabicText:
    def test_arabic_text_returns_true(self):
        assert is_arabic_text("مرحبا بالعالم")

    def test_english_text_returns_false(self):
        assert not is_arabic_text("Hello world")

    def test_bilingual_arabic_majority(self):
        assert is_arabic_text("مرحبا بالعالم Hello")

    def test_english_majority_returns_false(self):
        assert not is_arabic_text("Hello world and مرحبا")

    def test_empty_string_returns_false(self):
        assert not is_arabic_text("")

    def test_numbers_only_returns_false(self):
        assert not is_arabic_text("12345")