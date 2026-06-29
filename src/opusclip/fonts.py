"""Font resolution — resolves bundled TTF font paths for subtitle rendering."""

from pathlib import Path
from .exceptions import ConfigurationError


class FontManager:
    """Manages resolving bundled font paths securely."""

    def __init__(self, fonts_dir: Path | None = None) -> None:
        if fonts_dir is None:
            # Resolve relative to the project root: src/opusclip/fonts.py -> root/fonts/
            self.fonts_dir = Path(__file__).resolve().parent.parent.parent / "fonts"
        else:
            self.fonts_dir = fonts_dir

    def get_font_path(self, name: str) -> Path:
        """
        Returns the absolute path to a bundled font by its filename.
        Raises ConfigurationError if the font does not exist.
        """
        font_path = self.fonts_dir / name
        if not font_path.exists():
            raise ConfigurationError(
                f"Font not found: {font_path}. Ensure fonts are placed in the fonts/ directory per the zero-download policy."
            )
        return font_path
