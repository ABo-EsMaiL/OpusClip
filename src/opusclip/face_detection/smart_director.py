"""
Smart crop director for vertical video reframing.

Maintains a smoothed horizontal position for the output crop window and
updates it each frame based on detected face positions.
The director implements a three-state machine (SOLO, GROUP, BROLL) with
hysteresis debouncing and temporal smoothing to avoid jittery cuts.
"""

from dataclasses import dataclass

from .base import FaceResult


# ── Camera smoothing factors ──────────────────────────────────────────────────
_ALPHA_SOLO: float = 0.07
_ALPHA_GROUP: float = 0.04
_ALPHA_BROLL: float = 0.012

_MAX_DX_RATIO: float = 0.04

_GROUP_SPREAD_RATIO: float = 0.55

_NO_FACE_HOLD_S: float = 0.5


@dataclass(frozen=True, slots=True)
class _FacePoint:
    x: int
    mar: float


class SmartDirector:
    """Frame-by-frame crop director for vertical video reframing.

    Maintains a smoothed horizontal position for the output crop window and
    transitions between three states based purely on face COUNT:

    * **SOLO**: Exactly one valid face in frame — crop follows that person.
    * **GROUP**: Two or more valid faces — crop covers the bounding box of all faces.
    * **BROLL**: No valid faces detected — crop drifts toward centre.

    State transitions are debounced and include a temporal hold: if faces
    disappear briefly (< 0.5 s) the director stays in its previous state
    to avoid flickering between BROLL and a face mode.

    Args:
        vid_w: Source video width in pixels.
        vid_h: Source video height in pixels.
        src_crop_w: Width of the vertical crop window in source pixels.
        fps: Source video frame rate.
        speaking_mar: (Legacy) mouth-open threshold, kept for compatibility.
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
        self._grp_spread_px = src_crop_w * _GROUP_SPREAD_RATIO
        self._smooth_x = vid_w // 2
        self._state = self.BROLL
        self._hold_count = 0
        self._max_dx = max(1, int(src_crop_w * _MAX_DX_RATIO))
        self._no_face_hold_frames = max(1, int(fps * _NO_FACE_HOLD_S))
        self._no_face_counter = 0

    @property
    def state(self) -> int:
        return self._state

    def _crop_start(self) -> int:
        return max(0, min(self._smooth_x - self.cw // 2, self.vw - self.cw))

    def update(self, faces: list[FaceResult]) -> int:
        """Update the director state given this frame's detected faces.

        Args:
            faces: All detected faces in the current frame.

        Returns:
            The x-coordinate (pixels) of the left edge of the recommended
            crop window for this frame.
        """
        frame_area = self.vw * self.vh

        valid: list[_FacePoint] = []
        for f in faces:
            x, y, bw, bh = f.bbox
            area_ratio = (bw * bh) / frame_area
            if area_ratio >= self._area_thr:
                valid.append(_FacePoint(x=x + bw // 2, mar=f.mouth_open_score))

        n_faces = len(valid)

        # Determine desired state based on face count.
        if n_faces == 0:
            # Temporal hold: don't jump to BROLL immediately
            if self._state != self.BROLL:
                self._no_face_counter += 1
                if self._no_face_counter >= self._no_face_hold_frames:
                    desired = self.BROLL
                else:
                    desired = self._state
            else:
                desired = self.BROLL
        else:
            self._no_face_counter = 0
            if n_faces == 1:
                desired = self.SOLO
            else:
                desired = self.GROUP

        # Hysteresis: only commit after debounce threshold.
        if desired != self._state:
            self._hold_count += 1
            if self._hold_count >= self._hold_frames and desired != self._state:
                self._state = desired
                self._hold_count = 0
        else:
            self._hold_count = max(0, self._hold_count - 2)

        # Compute target pan position and smoothing speed.
        if self._state == self.SOLO:
            if valid:
                tx = sum(fp.x for fp in valid) // len(valid)
            else:
                tx = self.vw // 2
            alpha = _ALPHA_SOLO
        elif self._state == self.GROUP:
            if valid:
                xs = [fp.x for fp in valid]
                tx = (min(xs) + max(xs)) // 2
            else:
                tx = self.vw // 2
            alpha = _ALPHA_GROUP
        else:
            tx = self.vw // 2
            alpha = _ALPHA_BROLL

        raw_dx = int(alpha * (tx - self._smooth_x))
        self._smooth_x += max(-self._max_dx, min(self._max_dx, raw_dx))
        return self._crop_start()
