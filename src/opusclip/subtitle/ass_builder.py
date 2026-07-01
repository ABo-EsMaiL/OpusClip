"""
ASS Subtitle Builder module.
"""

from dataclasses import dataclass
from pathlib import Path
from .base import SubtitleRenderer, WordTiming
from .text_cleaner import clean_for_subtitle, is_arabic_text
from ..config import PipelineConfig
from ..fonts import FontManager

_NUMBER_COLOR = "&H00FF6600"
_DEFAULT_COLOR = "&H00FFFFFF"
_CURRENT_COLOR = "&H0000FFFF"
_ARABIC_RTL = "\\rtl1"

# Max pixel width for subtitle text (80% of play width)
_MAX_TEXT_WIDTH_RATIO: float = 0.80


@dataclass(frozen=True, slots=True)
class AssWord:
    text: str
    start: float
    end: float
    has_number: bool = False


def _contains_number(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


class ASSSubtitleRenderer(SubtitleRenderer):
    """Generates professional Advanced SubStation Alpha (.ass) subtitle files."""

    def __init__(self, font_manager: FontManager):
        self.font_manager = font_manager

    def _sec2ass(self, sec: float, offset: float = 0.0) -> str:
        t = max(0.0, sec - offset)
        cs = int(round(t * 100))
        h = cs // 360000
        m = (cs % 360000) // 6000
        s = (cs % 6000) // 100
        c = cs % 100
        return f"{h}:{m:02d}:{s:02d}.{c:02d}"

    def _estimate_text_width(self, text: str, font_size: int) -> float:
        avg_char_width = font_size * 0.55
        return len(text) * avg_char_width

    def render(
        self,
        words: list[WordTiming],
        clip_start: float,
        clip_end: float,
        config: PipelineConfig,
        output_path: Path,
        title: str = "",
    ) -> Path:
        tw = int(config.target_height * 9 / 16)
        if tw % 2 != 0:
            tw += 1
        th = config.target_height

        max_text_px = tw * _MAX_TEXT_WIDTH_RATIO

        fs = max(20, int(th * 0.042))
        fs_hook = max(24, int(th * 0.048))
        outline = max(3, int(th * 0.0025))
        shadow = 2
        mv = int(th * 0.085)
        mv_hook = int(th * 0.045)
        spacing = -0.3
        font_ar = "Amiri"
        font_en = "Montserrat"

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            f"PlayResX: {tw}\nPlayResY: {th}\n"
            "YCbCr Matrix: TV.601\n\n"
            "[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Ar,{font_ar},{fs},"
            f"&H00FFFFFF,&H000000FF,&H00333333,&H66000000,"
            f"-1,0,0,0,100,100,{spacing:.1f},0,1,{outline},{shadow},2,20,20,{mv},1\n"
            f"Style: En,{font_en},{fs},"
            f"&H00FFFFFF,&H000000FF,&H00333333,&H66000000,"
            f"-1,0,0,0,100,100,{spacing:.1f},0,1,{outline},{shadow},2,20,20,{mv},1\n"
            f"Style: Hook,{font_ar},{fs_hook},"
            f"&H001ADFFF,&H000000FF,&H00333333,&H88000000,"
            f"-1,0,0,0,100,100,{spacing:.1f},0,1,{outline},{shadow},8,20,20,{mv_hook},1\n\n"
            "[Events]\n"
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        )

        events = ""
        clean_t = clean_for_subtitle(title)
        if clean_t:
            events += (
                f"Dialogue: 0,{self._sec2ass(clip_start, clip_start)},"
                f"{self._sec2ass(clip_start + 3, clip_start)},Hook,,0,0,0,,{clean_t}\n"
            )

        clip_ws: list[AssWord] = []
        for w in words:
            mid = (w.start + w.end) / 2.0
            if clip_start <= mid <= clip_end:
                txt = clean_for_subtitle(w.word.strip())
                if txt:
                    clip_ws.append(AssWord(
                        text=txt, start=w.start, end=w.end,
                        has_number=_contains_number(txt),
                    ))

        if not clip_ws:
            output_path.write_text(header + events, encoding="utf-8")
            return output_path

        # Adaptive grouping: split lines based on pixel width, not just word count
        lines, cur = [], [clip_ws[0]]
        for i in range(1, len(clip_ws)):
            gap = clip_ws[i].start - clip_ws[i - 1].end
            candidate = " ".join(w.text for w in cur) + " " + clip_ws[i].text
            est_w = self._estimate_text_width(candidate, fs)
            if est_w > max_text_px or gap > 0.5:
                lines.append(cur)
                cur = []
            cur.append(clip_ws[i])
        if cur:
            lines.append(cur)

        for line in lines:
            n = len(line)
            line_text = " ".join(lw.text for lw in line)
            style = "Ar" if is_arabic_text(line_text) else "En"

            rtl_tag = _ARABIC_RTL if style == "Ar" else ""

            for i, word in enumerate(line):
                w_start = word.start
                w_end = line[i + 1].start if i < n - 1 else line[-1].end

                parts = []
                for j, lw in enumerate(line):
                    t = lw.text
                    if j == i:
                        if lw.has_number:
                            parts.append("{\\c" + _NUMBER_COLOR + "}" + t + "{\\c" + _DEFAULT_COLOR + "}")
                        else:
                            parts.append("{\\c" + _CURRENT_COLOR + "}" + t + "{\\c" + _DEFAULT_COLOR + "}")
                    else:
                        if lw.has_number:
                            parts.append("{\\c" + _NUMBER_COLOR + "}" + t + "{\\c" + _DEFAULT_COLOR + "}")
                        else:
                            parts.append(t)

                display = " ".join(parts)
                if rtl_tag:
                    display = f"{rtl_tag}{display}"
                ts = self._sec2ass(w_start, clip_start)
                te = self._sec2ass(w_end, clip_start)
                events += f"Dialogue: 0,{ts},{te},{style},,0,0,0,,{display}\n"

        output_path.write_text(header + events, encoding="utf-8")
        return output_path
