"""Pipeline orchestrator — runs the 10-step video-to-clips pipeline."""

import json
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


def _sec2str(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def _progress(current: int, total: int, message: str) -> None:
    print("=" * 80)
    print(f"[{current}/{total}] {message}...")
    print("=" * 80)


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
        self._skip_health_checks: bool = False

    def _error_msg(self, step_name: str, reason: str, suggestion: str = "") -> str:
        lines = [f"Step: {step_name}", f"Reason: {reason}"]
        if suggestion:
            lines.append(f"Suggestion: {suggestion}")
        lines.append("Resume available: run again to continue from this step.")
        return "\n".join(lines)

    def _check_health(self) -> None:
        if self._skip_health_checks:
            return
        import subprocess
        import shutil

        if shutil.which("ffmpeg") is None:
            raise OpusClipError("ffmpeg not found on PATH — install FFmpeg to continue.")
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OpusClipError(f"ffmpeg cannot execute: {exc}") from exc

        if shutil.which("ffprobe") is None:
            raise OpusClipError("ffprobe not found on PATH — install FFmpeg (includes ffprobe) to continue.")
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OpusClipError(f"ffprobe cannot execute: {exc}") from exc

        if self.config.encoder and self.config.encoder != "libx264":
            from .utils.ffmpeg_utils import check_encoder_available
            if not check_encoder_available(self.config.encoder):
                print("  Warning: encoder '{self.config.encoder}' unavailable, falling back to libx264.")

    def _save_transcript_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "transcript.json"
        try:
            p.write_text(
                json.dumps(self._ctx.transcript_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _save_repaired_transcript_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "repaired_transcript.json"
        try:
            data = {"repaired_words": self._ctx.transcript_data.get("repaired_words", [])}
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _save_clips_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "selected_clips.json"
        try:
            p.write_text(
                json.dumps(self._ctx.selected_clips, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def run(self, source: str, resume: bool = True,
            output_dir: Optional[Path] = None, fresh: bool = False) -> PipelineResult:
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

        self._check_health()

        result = PipelineResult(output_dir=out, source=source)
        self.metrics = PipelineMetrics()
        self.metrics.start()

        cache = CacheManager(out, source)

        if fresh:
            cache.clear()

        # ── Determine which stages are already complete ────────────────
        transcript_done = cache.transcript_is_valid()
        repair_done = cache.repaired_transcript_is_valid()
        clips_done = cache.selected_clips_are_valid()

        # Load required artifacts
        if transcript_done:
            self._load_transcript_artifact()
            print("  Found transcript.json — skipping transcription.")
        if repair_done:
            self._load_repaired_transcript_artifact()
            print("  Found repaired_transcript.json — skipping transcript repair.")
        if clips_done:
            self._load_clips_artifact()
            print("  Found selected_clips.json — skipping clip selection.")

        # Determine clip numbers for clip-level resume
        clip_numbers: list[int] = []
        if self._ctx.selected_clips:
            clip_numbers = [c["number"] for c in self._ctx.selected_clips]

        if transcript_done and repair_done and clips_done and clip_numbers:
            print(f"  Clip-level resume active for {len(clip_numbers)} clips.")

        steps: list[tuple[int, str, Callable[[], None]]] = [
            (1, "validate_input", lambda: self._step_1_validate_input(source)),
            (2, "read_metadata", self._step_2_read_metadata),
            (3, "transcribe_audio", self._step_3_transcribe_audio),
            (4, "repair_transcript", self._step_4_repair_transcript),
            (5, "select_clips", self._step_5_select_clips),
            (6, "render_subtitles", lambda: self._step_6_render_subtitles(cache)),
            (7, "render_videos", lambda: self._step_7_render_videos(result, cache)),
            (8, "validate_rendered", lambda: self._step_8_validate_rendered(result)),
            (9, "generate_metadata", lambda: self._step_9_generate_metadata(result, cache, clip_numbers)),
            (10, "produce_final", lambda: self._step_10_produce_final(result)),
        ]

        try:
            for step_num, stage_name, step_fn in steps:
                # Determine if this step is already complete
                skip = self._step_is_cached(step_num, cache, transcript_done, repair_done,
                                            clips_done, clip_numbers)
                if skip:
                    _progress(step_num, len(_STEPS), f"{_STEPS[step_num - 1]} (cached)")
                    continue
                with self.metrics.measure_stage(stage_name):
                    try:
                        step_fn()
                    except (OpusClipError, InputValidationError,
                            TranscriptionError, RenderingError, MetadataError) as exc:
                        err = self._error_msg(
                            _STEPS[step_num - 1],
                            str(exc),
                            "Retry later. Resume available — run again without --fresh.",
                        )
                        print(f"\n  [Pipeline Error]\n{err}")
                        raise
                elapsed = self.metrics.stages.get(stage_name, 0)
                print(f"  Completed in {elapsed:.1f}s")
                self._save_step_artifacts(step_num)
        except OpusClipError:
            raise
        except KeyboardInterrupt:
            print("\nInterrupted — progress saved. Resume available.")
            raise
        except Exception as exc:
            err = self._error_msg(
                "Unknown",
                f"{type(exc).__name__}: {exc}",
                "Check logs for details.",
            )
            print(f"\n  [Pipeline Error]\n{err}")
            raise OpusClipError(f"Pipeline failed at an unexpected point: {exc}") from exc
        finally:
            # Capture peak memory metrics
            self.metrics.record_memory()
            self.metrics.finish()
            self.metrics.failures = result.failed_clips
            print(self._summary_report(result))
            print(self.metrics.report())

        return result

    def _step_is_cached(self, step_num: int, cache: CacheManager,
                         transcript_done: bool, repair_done: bool,
                         clips_done: bool, clip_numbers: list[int]) -> bool:
        """Determine if a step can be skipped because its artifacts are valid."""
        if step_num == 1 or step_num == 2:
            return False
        if step_num == 3:
            return transcript_done
        if step_num == 4:
            return repair_done
        if step_num == 5:
            return clips_done
        if step_num == 6 and clips_done and clip_numbers:
            missing_subs = cache.list_missing_subtitles(clip_numbers)
            return len(missing_subs) == 0
        if step_num == 7 and clips_done and clip_numbers:
            missing_vids = cache.list_missing_videos(clip_numbers)
            return len(missing_vids) == 0
        if step_num == 8:
            if clips_done and clip_numbers:
                missing_vids = cache.list_missing_videos(clip_numbers)
                return len(missing_vids) == 0
            return False
        if step_num == 9 and clips_done and clip_numbers:
            missing_meta = cache.list_missing_metadata(clip_numbers)
            return len(missing_meta) == 0
        if step_num == 10:
            return cache.summary_exists()
        return False

    def _save_step_artifacts(self, step: int) -> None:
        if step == 3:
            self._save_transcript_artifact()
        elif step == 4:
            self._save_repaired_transcript_artifact()
        elif step == 5:
            self._save_clips_artifact()

    def _load_transcript_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "transcript.json"
        if not p.exists():
            return
        try:
            self._ctx.transcript_data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    def _load_repaired_transcript_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "repaired_transcript.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._ctx.transcript_data["repaired_words"] = data.get("repaired_words", [])
        except (json.JSONDecodeError, OSError):
            pass

    def _load_clips_artifact(self) -> None:
        if self._ctx is None or self._ctx.output_dir is None:
            return
        p = self._ctx.output_dir / "selected_clips.json"
        if not p.exists():
            return
        try:
            self._ctx.selected_clips = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    def run_batch(self, sources: list[str], resume: bool = True, fresh: bool = False) -> list[PipelineResult]:
        results: list[PipelineResult] = []
        for source in sources:
            sub_dir = self.config.output_dir / _sanitize_source_name(source)
            try:
                result = self.run(source, resume=resume, output_dir=sub_dir, fresh=fresh)
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
        print("  Checking source path...")
        import urllib.parse
        parsed = urllib.parse.urlparse(source)
        if parsed.scheme in ("http", "https"):
            from .input_validator import validate_youtube_url
            try:
                validate_youtube_url(source)
                print("  YouTube URL validated.")
            except InputValidationError:
                pass
        else:
            from .input_validator import validate_video_path
            validate_video_path(source)
            print(f"  Local file: {source}")

    # ------------------------------------------------------------------
    # Step 2: Read metadata
    # ------------------------------------------------------------------
    def _step_2_read_metadata(self) -> None:
        _progress(2, len(_STEPS), _STEPS[1])
        print("  Acquiring video metadata...")
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
        print(f"  Video duration: {_sec2str(self._ctx.duration)}")
        print(f"  Resolution: {meta.width}x{meta.height} @ {meta.fps}fps")
        print(f"  Crop width calculated: {self._ctx.src_crop_w}px")

    # ------------------------------------------------------------------
    # Step 3: Transcribe audio
    # ------------------------------------------------------------------
    def _step_3_transcribe_audio(self) -> None:
        _progress(3, len(_STEPS), _STEPS[2])
        print("  Loading Whisper model...")
        video = self._ctx.video_path
        if video is None:
            raise TranscriptionError("No video path available for transcription.")
        audio_path = self._ctx.output_dir / "audio.wav"
        from .subprocess_utils import run_ffmpeg
        print("  Extracting audio...")
        run_ffmpeg([
            "-y", "-i", str(video),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(audio_path),
        ])
        audio_size = audio_path.stat().st_size if audio_path.exists() else 0
        audio_dur = self._ctx.duration
        print(f"  Audio duration: {_sec2str(audio_dur)} ({audio_size / 1024:.0f} KB)")
        try:
            lang = self._detect_language_from_path(video)
            if lang:
                print(f"  Detected language: {lang}")
            print("  Transcribing...")
            t0 = time.monotonic()
            result_obj = self.transcription_provider.transcribe(audio_path, lang)
            elapsed = time.monotonic() - t0
            self._ctx.transcript_data = {
                "segments": [(s.id, s.text, s.start, s.end) for s in result_obj.segments],
                "words": [(w.word, w.start, w.end, w.probability) for w in result_obj.words],
                "language": result_obj.language,
                "duration": result_obj.duration,
            }
            total_chars = sum(len(s.text) for s in result_obj.segments)
            print(f"  Generated: {len(result_obj.segments)} segments, {len(result_obj.words)} words, {total_chars} chars")
            print(f"  Language: {result_obj.language}")
            print(f"  Transcription completed in {_sec2str(elapsed)}")
            self.metrics.api_calls += 1
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
            print("  No words to repair.")
            return
        result_obj = TranscriptResult(
            segments=segments,
            words=all_words,
            language=raw.get("language", ""),
            duration=raw.get("duration", 0.0),
        )
        from .transcription.word_repair import fill_missing_words
        print(f"  Repairing {len(all_words)} words...")
        repaired = fill_missing_words(result_obj)
        from .subtitle.text_cleaner import clean_transcript_for_llm
        cleaned_words = [
            (clean_transcript_for_llm(w.word), w.start, w.end, w.probability)
            for w in repaired
        ]
        self._ctx.transcript_data["repaired_words"] = cleaned_words
        print(f"  Repaired: {len(cleaned_words)} words")

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
        total_chars = sum(len(s.text) for s in segments)
        print(f"  Total transcript chars: {total_chars}")
        print("  Preparing LLM prompt...")
        print(f"  Prompt size: {total_chars} chars")
        print("  Sending request to LLM...")
        t0 = time.monotonic()
        candidates = self.clip_selector.select_clips(result_obj, self.config)
        elapsed = time.monotonic() - t0
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
        print(f"  LLM response received in {elapsed:.1f}s")
        print(f"  Generated: {len(candidates)} clips")
        for c in candidates:
            print(f"    Clip {c.clip_number}: {c.start:.1f}s-{c.end:.1f}s (score: {c.score:.0f})")

    # ------------------------------------------------------------------
    # Step 6: Render subtitles
    # ------------------------------------------------------------------
    def _step_6_render_subtitles(self, cache: CacheManager) -> None:
        _progress(6, len(_STEPS), _STEPS[5])
        subs_dir = self._ctx.output_dir / "subtitles"
        subs_dir.mkdir(exist_ok=True)
        repaired = self._ctx.transcript_data.get("repaired_words", [])
        if not repaired:
            raw_words = self._ctx.transcript_data.get("words", [])
            if raw_words:
                repaired = raw_words
        if not repaired:
            print("  No words available for subtitle rendering.")
            return
        words_timing = [
            WordTiming(word=clean_for_subtitle(w[0]), start=float(w[1]), end=float(w[2]))
            for w in repaired
        ]
        subtitle_paths = []
        n_clips = len(self._ctx.selected_clips)
        clip_numbers = [c["number"] for c in self._ctx.selected_clips]
        missing = cache.list_missing_subtitles(clip_numbers)

        print(f"  Rendering subtitles for {len(missing)}/{n_clips} clips")
        for clip_info in self._ctx.selected_clips:
            num = clip_info["number"]
            c_start = clip_info["start"]
            c_end = clip_info["end"]
            out_path = subs_dir / f"clip_{num:02d}.ass"

            if num not in missing:
                print(f"    Clip {num}: cached")
                subtitle_paths.append((num, out_path))
                continue

            print(f"    Clip {num}: rendering ({c_start:.1f}s-{c_end:.1f}s)...")
            self.subtitle_renderer.render(
                words=words_timing,
                clip_start=c_start,
                clip_end=c_end,
                config=self.config,
                output_path=out_path,
            )
            subtitle_paths.append((num, out_path))
        self._ctx.render_state["subtitle_paths"] = subtitle_paths
        print(f"  Subtitle files: {len(subtitle_paths)}/{n_clips}")

    # ------------------------------------------------------------------
    # Step 7: Render videos
    # ------------------------------------------------------------------
    def _step_7_render_videos(self, result: PipelineResult, cache: CacheManager) -> None:
        _progress(7, len(_STEPS), _STEPS[6])
        clips_dir = self._ctx.output_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        subtitle_paths = self._ctx.render_state.get("subtitle_paths", [])
        sub_map = {num: path for num, path in subtitle_paths}
        total = len(self._ctx.selected_clips)
        clip_numbers = [c["number"] for c in self._ctx.selected_clips]
        missing = cache.list_missing_videos(clip_numbers)

        # Add cached clips to result
        for clip_info in self._ctx.selected_clips:
            num = clip_info["number"]
            if num not in missing:
                final = clips_dir / f"clip_{num:02d}_FINAL.mp4"
                thumb = clips_dir / f"clip_{num:02d}_thumb.jpg"
                result.clips.append(ClipResult(
                    number=num, video_path=final, thumbnail_path=thumb,
                ))

        print(f"  Rendering {len(missing)}/{total} clips (cached: {total - len(missing)})")

        clip_iter = self._ctx.selected_clips
        if _TQDM_AVAILABLE:
            clip_iter = _tqdm(clip_iter, desc="Rendering clips", leave=False)
        for clip_info in clip_iter:
            num = clip_info["number"]
            if num not in missing:
                continue
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
                print(f"  Rendering clip {num}/{total}: cropping...")
                t0 = time.monotonic()
                rendered = self.video_renderer.render_clip(self._ctx, candidate, sub_path)
                elapsed = time.monotonic() - t0
                self.metrics.record_clip_render(num, elapsed)
                result.clips.append(ClipResult(
                    number=num,
                    video_path=rendered.path,
                    thumbnail_path=rendered.thumbnail_path,
                ))
                size_mb = rendered.path.stat().st_size / (1024 * 1024) if rendered.path.exists() else 0
                print(f"    Clip {num}: saved ({elapsed:.1f}s, {size_mb:.1f} MB)")
            except RenderingError as exc:
                result.clips.append(ClipResult(
                    number=num, video_path=Path(), thumbnail_path=Path(),
                    success=False, error=str(exc),
                ))
                print(f"    Clip {num}: FAILED - {exc}")

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
            print("  No clips directory found.")
            return
        validated = 0
        failed_validation = 0
        for f in clips_dir.iterdir():
            if f.suffix.lower() == ".mp4":
                try:
                    validate_rendered_video(f, _TARGET_WIDTH, _TARGET_HEIGHT)
                    validated += 1
                except RenderingError as exc:
                    print(f"  Validation warning for {f.name}: {exc}")
                    for cr in result.clips:
                        if cr.video_path.resolve() == f.resolve():
                            cr.success = False
                            cr.error = f"Validation failed: {exc}"
                            break
                    failed_validation += 1
        result.successful_clips = sum(1 for c in result.clips if c.success)
        result.failed_clips = sum(1 for c in result.clips if not c.success)
        print(f"  Validated: {validated}/{validated + failed_validation} clips passed")

    # ------------------------------------------------------------------
    # Step 9: Generate metadata
    # ------------------------------------------------------------------
    def _step_9_generate_metadata(self, result: PipelineResult, cache: CacheManager,
                                   clip_numbers: list[int]) -> None:
        _progress(9, len(_STEPS), _STEPS[8])
        repaired = self._ctx.transcript_data.get("repaired_words", [])
        missing_meta = cache.list_missing_metadata(clip_numbers) if clip_numbers else [c["number"] for c in self._ctx.selected_clips]

        print(f"  Generating metadata for {len(missing_meta)}/{len(self._ctx.selected_clips)} clips")

        for clip_info in self._ctx.selected_clips:
            num = clip_info["number"]
            if num not in missing_meta:
                print(f"    Clip {num}: cached")
                continue
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
                    meta_path.write_text(
                        json.dumps({
                            "title": meta.title,
                            "description": meta.description,
                            "hashtags": meta.hashtags,
                            "category": meta.category,
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                print(f"    Clip {num}: metadata generated")
            except MetadataError as exc:
                print(f"    Clip {num}: metadata failed - {exc}")

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
        summary_path = self._ctx.output_dir / "pipeline_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[{len(_STEPS)}/{len(_STEPS)}] Finished.")

    def _summary_report(self, result: PipelineResult) -> str:
        lines = []
        lines.append("=" * 48)
        lines.append("  Pipeline Summary")
        lines.append("=" * 48)
        lines.append(f"  Source duration     : {_sec2str(self._ctx.duration) if self._ctx else 'N/A'}")
        for stage, elapsed in sorted(self.metrics.stages.items(), key=lambda x: x[1], reverse=True):
            pct = (elapsed / self.metrics.total_duration * 100) if self.metrics.total_duration else 0
            lines.append(f"  {stage:20s} : {elapsed:.1f}s ({pct:.0f}%)")
        lines.append(f"  Total time          : {self.metrics.total_duration:.1f}s")
        if self.metrics.clip_renders:
            avg = sum(self.metrics.clip_renders.values()) / max(len(self.metrics.clip_renders), 1)
            lines.append(f"  Avg clip render     : {avg:.1f}s")
        lines.append(f"  Successful clips    : {result.successful_clips}/{result.total_clips}")
        if self.metrics.peak_ram_mb:
            lines.append(f"  Peak RAM            : {self.metrics.peak_ram_mb:.0f} MB")
        if self.metrics.peak_vram_mb:
            lines.append(f"  Peak VRAM           : {self.metrics.peak_vram_mb:.0f} MB")
        if self.metrics.api_calls:
            lines.append(f"  LLM API calls       : {self.metrics.api_calls}")
        if self.metrics.api_retries:
            lines.append(f"  LLM API retries     : {self.metrics.api_retries}")
        lines.append("=" * 48)
        return "\n".join(lines)
