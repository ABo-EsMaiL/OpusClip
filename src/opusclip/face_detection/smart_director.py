"""
Smart crop director for vertical video reframing.

Maintains a smoothed horizontal position for the output crop window and
updates it each frame based on detected face positions and active speaker
detection (mouth aspect ratio).

State transitions:
  BROLL — no faces, drift toward centre.
  SOLO  — one active speaker (or multiple speakers close together).
  GROUP — multiple active speakers spread far apart.

Based on the original v2.1 implementation which uses dlib-style MAR
(Mouth Aspect Ratio) to detect who is actively speaking.
"""

from dataclasses import dataclass

from .base import FaceResult


_ALPHA_SOLO: float = 0.07
_ALPHA_GROUP: float = 0.04
_ALPHA_BROLL: float = 0.012

_MAX_DX_RATIO: float = 0.04

_NO_FACE_HOLD_S: float = 0.5

# If multiple active speakers are closer than this fraction of crop width,
# treat them as a single subject (SOLO mode).
_GRP_SPREAD_RATIO: float = 0.55


@dataclass(frozen=True, slots=True)
class _FacePoint:
    x: int
    y: int
    w: int
    h: int
    mar: float


class SmartDirector:
    """Frame-by-frame crop director for vertical video reframing.

    Uses MAR (mouth aspect ratio) to detect active speakers and decides
    between SOLO, GROUP, and BROLL states.

    Args:
        vid_w: Source video width in pixels.
        vid_h: Source video height in pixels.
        src_crop_w: Width of the vertical crop window in source pixels.
        fps: Source video frame rate.
        speaking_mar: MAR threshold above which a face is 'actively speaking'.
        min_face_area: Minimum face area fraction. Smaller faces ignored.
        debounce_s: Seconds a state must persist before committing.
    """

    SOLO = 0
    GROUP = 1
    BROLL = 2

    def __init__(
        self,
        vid_w: int,
        vid_h: int,
        src_crop_w: int,
        fps: float,
        speaking_mar: float,
        min_face_area: float,
        debounce_s: float,
    ) -> None:
        self.vw = vid_w
        self.vh = vid_h
        self.cw = src_crop_w
        self.fps = fps
        self._mar_thr = speaking_mar
        self._area_thr = min_face_area
        self._hold_frames = max(1, int(fps * debounce_s))
        self._grp_spread = src_crop_w * _GRP_SPREAD_RATIO
        self._smooth_x = float(vid_w // 2)
        self._state = self.BROLL
        self._hold_count = 0
        self._max_dx = max(1, int(src_crop_w * _MAX_DX_RATIO))
        self._no_face_hold_frames = max(1, int(fps * _NO_FACE_HOLD_S))
        self._no_face_counter = 0

    @property
    def state(self) -> int:
        return self._state

    def _crop_start(self) -> int:
        return int(max(0, min(self._smooth_x - self.cw // 2, self.vw - self.cw)))

    def _get_valid_faces(self, faces: list[FaceResult]) -> list[_FacePoint]:
        frame_area = self.vw * self.vh
        valid: list[_FacePoint] = []
        for f in faces:
            x, y, bw, bh = f.bbox
            area_ratio = (bw * bh) / frame_area
            if area_ratio >= self._area_thr:
                valid.append(_FacePoint(x=x + bw // 2, y=y + bh // 2, w=bw, h=bh, mar=f.mouth_open_score))
        return valid

    def update(self, faces: list[FaceResult]) -> int:
        """Update the director state given this frame's detected faces.

        Args:
            faces: All detected faces in the current frame.

        Returns:
            The x-coordinate (pixels) of the left edge of the recommended
            crop window for this frame.
        """
        valid = self._get_valid_faces(faces)

        # Determine active speakers (MAR above threshold)
        active = [fp for fp in valid if fp.mar > self._mar_thr]

        # Decide desired state based on v2.1 logic
        if not valid:
            # No faces at all → BROLL (with hold for brief disappearances)
            if self._state != self.BROLL:
                self._no_face_counter += 1
                if self._no_face_counter >= self._no_face_hold_frames:
                    desired = self.BROLL
                else:
                    desired = self._state
            else:
                desired = self.BROLL
        elif not active:
            # Faces present but no one actively speaking → keep current state
            desired = self._state
        elif len(active) == 1:
            desired = self.SOLO
        else:
            # Multiple active speakers → SOLO if close together, GROUP if spread
            xs = [fp.x for fp in active]
            if (max(xs) - min(xs)) < self._grp_spread:
                desired = self.SOLO
            else:
                desired = self.GROUP

        # Hysteresis debounce
        if desired != self._state:
            self._hold_count += 1
            if self._hold_count >= self._hold_frames:
                self._state = desired
                self._hold_count = 0
        else:
            self._hold_count = max(0, self._hold_count - 2)

        # Reset no-face counter when faces are present
        if valid:
            self._no_face_counter = 0

        # Compute target pan position
        if self._state == self.SOLO:
            src = active if active else valid
            if src:
                tx = sum(fp.x for fp in src) // len(src)
            else:
                tx = self.vw // 2
            alpha = _ALPHA_SOLO
        elif self._state == self.GROUP:
            src = active if active else valid
            if src:
                xs = [fp.x for fp in src]
                tx = (min(xs) + max(xs)) // 2
            else:
                tx = self.vw // 2
            alpha = _ALPHA_GROUP
        else:
            tx = self.vw // 2
            alpha = _ALPHA_BROLL

        raw_dx = alpha * (tx - self._smooth_x)
        self._smooth_x += max(float(-self._max_dx), min(float(self._max_dx), raw_dx))
        return self._crop_start()
