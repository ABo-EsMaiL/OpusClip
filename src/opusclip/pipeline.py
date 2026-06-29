"""Pipeline orchestrator — runs the 10-step video-to-clips pipeline."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .cache import CacheManager
from .config import PipelineConfig
from .context import PipelineContext
from .input.base import InputProvider, VideoMetadata
from .transcription.base import TranscriptionProvider, WordInfo
from .clip_selection.base import ClipSelector, ClipCandidate
from .face_detection.base import FaceDetector
from .subtitle.base import SubtitleRenderer, WordTiming
from .subtitle.text_cleaner import clean_for_subtitle
from .rendering.base import VideoRenderer
from .rendering.validator import validate_rendered_video
from .metadata.base import MetadataGenerator, ClipMetadata
from .metrics import PipelineMetrics
from .exceptions import (
    OpusClipError,
    InputValidationError,
    TranscriptionError,
    RenderingError,
    MetadataError,
)


_TARGET_WIDTH = 1080
_TARGET_HEIGHT = 1920


try:
    from tqdm import tqdm as _tqdm
    _TQDM_AVAILABLE = True
except ImportError:
    _TQDM_AVAILABLE = False


@dataclass
class PipelineResult:
    """Structured output from a single pipeline run.

    Attributes:
        clips: List of per-clip results.
        output_dir: Root output directory for this run.
        duration: Source video duration in seconds.
        total_clips: Number of clips attempted.
        successful_clips: Number of clips rendered successfully.
        failed_clips: Number of clips that failed.
        source: Original input source string.
        error: Top-level error message if the pipeline aborted.
    """
    clips: List["ClipResult"] = field(default_factory=list)
    output_dir: Optional[Path] = None
    duration: float = 0.0
    total_clips: int = 0
    successful_clips: int = 0
    failed_clips: int = 0
    source: str = ""
    error: Optional[str] = None


@dataclass
class ClipResult:
    """Result of rendering a single clip.

    Attributes:
        number: 1-based index within the output clip list.
        video_path: Path to the rendered video file.
        thumbnail_path: Path to the thumbnail image.
        metadata: Generated social-media metadata, if available.
        success: Whether this clip was rendered successfully.
        error: Error message if rendering failed.
    """
    number: int
    video_path: Path
    thumbnail_path: Path
    metadata: Optional[ClipMetadata] = None
    success: bool = True
    error: Optional[str] = None


_STEPS = [
    "Validating input",
    "Reading video metadata",
    "Transcribing audio",
    "Repairing transcript",
    "Selecting clips",
    "Rendering subtitles",
    "Rendering videos",
    "Validating rendered outputs",
    "Generating metadata",
    "Producing final outputs",
]


def _progress(current: int, total: int, message: str) -> None:
    print(f"[{current}/{total}] {message}...")


def _sanitize_source_name(source: str) -> str:
    import hashlib
    import re
    from urllib.parse import urlparse
    parsed = urlparse(source)
    h = hashlib.sha256(source.encode()).hexdigest()[:6]
    if parsed.scheme in ("http", "https"):
        base = "url"
    else:
        base = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(source).stem) or "file"
    return f"{base}_{h}"


class Pipeline:
    """Orchestrates the full video-to-clips pipeline.

    Accepts all providers via constructor injection (dependency injection).
    Runs a 10-step pipeline: validate → read metadata → transcribe → repair
    → select clips → render subtitles → render videos → validate → generate
    metadata → produce outputs.

    Supports single runs, batch processing via ``run_batch()``, and
    step-level resume via ``CacheManager``.
    """

    def __init__(
        self,
        config: PipelineConfig,
        input_provider: InputProvider,
        transcription_provider: TranscriptionProvider,
        clip_selector: ClipSelector,
        face_detector: FaceDetector,
        subtitle_renderer: SubtitleRenderer,
        video_renderer: VideoRenderer,
        metadata_generator: MetadataGenerator,
    ) -> None:
        self.config = config
        self.input_provider = input_provider
        self.transcription_provider = transcription_provider
        self.clip_selector = clip_selector
        self.face_detector = face_detector
        self.subtitle_renderer = subtitle_renderer
        self.video_renderer = video_renderer
        self.metadata_generator = metadata_generator
        self.metrics: PipelineMetrics = PipelineMetrics()
        self._source: str = ""
        self._ctx: Optional[PipelineContext] = None

    def run(self, source: str, resume: bool = False,
            output_dir: Optional[Path] = None) -> PipelineResult:
        self._source = source
        out = output_dir or self.config.output_dir
        self._ctx = PipelineContext(
            target_width=_TARGET_WIDTH,
            target_height=_TARGET_HEIGHT,
            output_dir=out,
            metadata_output_dir=out / "metadata",
        )
        self._ctx.output_dir.mkdir(parents=True, exist_ok=True)
        self._ctx.metadata_output_dir.mkdir(parents=True, exist_ok=True)

        result = PipelineResult(output_dir=out, source=source)
        self.metrics = PipelineMetrics()
        self.metrics.start()
        cache = CacheManager(out, source) if resume else None

        steps: list[tuple[int, str, Callable[[], None]]] = [
            (1, "validate_input", lambda: self._step_1_validate_input(source)),
            (2, "read_metadata", self._step_2_read_metadata),
            (3, "transcribe_audio", self._step_3_transcribe_audio),
            (4, "repair_transcript", self._step_4_repair_transcript),
            (5, "select_clips", self._step_5_select_clips),
            (6, "render_subtitles", self._step_6_render_subtitles),
            (7, "render_videos", lambda: self._step_7_render_videos(result)),
            (8, "validate_rendered", lambda: self._step_8_validate_rendered(result)),
            (9, "generate_metadata", lambda: self._step_9_generate_metadata(result)),
            (10, "produce_final", lambda: self._step_10_produce_final(result)),
        ]

        try:
            for step_num, stage_name, step_fn in steps:
                if cache and cache.is_step_completed(step_num):
                    _progress(step_num, len(_STEPS), f"{_STEPS[step_num - 1]} (cached)")
                    continue
                with self.metrics.measure_stage(stage_name):
                    step_fn()
                if cache:
                    cache.mark_step_completed(step_num)
        except OpusClipError:
            raise
        except Exception as exc:
            raise OpusClipError(f"Pipeline failed at an unexpected point: {exc}") from exc
        finally:
            self.metrics.finish()
            self.metrics.failures = result.failed_clips
            # TODO: Wire metrics.api_calls / api_retries into LLM providers
            # for accurate retry and API usage tracking during pipeline execution.
            print(self.metrics.report())

        return result

    def run_batch(self, sources: list[str], resume: bool = False) -> list[PipelineResult]:
        results: list[PipelineResult] = []
        for source in sources:
            sub_dir = self.config.output_dir / _sanitize_source_name(source)
            try:
                result = self.run(source, resume=resume, output_dir=sub_dir)
                results.append(result)
            except OpusClipError as exc:
                results.append(PipelineResult(
                    output_dir=sub_dir, source=source,
                    error=str(exc),
                ))
        return results

    # ------------------------------------------------------------------
    # Step 1: Validate input
    # ------------------------------------------------------------------
    def _step_1_validate_input(self, source: str) -> None:
        _progress(1, len(_STEPS), _STEPS[0])
        import urllib.parse
        parsed = urllib.parse.urlparse(source)
        if parsed.scheme in ("http", "https"):
            from .input_validator import validate_youtube_url
            try:
                validate_youtube_url(source)
            except InputValidationError:
                pass
        else:
            from .input_validator import validate_video_path
            validate_video_path(source)

    # ------------------------------------------------------------------
    # Step 2: Read metadata
    # ------------------------------------------------------------------
    def _step_2_read_metadata(self) -> None:
        _progress(2, len(_STEPS), _STEPS[1])
        meta: VideoMetadata = self.input_provider.acquire(
            source=self._source,
            output_dir=self._ctx.output_dir,
        )
        self._ctx.video_path = meta.path
        self._ctx.video_width = meta.width
        self._ctx.video_height = meta.height
        self._ctx.video_fps = meta.fps
        self._ctx.duration = meta.duration
        aspect = meta.width / meta.height
        self._ctx.src_crop_w = int(meta.height * (_TARGET_WIDTH / _TARGET_HEIGHT) / aspect)
        if self._ctx.src_crop_w % 2:
            self._ctx.src_crop_w += 1
        if self._ctx.src_crop_w > meta.width or self._ctx.src_crop_w == 0:
            self._ctx.src_crop_w = meta.width

    # ------------------------------------------------------------------
    # Step 3: Transcribe audio
    # ------------------------------------------------------------------
    def _step_3_transcribe_audio(self) -> None:
        _progress(3, len(_STEPS), _STEPS[2])
        video = self._ctx.video_path
        if video is None:
            raise TranscriptionError("No video path available for transcription.")
        audio_path = self._ctx.output_dir / "audio.wav"
        from .subprocess_utils import run_ffmpeg
        run_ffmpeg([
            "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(audio_path),
        ])
        try:
            lang = self._detect_language_from_path(video)
            result_obj = self.transcription_provider.transcribe(audio_path, lang)
            self._ctx.transcript_data = {
                "segments": [(s.id, s.text, s.start, s.end) for s in result_obj.segments],
                "words": [(w.word, w.start, w.end, w.probability) for w in result_obj.words],
                "language": result_obj.language,
                "duration": result_obj.duration,
            }
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _detect_language_from_path(video_path: Path) -> str:
        import re
        name = video_path.stem.lower()
        if re.search(r"arab|عربي|بودكاست|مصر|سعود", name):
            return "ar"
        return ""

    # ------------------------------------------------------------------
    # Step 4: Repair transcript
    # ------------------------------------------------------------------
    def _step_4_repair_transcript(self) -> None:
        _progress(4, len(_STEPS), _STEPS[3])
        from .transcription.base import TranscriptResult, TranscriptSegment
        raw = self._ctx.transcript_data
        segments = [
            TranscriptSegment(id=sid, text=stxt, start=sstart, end=send, words=[])
            for sid, stxt, sstart, send in raw.get("segments", [])
        ]
        all_words = [
            WordInfo(word=wword, start=wstart, end=wend, probability=wprob)
            for wword, wstart, wend, wprob in raw.get("words", [])
        ]
        if not all_words:
            return
        result_obj = TranscriptResult(
            segments=segments,
            words=all_words,
            language=raw.get("language", ""),
            duration=raw.get("duration", 0.0),
        )
        from .transcription.word_repair import fill_missing_words
        repaired = fill_missing_words(result_obj)
        self._ctx.transcript_data["repaired_words"] = [
            (w.word, w.start, w.end, w.probability) for w in repaired
        ]

    # ------------------------------------------------------------------
    # Step 5: Select clips
    # ------------------------------------------------------------------
    def _step_5_select_clips(self) -> None:
        _progress(5, len(_STEPS), _STEPS[4])
        from .transcription.base import TranscriptResult, TranscriptSegment
        raw = self._ctx.transcript_data
        segments = [
            TranscriptSegment(id=sid, text=stxt, start=sstart, end=send, words=[])
            for sid, stxt, sstart, send in raw.get("segments", [])
        ]
        all_words = [
            WordInfo(word=wword, start=wstart, end=wend, probability=wprob)
            for wword, wstart, wend, wprob in raw.get("words", [])
        ]
        result_obj = TranscriptResult(
            segments=segments,
            words=all_words,
            language=raw.get("language", ""),
            duration=raw.get("duration", 0.0),
        )
        candidates = self.clip_selector.select_clips(result_obj, self.config)
        for i, c in enumerate(candidates):
            c.clip_number = i + 1
        self._ctx.selected_clips = [
            {
                "number": i + 1,
                "start": c.start,
                "end": c.end,
                "score": c.score,
                "title": c.title,
                "summary": c.summary,
            }
            for i, c in enumerate(candidates)
        ]

    # ------------------------------------------------------------------
    # Step 6: Render subtitles
    # ------------------------------------------------------------------
    def _step_6_render_subtitles(self) -> None:
        _progress(6, len(_STEPS), _STEPS[5])
        subs_dir = self._ctx.output_dir / "subtitles"
        subs_dir.mkdir(exist_ok=True)
        repaired = self._ctx.transcript_data.get("repaired_words", [])
        if not repaired:
            raw_words = self._ctx.transcript_data.get("words", [])
            if raw_words:
                repaired = raw_words
        if not repaired:
            return
        words_timing = [
            WordTiming(word=clean_for_subtitle(w[0]), start=float(w[1]), end=float(w[2]))
            for w in repaired
        ]
        subtitle_paths = []
        for clip_info in self._ctx.selected_clips:
            c_start = clip_info["start"]
            c_end = clip_info["end"]
            out_path = subs_dir / f"clip_{clip_info['number']:02d}.ass"
            self.subtitle_renderer.render(
                words=words_timing,
                clip_start=c_start,
                clip_end=c_end,
                config=self.config,
                output_path=out_path,
            )
            subtitle_paths.append((clip_info["number"], out_path))
        self._ctx.render_state["subtitle_paths"] = subtitle_paths

    # ------------------------------------------------------------------
    # Step 7: Render videos
    # ------------------------------------------------------------------
    def _step_7_render_videos(self, result: PipelineResult) -> None:
        _progress(7, len(_STEPS), _STEPS[6])
        clips_dir = self._ctx.output_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        subtitle_paths = self._ctx.render_state.get("subtitle_paths", [])
        sub_map = {num: path for num, path in subtitle_paths}

        clip_iter = self._ctx.selected_clips
        if _TQDM_AVAILABLE:
            clip_iter = _tqdm(clip_iter, desc="Rendering clips", leave=False)
        for clip_info in clip_iter:
            num = clip_info["number"]
            candidate = ClipCandidate(
                clip_number=num,
                start=clip_info["start"],
                end=clip_info["end"],
                score=clip_info["score"],
                title=clip_info["title"],
                summary=clip_info["summary"],
            )
            sub_path = sub_map.get(num)
            if sub_path is None:
                result.clips.append(ClipResult(
                    number=num, video_path=Path(), thumbnail_path=Path(),
                    success=False, error="No subtitle path found",
                ))
                continue
            try:
                t0 = time.monotonic()
                rendered = self.video_renderer.render_clip(self._ctx, candidate, sub_path)
                elapsed = time.monotonic() - t0
                self.metrics.record_clip_render(num, elapsed)
                result.clips.append(ClipResult(
                    number=num,
                    video_path=rendered.path,
                    thumbnail_path=rendered.thumbnail_path,
                ))
            except RenderingError as exc:
                result.clips.append(ClipResult(
                    number=num, video_path=Path(), thumbnail_path=Path(),
                    success=False, error=str(exc),
                ))

        result.successful_clips = sum(1 for c in result.clips if c.success)
        result.failed_clips = sum(1 for c in result.clips if not c.success)
        result.total_clips = len(result.clips)

    # ------------------------------------------------------------------
    # Step 8: Validate rendered outputs
    # ------------------------------------------------------------------
    def _step_8_validate_rendered(self, result: PipelineResult) -> None:
        _progress(8, len(_STEPS), _STEPS[7])
        clips_dir = self._ctx.output_dir / "clips"
        if not clips_dir.exists():
            return
        for f in clips_dir.iterdir():
            if f.suffix.lower() == ".mp4":
                try:
                    validate_rendered_video(f, _TARGET_WIDTH, _TARGET_HEIGHT)
                except RenderingError as exc:
                    _progress(8, len(_STEPS), f"Validation warning for {f.name}: {exc}")
                    for cr in result.clips:
                        if cr.video_path.resolve() == f.resolve():
                            cr.success = False
                            cr.error = f"Validation failed: {exc}"
                            break
        result.successful_clips = sum(1 for c in result.clips if c.success)
        result.failed_clips = sum(1 for c in result.clips if not c.success)

    # ------------------------------------------------------------------
    # Step 9: Generate metadata
    # ------------------------------------------------------------------
    def _step_9_generate_metadata(self, result: PipelineResult) -> None:
        _progress(9, len(_STEPS), _STEPS[8])
        repaired = self._ctx.transcript_data.get("repaired_words", [])
        for clip_info in self._ctx.selected_clips:
            num = clip_info["number"]
            c_start = clip_info["start"]
            c_end = clip_info["end"]
            candidate = ClipCandidate(
                clip_number=num,
                start=c_start,
                end=c_end,
                score=clip_info["score"],
                title=clip_info["title"],
                summary=clip_info["summary"],
            )
            excerpt_words = [
                WordInfo(word=w[0], start=float(w[1]), end=float(w[2]), probability=float(w[3]))
                for w in repaired
                if float(w[1]) >= c_start and float(w[2]) <= c_end
            ]
            excerpt = " ".join(w.word for w in excerpt_words)
            try:
                meta = self.metadata_generator.generate(candidate, excerpt, self.config)
                cr = next((c for c in result.clips if c.number == num), None)
                if cr is not None:
                    cr.metadata = meta
                meta_dir = self._ctx.metadata_output_dir
                if meta_dir:
                    meta_path = meta_dir / f"clip_{num:02d}_metadata.json"
                    import json
                    meta_path.write_text(
                        json.dumps({
                            "title": meta.title,
                            "description": meta.description,
                            "hashtags": meta.hashtags,
                            "category": meta.category,
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except MetadataError as exc:
                _progress(9, len(_STEPS), f"Metadata generation failed for clip {num}: {exc}")

    # ------------------------------------------------------------------
    # Step 10: Produce final outputs
    # ------------------------------------------------------------------
    def _step_10_produce_final(self, result: PipelineResult) -> None:
        _progress(10, len(_STEPS), _STEPS[9])
        result.duration = self._ctx.duration
        summary = {
            "source_duration_s": self._ctx.duration,
            "total_clips": result.total_clips,
            "successful_clips": result.successful_clips,
            "failed_clips": result.failed_clips,
            "output_dir": str(result.output_dir),
            "clips": [
                {
                    "number": c.number,
                    "video": str(c.video_path),
                    "thumbnail": str(c.thumbnail_path),
                    "success": c.success,
                }
                for c in result.clips
            ],
        }
        import json
        summary_path = self._ctx.output_dir / "pipeline_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[{len(_STEPS)}/{len(_STEPS)}] Finished.")
