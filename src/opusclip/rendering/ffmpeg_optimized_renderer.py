"""
Optimized Single-Pass FFmpeg Renderer implementation.

Eliminates the intermediate scan.mp4 file and double-read loop by running
face detection and smart cropping in a single unified pass.
"""

import cv2
import os
from pathlib import Path
import shutil

from .base import VideoRenderer, RenderedClip
from ..context import PipelineContext
from ..clip_selection.base import ClipCandidate
from ..face_detection.base import FaceDetector, FaceResult
from ..face_detection.smart_director import SmartDirector
from .broll import make_broll_frame
from ..utils.ffmpeg_utils import run_ffmpeg, FFmpegPipe, build_encoder_args, check_encoder_available
from ..exceptions import RenderingError

from ..config import PipelineConfig

_FADE_DURATION = 0.4


class FFmpegOptimizedRenderer(VideoRenderer):
    """Single-pass FFmpeg renderer that merges subtitles, audio, and fades in one pipe."""

    def __init__(self, face_detector: FaceDetector, config: PipelineConfig):
        self.face_detector = face_detector
        self.config = config
        self._encoder = self._resolve_encoder()

    def _resolve_encoder(self) -> str:
        enc = self.config.encoder
        if enc != "libx264" and not check_encoder_available(enc):
            import warnings
            warnings.warn(
                f"Requested encoder '{enc}' is unavailable. Falling back to libx264."
            )
            return "libx264"
        return enc

    def render_clip(
        self, context: PipelineContext, clip: ClipCandidate, subtitle_path: Path
    ) -> RenderedClip:
        n = clip.clip_number or 1
        c_start = clip.start
        duration = clip.end - clip.start

        work_dir = context.output_dir / "work"
        clips_dir = context.output_dir / "clips"
        work_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        base = f"clip_{n:02d}"
        raw_path = work_dir / f"{base}_raw.mp4"
        audio_path = work_dir / f"{base}_audio.aac"
        safe_ass = work_dir / f"{base}_safe.ass"
        thumb_path = clips_dir / f"{base}_thumb.jpg"
        final_path = clips_dir / f"{base}_FINAL.mp4"

        if final_path.exists():
            return RenderedClip(
                path=final_path,
                thumbnail_path=thumb_path if thumb_path.exists() else final_path,
                duration=duration,
                resolution=(context.target_width, context.target_height),
            )

        try:
            # ── Step 1: Two-stage seek
            PRE_SEEK = max(0.0, c_start - 10.0)
            FINE_SEEK = c_start - PRE_SEEK

            raw_encoder = build_encoder_args(self._encoder, self.config.raw_clip_crf, "ultrafast", raw_extract=True)
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{PRE_SEEK:.3f}",
                    "-i",
                    str(context.video_path),
                    "-ss",
                    f"{FINE_SEEK:.3f}",
                    "-t",
                    f"{duration + 0.5:.3f}",
                    *raw_encoder,
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(raw_path),
                ]
            )

            run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(raw_path),
                    "-vn",
                    "-af",
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    str(audio_path),
                ]
            )

            # ── Step 2: Single-pass Face Scan & Render with subtitles + audio
            SCAN_H = min(480, context.video_height)
            scan_scale = SCAN_H / context.video_height
            SCAN_W = int(context.video_width * scan_scale)
            if SCAN_W % 2:
                SCAN_W += 1

            director = SmartDirector(
                vid_w=context.video_width,
                vid_h=context.video_height,
                src_crop_w=context.src_crop_w,
                fps=context.video_fps,
                speaking_mar=self.config.speaking_mar,
                min_face_area=self.config.min_face_area,
                debounce_s=self.config.state_debounce_s,
            )

            raw_cap = cv2.VideoCapture(str(raw_path))
            if not raw_cap.isOpened():
                raise RenderingError(f"Failed to open generated raw clip: {raw_path}")
            n_frames = int(raw_cap.get(cv2.CAP_PROP_FRAME_COUNT))

            best_frame = None
            best_face_area = 0.0
            fi = 0
            last_faces = []

            shutil.copy(subtitle_path, safe_ass)

            vf = f"ass={safe_ass},fade=t=in:st=0:d={_FADE_DURATION},fade=t=out:st={max(0, duration - _FADE_DURATION):.2f}:d={_FADE_DURATION}"
            pipe_encoder = build_encoder_args(self._encoder, self.config.clip_crf, "fast")

            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{context.target_width}x{context.target_height}",
                "-r",
                str(context.video_fps),
                "-i",
                "pipe:0",
                "-i",
                str(audio_path),
                "-vf",
                vf,
                *pipe_encoder,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                str(final_path),
            ]

            with FFmpegPipe(cmd) as pipe:
                try:
                    while True:
                        ok, frame = raw_cap.read()
                        if not ok:
                            break

                        if fi % 3 == 0:
                            scan_frame = cv2.resize(
                                frame, (SCAN_W, SCAN_H), interpolation=cv2.INTER_LINEAR
                            )
                            last_faces = self.face_detector.detect(scan_frame)

                        scaled_faces = []
                        for f in last_faces:
                            x, y, w, h = f.bbox
                            scaled_faces.append(
                                FaceResult(
                                    bbox=(
                                        int(x / scan_scale),
                                        int(y / scan_scale),
                                        int(w / scan_scale),
                                        int(h / scan_scale),
                                    ),
                                    landmarks=[],
                                    mouth_open_score=f.mouth_open_score,
                                )
                            )

                        cx = director.update(scaled_faces)
                        fstate = director.state

                        if fstate == SmartDirector.BROLL:
                            resized = make_broll_frame(
                                frame, context.target_width, context.target_height
                            )
                        else:
                            cx = max(0, min(cx, context.video_width - context.src_crop_w))
                            cropped = frame[:, cx : cx + context.src_crop_w]
                            resized = cv2.resize(
                                cropped,
                                (context.target_width, context.target_height),
                                interpolation=cv2.INTER_LINEAR,
                            )

                            if last_faces and n_frames * 0.25 < fi < n_frames * 0.75:
                                fa = max(
                                    (f.bbox[2] * f.bbox[3]) / (SCAN_W * SCAN_H) for f in last_faces
                                )
                                if fa > best_face_area:
                                    best_face_area = fa
                                    best_frame = resized.copy()

                        try:
                            pipe.stdin.write(resized.tobytes())
                        except BrokenPipeError:
                            try:
                                pipe.stdin.close()
                            except OSError:
                                pass
                            rc = pipe.process.wait(timeout=30)
                            if rc != 0:
                                raise RenderingError(
                                    f"FFmpeg pipe failed with exit code {rc} during rendering."
                                ) from None
                            break
                        fi += 1
                finally:
                    raw_cap.release()

            if best_frame is not None:
                cv2.imwrite(str(thumb_path), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])

            return RenderedClip(
                path=final_path,
                thumbnail_path=thumb_path if best_frame is not None else final_path,
                duration=duration,
                resolution=(context.target_width, context.target_height),
            )

        finally:
            for p in [raw_path, audio_path, safe_ass]:
                try:
                    os.remove(p)
                except OSError:
                    pass
