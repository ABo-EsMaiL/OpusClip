"""
MediaPipe FaceLandmarker-based face detection provider.

Implements :class:`~opusclip.face_detection.base.FaceDetector` using the
MediaPipe Tasks vision API. Replaces the legacy dlib HOG detector with a
modern, GPU-friendly solution that also exposes facial blendshapes (used to
infer mouth-open score without extra landmark arithmetic).

The required ``face_landmarker.task`` model (~15 MB) is automatically
downloaded from the MediaPipe model zoo on first use if not already
present at the configured path.
"""

import os
import urllib.request


import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from .base import FaceDetector, FaceResult, VideoFrame
from ..exceptions import FaceDetectionError

# https://developers.google.com/mediapipe/solutions/vision/face_landmarker
_FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)


class MediaPipeFaceDetector(FaceDetector):
    """Face detector backed by MediaPipe FaceLandmarker.

    Detects faces in a single video frame and converts normalised MediaPipe
    landmarks into pixel-space bounding boxes and landmark coordinates
    compatible with :class:`~opusclip.face_detection.base.FaceResult`.

    The model file is auto-downloaded from the MediaPipe model zoo on first
    initialisation if it does not exist at *model_asset_path*.

    Args:
        model_asset_path: Absolute or relative path to the
            ``face_landmarker.task`` model file.
        num_faces: Maximum number of faces to detect per frame.
    """

    def __init__(self, model_asset_path: str, num_faces: int = 10) -> None:
        """Load and initialise the MediaPipe FaceLandmarker.

        Downloads the model automatically if it is not found at the given path.

        Args:
            model_asset_path: Path to the ``.task`` model bundle.
            num_faces: Upper bound on detected faces per frame.

        Raises:
            FaceDetectionError: If the model could not be found or downloaded.
        """
        if not os.path.exists(model_asset_path):
            print("Downloading face_landmarker.task (~15 MB) ...")
            try:
                urllib.request.urlretrieve(_FACE_LANDMARKER_URL, model_asset_path)
            except Exception as exc:
                raise FaceDetectionError(
                    f"MediaPipe model not found: {model_asset_path!r} "
                    f"and auto-download failed: {exc}. "
                    "Download manually from: " + _FACE_LANDMARKER_URL
                ) from exc
            size_mb = os.path.getsize(model_asset_path) / 1_048_576
            print(f"  Downloaded ({size_mb:.1f} MB)")

        base_options = mp_python.BaseOptions(model_asset_path=model_asset_path)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
            num_faces=num_faces,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    def detect(self, frame: VideoFrame) -> list[FaceResult]:
        """Detect all faces in *frame* and return structured results.

        Args:
            frame: A video frame conforming to the :class:`VideoFrame` protocol
                (i.e. any object that exposes ``.shape`` and ``.tobytes()``).
                At runtime this is a ``numpy.ndarray`` in BGR format.

        Returns:
            A (possibly empty) list of :class:`FaceResult` objects, one per
            detected face, with pixel-space bounding boxes and landmarks.
        """
        # MediaPipe expects SRGB byte data. numpy arrays satisfy VideoFrame.
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame,  # type: ignore[arg-type]
        )
        detection = self._landmarker.detect(mp_image)

        h, w = frame.shape[:2]
        results: list[FaceResult] = []

        for i, landmarks in enumerate(detection.face_landmarks):
            blendshapes = detection.face_blendshapes[i] if detection.face_blendshapes else []

            # Extract jawOpen blendshape score as mouth-open metric.
            mouth_open_score = 0.0
            for bs in blendshapes:
                if bs.category_name == "jawOpen":
                    mouth_open_score = float(bs.score)
                    break

            # Convert normalised [0,1] coordinates to pixel integers.
            px_landmarks = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

            if not px_landmarks:
                continue

            xs = [p[0] for p in px_landmarks]
            ys = [p[1] for p in px_landmarks]
            bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

            results.append(
                FaceResult(
                    bbox=bbox,
                    landmarks=px_landmarks,
                    mouth_open_score=mouth_open_score,
                )
            )

        return results

    def is_speaking(self, face: FaceResult) -> bool:
        """Return ``True`` if the face's jaw-open score exceeds a baseline threshold.

        .. note::
            This method provides a conservative, context-free estimate.
            :class:`~opusclip.face_detection.smart_director.SmartDirector`
            applies a configurable threshold (``speaking_mar`` from
            :class:`~opusclip.config.PipelineConfig`) rather than calling
            this method directly, which allows per-deployment calibration
            without changing the detector.

        Args:
            face: A detected face result.

        Returns:
            ``True`` when ``mouth_open_score > 0.05`` (a rough lower bound
            for any perceptible jaw opening on the MediaPipe 0–1 scale).
        """
        # 0.05 is not a tunable threshold; it is a definitional lower bound
        # meaning "any measurable jaw opening". SmartDirector uses its own
        # configurable MAR_THR for the actual speaking decision.
        return face.mouth_open_score > 0.05
