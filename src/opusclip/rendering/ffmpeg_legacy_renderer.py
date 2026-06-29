"""
Legacy Two-Pass FFmpeg Renderer implementation.

Matches the original notebook's two-pass behavior to serve as a baseline
for proving the correctness of the single-pass optimized renderer.
"""

import cv2
import os
from pathlib import Path
import shutil

from .base import VideoRenderer, RenderedClip
from ..context import PipelineContext
from ..clip_selection.base import ClipCandidate
from ..face_detection.base import FaceDetector
from ..face_detection.smart_director import SmartDirector
from .broll import make_broll_frame
from ..utils.ffmpeg_utils import run_ffmpeg, FFmpegPipe, build_encoder_args, check_encoder_available
from ..exceptions import RenderingError
from ..config import PipelineConfig


_FADE_DURATION = 0.4


class FFmpegLegacyRenderer(VideoRenderer):
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
        scan_path = work_dir / f"{base}_scan.mp4"
        silent_path = work_dir / f"{base}_silent.mp4"
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

            # ── Step 2: Face scan at 480p
            SCAN_H = min(480, context.video_height)
            scan_scale = SCAN_H / context.video_height
            SCAN_W = int(context.video_width * scan_scale)
            if SCAN_W % 2:
                SCAN_W += 1

            scan_encoder = build_encoder_args(self._encoder, 28, "ultrafast", raw_extract=True)
            run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(raw_path),
                    "-vf",
                    f"scale={SCAN_W}:{SCAN_H}",
                    *scan_encoder,
                    "-an",
                    str(scan_path),
                ]
            )

            scan_cap = cv2.VideoCapture(str(scan_path))
            if not scan_cap.isOpened():
                raise RenderingError(f"Failed to open generated scan clip: {scan_path}")
            frames_faces = []
            last_faces = []
            fi = 0
            try:
                while True:
                    ok, frame = scan_cap.read()
                    if not ok:
                        break
                    if fi % 3 == 0:  # FACE_DETECT_EVERY = 3
                        last_faces = self.face_detector.detect(frame)
                    frames_faces.append(last_faces)
                    fi += 1
            finally:
                scan_cap.release()

            # ── Step 3: Director decisions
            director = SmartDirector(
                vid_w=context.video_width,
                vid_h=context.video_height,
                src_crop_w=context.src_crop_w,
                fps=context.video_fps,
                speaking_mar=self.config.speaking_mar,
                min_face_area=self.config.min_face_area,
                debounce_s=self.config.state_debounce_s,
            )

            frame_data = [(director.update(ff), director.state) for ff in frames_faces]

            # ── Step 4: Render with smart crop
            raw_cap = cv2.VideoCapture(str(raw_path))
            if not raw_cap.isOpened():
                raise RenderingError(f"Failed to open generated raw clip: {raw_path}")
            best_frame = None
            best_face_area = 0.0
            n_frames = len(frames_faces)
            fi = 0

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
                *pipe_encoder,
                "-pix_fmt",
                "yuv420p",
                str(silent_path),
            ]

            with FFmpegPipe(cmd) as pipe:
                try:
                    while True:
                        ok, frame = raw_cap.read()
                        if not ok:
                            break

                        if fi < len(frame_data):
                            cx, fstate = frame_data[fi]
                        else:
                            cx, fstate = frame_data[-1]

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

                            if frames_faces[fi] and n_frames * 0.25 < fi < n_frames * 0.75:
                                # Need to calculate area from bbox (x, y, w, h)
                                fa = 0
                                for f in frames_faces[fi]:
                                    # FaceResult.bbox is tuple[int, int, int, int] (x, y, w, h)
                                    ar = (f.bbox[2] * f.bbox[3]) / (SCAN_W * SCAN_H)
                                    if ar > fa:
                                        fa = ar

                                if fa > best_face_area:
                                    best_face_area = fa
                                    best_frame = resized.copy()

                        try:
                            pipe.stdin.write(resized.tobytes())
                        except BrokenPipeError as e:
                            raise RenderingError(
                                "FFmpeg pipe closed unexpectedly during rendering."
                            ) from e
                        fi += 1
                finally:
                    raw_cap.release()

            if best_frame is not None:
                cv2.imwrite(str(thumb_path), best_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])

            # ── Step 5: Subtitles + merge
            shutil.copy(subtitle_path, safe_ass)

            vf = f"subtitles={safe_ass},fade=t=in:st=0:d={_FADE_DURATION},fade=t=out:st={max(0, duration - _FADE_DURATION):.2f}:d={_FADE_DURATION}"

            try:
                merge_encoder = build_encoder_args(self._encoder, self.config.clip_crf, "fast")
                run_ffmpeg(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(silent_path),
                        "-i",
                        str(audio_path),
                        "-vf",
                        vf,
                        *merge_encoder,
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-shortest",
                        str(final_path),
                    ]
                )
            except RenderingError:
                run_ffmpeg(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(silent_path),
                        "-i",
                        str(audio_path),
                        "-c:v",
                        "copy",
                        "-c:a",
                        "copy",
                        "-shortest",
                        str(final_path),
                    ]
                )

            return RenderedClip(
                path=final_path,
                thumbnail_path=thumb_path if best_frame is not None else final_path,
                duration=duration,
                resolution=(context.target_width, context.target_height),
            )

        finally:
            for p in [raw_path, scan_path, silent_path, audio_path, safe_ass]:
                try:
                    os.remove(p)
                except OSError:
                    pass
