"""
JSON extraction utilities for parsing LLM responses.

LLM APIs frequently wrap JSON output in markdown code fences or add
surrounding prose. This module provides safe parsers that strip those
wrappers before decoding.
"""

import json
import re
from typing import Any

# Type alias for the heterogeneous JSON dictionaries returned by LLM responses.
# Using ``Any`` here is intentional: LLM output is inherently untyped at parse
# time. Callers are responsible for field-level validation after extraction.
JsonObject = dict[str, Any]
JsonArray = list[JsonObject]


def extract_json_array(text: str) -> JsonArray | None:
    """Extract a JSON array from a (possibly markdown-wrapped) string.

    Attempts two strategies in order:
    1. Strip markdown fences, then find the first ``[…]`` block and parse it.
    2. Parse the stripped string directly as JSON.

    Args:
        text: Raw string from an LLM response.

    Returns:
        A list of dicts if parsing succeeds, or ``None`` if no valid JSON
        array can be extracted.
    """
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if m:
        try:
            result = json.loads(m.group())
            if isinstance(result, list):
                return result  # type: ignore[return-value]
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result  # type: ignore[return-value]
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def extract_json_object(text: str) -> JsonObject | None:
    """Extract a JSON object from a (possibly markdown-wrapped) string.

    Args:
        text: Raw string from an LLM response.

    Returns:
        A dict if parsing succeeds, or ``None`` if no valid JSON object
        can be extracted.
    """
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result  # type: ignore[return-value]
    except (json.JSONDecodeError, ValueError):
        pass
    return None
