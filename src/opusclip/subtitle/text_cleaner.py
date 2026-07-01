"""
Text cleaning utilities for Arabic and English subtitles.
"""

import re
import unicodedata


# Arabic-Indic digits (٠-٩) and Eastern Arabic-Indic digits (۰-۹) map
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Worded numbers (English) pattern
_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12",
}
# Strip isolated punctuation tokens
_ISOLATED_PUNCT_RE = re.compile(r"\s+([،;:؟!.\-,?;!]+)\s+")
# Leading/trailing punctuation cleanup per token
_LEADING_TRAILING_PUNCT_RE = re.compile(r"^[^\w\d]+|[^\w\d]+$")

# BiDi markers
_RLM = "\u200F"  # Right-to-Left Mark
_LRM = "\u200E"  # Left-to-Right Mark

# Patterns for elements that must not be altered
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.]+@[\w.]+\.\w+", re.IGNORECASE)
_PERCENTAGE_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_CURRENCY_RE = re.compile(r"[€$£¥₹]\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*(?:€|د\.ك|د\.ع|جنيه|ل\.س|USD|EUR|GBP)")


def normalize_numbers(text: str) -> str:
    """Convert Arabic-Indic digits and worded numbers to ASCII digits (0-9)."""
    text = text.translate(_ARABIC_DIGITS)
    words = text.split()
    out = []
    for w in words:
        lower = w.lower().strip(",.!?;:")
        if lower in _NUMBER_WORDS:
            punct_before = w[: len(w) - len(w.lstrip(",.!?;:("))]
            punct_after = w[len(w.rstrip(",.!?;:)")):]
            out.append(f"{punct_before}{_NUMBER_WORDS[lower]}{punct_after}")
        else:
            out.append(w)
    return " ".join(out)


def clean_punctuation(text: str) -> str:
    """Clean isolated punctuation tokens and normalize spacing around punctuation."""
    text = _ISOLATED_PUNCT_RE.sub(r"\1 ", text)
    text = re.sub(r"\s+([،;:؟!.\-,?;!])", r"\1", text)
    text = re.sub(r"([،;:؟!.\-,?;!])\s+", r"\1 ", text)
    return text


def bidi_clean_text(text: str) -> str:
    """Insert Unicode BiDi markers to help renderers handle mixed text.

    For lines that are predominantly Arabic, ensures trailing Latin text
    (URLs, emails, numbers) is preceded by LRM for correct display.
    """
    if not text:
        return text
    if not is_arabic_text(text):
        return text
    result = []
    words = text.split()
    for i, w in enumerate(words):
        has_latin = bool(re.search(r"[a-zA-Z]", w))
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", w))
        if has_latin and not has_arabic:
            if i > 0 and re.search(r"[\u0600-\u06FF]", words[i - 1]):
                result.append(_LRM + w)
            elif i < len(words) - 1 and re.search(r"[\u0600-\u06FF]", words[i + 1]):
                result.append(w + _LRM)
            else:
                result.append(w)
        else:
            result.append(w)
    return " ".join(result)


def clean_for_subtitle(text: str) -> str:
    """
    Whitelist-based cleaning for subtitle rendering.
    Drops characters that are not explicitly Arabic or Latin to prevent
    'tofu' (hollow box) rendering issues in libass/Cairo.

    Also normalizes numbers, cleans punctuation, and applies BiDi hints.

    Args:
        text: Raw text from transcription or LLM.

    Returns:
        Cleaned text safe for subtitle rendering.
    """
    if not text:
        return ""
    text = normalize_numbers(text)
    text = unicodedata.normalize("NFC", text)
    result = []
    for ch in text:
        cp = ord(ch)
        keep = (
            0x0020 <= cp <= 0x007E  # ASCII printable (letters, digits, punct)
            or 0x00C0 <= cp <= 0x024F  # Latin Extended A/B (é, ü, etc.)
            or 0x0600 <= cp <= 0x06FF  # Arabic main block
            or 0x0750 <= cp <= 0x077F  # Arabic Supplement
            or 0x08A0 <= cp <= 0x08FF  # Arabic Extended-A
            or 0xFB50 <= cp <= 0xFDFF  # Arabic Presentation Forms-A
            or 0xFE70 <= cp <= 0xFEFF  # Arabic Presentation Forms-B
            or cp == 0x0640  # Arabic Tatweel (kashida ـ)
            or cp
            in (
                0x060C,  # Arabic comma ،
                0x061B,  # Arabic semicolon ؛
                0x061F,  # Arabic question mark ؟
                0x200C,  # ZWNJ (needed for correct Arabic rendering)
                0x200D,  # ZWJ  (needed for correct Arabic rendering)
                0x2019,  # Right single quote '
                0x201C,  # Left double quote "
                0x201D,  # Right double quote "
                0x2026,  # Ellipsis …
                0x2013,  # En dash –
                0x2014,  # Em dash —
                0x200E,  # LRM (Left-to-Right Mark)
                0x200F,  # RLM (Right-to-Left Mark)
            )
        )
        if keep:
            result.append(ch)
    text = "".join(result)
    text = clean_punctuation(text)
    text = bidi_clean_text(text)
    return " ".join(text.split())


def clean_transcript_for_llm(text: str) -> str:
    """Clean transcript text before sending to LLM for clip selection.

    Removes repetitions, extra spaces, unifies punctuation, removes
    long filler sequences, and merges broken sentences.
    """
    if not text:
        return ""
    text = normalize_numbers(text)
    text = unicodedata.normalize("NFC", text)
    # Remove repeated words (e.g. "I I I went" -> "I went")
    text = re.sub(r"\b(\w+)\s+\1\b", r"\1", text)
    text = re.sub(r"\b(\w+)\s+\1\s+\1\b", r"\1", text)
    # Remove long filler sequences
    text = re.sub(r"\b(?:uh|um|er|ah|eh|like|you know)\s*", "", text, flags=re.IGNORECASE)
    # Remove repeated fillers
    text = re.sub(r"\b(?:uh|um|er|ah|eh)\b", "", text, flags=re.IGNORECASE)
    # Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()
    # Clean punctuation
    text = clean_punctuation(text)
    return text


def is_arabic_text(text: str) -> bool:
    """Detect if the text is predominantly Arabic.

    Checks if more than 30% of the characters are in the Arabic Unicode block.
    """
    if not text:
        return False
    return len(re.findall(r"[\u0600-\u06FF]", text)) > len(text) * 0.3
