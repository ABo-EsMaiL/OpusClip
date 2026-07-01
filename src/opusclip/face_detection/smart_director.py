"""
Smart crop director for vertical video reframing.

Maintains a smoothed horizontal position for the output crop window and
updates it each frame based on detected face positions.
Implements a three-state machine (SOLO, GROUP, BROLL) with hysteresis
debouncing and temporal smoothing.

GROUP mode uses a union bounding box covering all valid faces plus 10%
safe padding to guarantee no detected face is cropped out.
"""

from dataclasses import dataclass

from .base import FaceResult


_ALPHA_SOLO: float = 0.07
_ALPHA_GROUP: float = 0.04
_ALPHA_BROLL: float = 0.012

_MAX_DX_RATIO: float = 0.04

_NO_FACE_HOLD_S: float = 0.5

_UNION_PADDING_RATIO: float = 0.10


@dataclass(frozen=True, slots=True)
class _FacePoint:
    x: int
    y: int
    w: int
    h: int
    mar: float


class SmartDirector:
    """Frame-by-frame crop director for vertical video reframing.

    Transitions between three states based purely on face COUNT:
      SOLO  — one valid face, crop tracks that person.
      GROUP — two or more faces, crop covers union bounding box + 10% padding.
      BROLL — no faces, crop drifts toward centre.

    Args:
        vid_w: Source video width in pixels.
        vid_h: Source video height in pixels.
        src_crop_w: Width of the vertical crop window in source pixels.
        fps: Source video frame rate.
        speaking_mar: (Legacy) mouth-open threshold.
        min_face_area: Minimum face area fraction. Smaller faces ignored.
        debounce_s: Seconds a state must persist before committing.
        union_padding: Fractional padding around the union bounding box.
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
        union_padding: float = _UNION_PADDING_RATIO,
    ) -> None:
        self.vw = vid_w
        self.vh = vid_h
        self.cw = src_crop_w
        self.fps = fps
        self._mar_thr = speaking_mar
        self._area_thr = min_face_area
        self._hold_frames = max(1, int(fps * debounce_s))
        self._smooth_x = float(vid_w // 2)
        self._state = self.BROLL
        self._hold_count = 0
        self._max_dx = max(1, int(src_crop_w * _MAX_DX_RATIO))
        self._no_face_hold_frames = max(1, int(fps * _NO_FACE_HOLD_S))
        self._no_face_counter = 0
        self._union_pad = union_padding

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
        n_faces = len(valid)

        # Determine desired state based on face count.
        if n_faces == 0:
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

        # Hysteresis debounce.
        if desired != self._state:
            self._hold_count += 1
            if self._hold_count >= self._hold_frames:
                self._state = desired
                self._hold_count = 0
        else:
            self._hold_count = max(0, self._hold_count - 2)

        # Compute target pan position with union bounding box for GROUP.
        if self._state == self.SOLO and valid:
            tx = valid[0].x
            alpha = _ALPHA_SOLO
        elif self._state == self.GROUP and valid:
            # Union bounding box covering all valid faces with 10% padding
            # Calculate the leftmost and rightmost edges of all faces
            left_edges = [fp.x - fp.w // 2 for fp in valid]
            right_edges = [fp.x + fp.w // 2 for fp in valid]
            
            leftmost = min(left_edges)
            rightmost = max(right_edges)
            union_width = rightmost - leftmost
            
            # Add 10% padding
            padding = int(union_width * self._union_pad)
            leftmost = max(0, leftmost - padding)
            rightmost = min(self.vw, rightmost + padding)
            
            # Center the crop on the union box center
            tx = (leftmost + rightmost) // 2
            alpha = _ALPHA_GROUP
        else:
            tx = self.vw // 2
            alpha = _ALPHA_BROLL

        raw_dx = alpha * (tx - self._smooth_x)
        self._smooth_x += max(float(-self._max_dx), min(float(self._max_dx), raw_dx))
        return self._crop_start()
