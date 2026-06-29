import pytest

from opusclip.fonts import FontManager
from opusclip.exceptions import ConfigurationError


class TestFontManagerSuccess:
    def test_custom_fonts_dir_resolves_font(self, tmp_path):
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "TestFont.ttf").write_bytes(b"\x00" * 100)
        fm = FontManager(fonts_dir)
        result = fm.get_font_path("TestFont.ttf")
        assert result.exists()
        assert result.name == "TestFont.ttf"

    def test_multiple_fonts_resolvable(self, tmp_path):
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "FontA.ttf").write_bytes(b"\x00" * 100)
        (fonts_dir / "FontB.ttf").write_bytes(b"\x00" * 100)
        fm = FontManager(fonts_dir)
        assert fm.get_font_path("FontA.ttf").exists()
        assert fm.get_font_path("FontB.ttf").exists()

    def test_fonts_dir_defaults_to_project_fonts(self, tmp_path):
        fm = FontManager(tmp_path)
        assert fm.fonts_dir == tmp_path


class TestFontManagerFailure:
    def test_missing_font_raises_configuration_error(self, tmp_path):
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        fm = FontManager(fonts_dir)
        with pytest.raises(ConfigurationError, match="Font not found"):
            fm.get_font_path("Nonexistent.ttf")

    def test_empty_fonts_dir_raises_error(self, tmp_path):
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        fm = FontManager(fonts_dir)
        with pytest.raises(ConfigurationError):
            fm.get_font_path("Missing.ttf")