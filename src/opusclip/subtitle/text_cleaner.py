"""
Text cleaning utilities for Arabic and English subtitles.
"""

import unicodedata


def clean_for_subtitle(text: str) -> str:
    """
    Whitelist-based cleaning for subtitle rendering.
    Drops characters that are not explicitly Arabic or Latin to prevent
    'tofu' (hollow box) rendering issues in libass/Cairo.

    Args:
        text: Raw text from transcription or LLM.

    Returns:
        Cleaned text safe for subtitle rendering.
    """
    if not text:
        return ""
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
            )
        )
        if keep:
            result.append(ch)
    # Collapse multiple spaces into one
    return " ".join("".join(result).split())


def is_arabic_text(text: str) -> bool:
    """Detect if the text is predominantly Arabic.

    Checks if more than 30% of the characters are in the Arabic Unicode block.
    """
    import re

    if not text:
        return False
    return len(re.findall(r"[\u0600-\u06FF]", text)) > len(text) * 0.3
