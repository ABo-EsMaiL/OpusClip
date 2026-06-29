import pytest

from opusclip.subtitle.ass_builder import ASSSubtitleRenderer
from opusclip.subtitle.base import WordTiming
from opusclip.config import PipelineConfig
from opusclip.fonts import FontManager


@pytest.fixture
def ass_renderer(tmp_path) -> ASSSubtitleRenderer:
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    (fonts_dir / "Tajawal-Regular.ttf").write_bytes(b"\x00" * 100)
    (fonts_dir / "Montserrat-Regular.ttf").write_bytes(b"\x00" * 100)
    fm = FontManager(fonts_dir)
    return ASSSubtitleRenderer(fm)


@pytest.fixture
def config(tmp_path) -> PipelineConfig:
    cfg = PipelineConfig(output_dir=tmp_path)
    cfg.target_height = 1920
    return cfg


class TestAssRendererOutputStructure:
    def test_renders_ass_file(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        result = ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        assert result == out
        assert out.exists()

    def test_contains_script_info(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "[Script Info]" in content

    def test_contains_styles(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "[V4+ Styles]" in content
        assert "Style: Ar" in content
        assert "Style: En" in content
        assert "Style: Hook" in content

    def test_contains_events(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "[Events]" in content
        assert "Dialogue:" in content


class TestAssRendererEnglish:
    def test_renders_english_word(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "Hello" in content

    def test_uses_en_style_for_english(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert ",En," in content


class TestAssRendererArabic:
    def test_renders_arabic_word(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="مرحبا", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "مرحبا" in content

    def test_uses_ar_style_for_arabic(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="مرحبا", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert ",Ar," in content


class TestAssRendererBilingual:
    def test_renders_bilingual_text(self, ass_renderer, config, tmp_path):
        words = [
            WordTiming(word="Hello", start=0.0, end=0.5),
            WordTiming(word="مرحبا", start=0.6, end=1.0),
        ]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "Hello" in content
        assert "مرحبا" in content


class TestAssRendererEdgeCases:
    def test_empty_words_list(self, ass_renderer, config, tmp_path):
        out = tmp_path / "test.ass"
        ass_renderer.render([], clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Dialogue:" not in content

    def test_words_outside_clip_window_excluded(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=10.0, end=10.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "Hello" not in content

    def test_words_on_clip_boundary_included(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=4.5, end=4.8)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert "Hello" in content

    def test_timestamps_formatted_correctly(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out)
        content = out.read_text(encoding="utf-8")
        assert ",0:00:00.00," in content or ",0:00:00.50," in content

    def test_title_rendered_as_hook(self, ass_renderer, config, tmp_path):
        words = [WordTiming(word="Hello", start=0.0, end=0.5)]
        out = tmp_path / "test.ass"
        ass_renderer.render(words, clip_start=0.0, clip_end=5.0, config=config, output_path=out, title="Title Card")
        content = out.read_text(encoding="utf-8")
        assert "Title Card" in content
        assert ",Hook," in content