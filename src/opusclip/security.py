"""API key loader — reads OPUSCLIP_API_KEY from the environment securely."""

import os
from .exceptions import ConfigurationError


def load_api_key() -> str:
    """
    Loads the API key from the environment.
    Raises ConfigurationError if not found or empty.
    """
    api_key = os.getenv("OPUSCLIP_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError("OPUSCLIP_API_KEY environment variable is missing or empty.")
    return api_key
