"""
ASS Subtitle Builder module.
"""

from dataclasses import dataclass
from pathlib import Path
from .base import SubtitleRenderer, WordTiming
from .text_cleaner import clean_for_subtitle, is_arabic_text
from ..config import PipelineConfig
from ..fonts import FontManager


@dataclass(frozen=True, slots=True)
class AssWord:
    """Internal representation of a subtitle word for formatting."""

    text: str
    start: float
    end: float


class ASSSubtitleRenderer(SubtitleRenderer):
    """Generates professional Advanced SubStation Alpha (.ass) subtitle files."""

    def __init__(self, font_manager: FontManager):
        self.font_manager = font_manager

    def _sec2ass(self, sec: float, offset: float = 0.0) -> str:
        """Convert seconds to ASS timestamp format (H:MM:SS.cs)."""
        t = max(0.0, sec - offset)
        cs = int(round(t * 100))
        h = cs // 360000
        m = (cs % 360000) // 6000
        s = (cs % 6000) // 100
        c = cs % 100
        return f"{h}:{m:02d}:{s:02d}.{c:02d}"

    def render(
        self,
        words: list[WordTiming],
        clip_start: float,
        clip_end: float,
        config: PipelineConfig,
        output_path: Path,
        title: str = "",
    ) -> Path:
        """
        Builds the ASS file content and writes it to disk.
        """
        tw = int(config.target_height * 9 / 16)
        if tw % 2 != 0:
            tw += 1
        th = config.target_height

        fs = max(26, int(th * 0.052))
        fs_hook = max(30, int(th * 0.058))
        outline = max(6, int(th * 0.0045))
        shadow = 3
        mv = int(th * 0.07)
        mv_hook = int(th * 0.04)
        # We will use the family name assuming it maps correctly.
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
            f"&H00FFFFFF,&H000000FF,&H00000000,&H99000000,"
            f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,20,20,{mv},1\n"
            f"Style: En,{font_en},{fs},"
            f"&H00FFFFFF,&H000000FF,&H00000000,&H99000000,"
            f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,20,20,{mv},1\n"
            f"Style: Hook,{font_ar},{fs_hook},"
            f"&H001ADFFF,&H000000FF,&H00000000,&HAA000000,"
            f"-1,0,0,0,100,100,0,0,1,{outline},{shadow},8,20,20,{mv_hook},1\n\n"
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
                    clip_ws.append(AssWord(text=txt, start=w.start, end=w.end))

        if not clip_ws:
            output_path.write_text(header + events, encoding="utf-8")
            return output_path

        lines, cur = [], [clip_ws[0]]
        for i in range(1, len(clip_ws)):
            gap = clip_ws[i].start - clip_ws[i - 1].end
            if len(cur) >= 3 or gap > 0.45:
                lines.append(cur)
                cur = []
            cur.append(clip_ws[i])
        if cur:
            lines.append(cur)

        for line in lines:
            n = len(line)
            line_text = " ".join(lw.text for lw in line)
            style = "Ar" if is_arabic_text(line_text) else "En"

            for i, word in enumerate(line):
                w_start = word.start
                w_end = line[i + 1].start if i < n - 1 else line[-1].end

                parts = []
                for j, lw in enumerate(line):
                    t = lw.text
                    if j == i:
                        parts.append(f"{{\\c&H0000FFFF&}}{t}{{\\c&HFFFFFF&}}")
                    else:
                        parts.append(t)

                display = " ".join(parts)
                ts = self._sec2ass(w_start, clip_start)
                te = self._sec2ass(w_end, clip_start)
                events += f"Dialogue: 0,{ts},{te},{style},,0,0,0,,{display}\n"

        output_path.write_text(header + events, encoding="utf-8")
        return output_path
