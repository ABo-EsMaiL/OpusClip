"""
Smart crop director for vertical video reframing.

Maintains a smoothed horizontal position for the output crop window and
updates it each frame based on detected face positions and activity states.
The director implements a three-state machine (SOLO → GROUP → BROLL) with
hysteresis debouncing to avoid jittery cuts.
"""

from dataclasses import dataclass

from .base import FaceResult


# ── Camera smoothing factors ──────────────────────────────────────────────────
# These constants control how quickly the crop window tracks the subject.
# Lower values = smoother but slower panning; higher values = more responsive.
# Values are empirically tuned for 30 fps vertical video.
_ALPHA_SOLO: float = 0.07  # Pan speed when tracking a single active speaker
_ALPHA_GROUP: float = 0.04  # Pan speed when framing a group of speakers
_ALPHA_BROLL: float = 0.012  # Drift speed when returning to centre in b-roll

# Fraction of the crop width used as the maximum per-frame pixel displacement.
# Prevents the crop window from jumping more than 4% of its width per frame.
_MAX_DX_RATIO: float = 0.04

# Fraction of the crop width that defines the "group spread" threshold.
# If active speakers span more than 55% of the crop width, GROUP mode is used.
_GROUP_SPREAD_RATIO: float = 0.55


@dataclass(frozen=True, slots=True)
class _FacePoint:
    """Internal representation of a validated face centre for director logic."""

    x: int  # Horizontal pixel centre of the face bounding box
    mar: float  # Mouth-open score (jawOpen blendshape, 0–1 scale)


class SmartDirector:
    """Frame-by-frame crop director for vertical video reframing.

    Maintains a smoothed horizontal position for the output crop window and
    transitions between three states:

    * **SOLO**: One active (speaking) face dominates the frame.
    * **GROUP**: Multiple active faces span a wide portion of the frame.
    * **BROLL**: No valid faces detected; crop drifts toward centre.

    State transitions are debounced: a new state must be consistently
    desired for at least ``debounce_s`` seconds before it is adopted.

    Args:
        vid_w: Source video width in pixels.
        vid_h: Source video height in pixels.
        src_crop_w: Width of the vertical crop window in source pixels.
        fps: Source video frame rate.
        speaking_mar: Mouth-open score threshold above which a face is
            considered actively speaking (MediaPipe jawOpen scale, 0–1).
            Sourced from :attr:`~opusclip.config.PipelineConfig.speaking_mar`.
        min_face_area: Minimum face bounding-box area as a fraction of the
            full frame area. Faces below this size are ignored.
            Sourced from :attr:`~opusclip.config.PipelineConfig.min_face_area`.
        debounce_s: Seconds a desired state must persist before the director
            commits to it, preventing rapid state oscillation.
            Sourced from :attr:`~opusclip.config.PipelineConfig.state_debounce_s`.
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

    @property
    def state(self) -> int:
        """The current director state (SOLO, GROUP, or BROLL)."""
        return self._state

    def _crop_start(self) -> int:
        """Compute the left edge of the current crop window, clamped to valid range."""
        return max(0, min(self._smooth_x - self.cw // 2, self.vw - self.cw))

    def update(self, faces: list[FaceResult]) -> int:
        """Update the director state given this frame's detected faces.

        Args:
            faces: All :class:`~opusclip.face_detection.base.FaceResult`
                objects detected in the current frame.

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

        active = [fp for fp in valid if fp.mar > self._mar_thr]

        # Determine desired state for this frame.
        if not valid:
            desired = self.BROLL
        elif not active:
            desired = self._state  # Hold current state; no new information
        elif len(active) == 1:
            desired = self.SOLO
        else:
            xs = [fp.x for fp in active]
            desired = self.SOLO if (max(xs) - min(xs)) < self._grp_spread_px else self.GROUP

        # Hysteresis: only commit to a state change after debounce threshold.
        if desired != self._state:
            self._hold_count += 1
            if self._hold_count >= self._hold_frames:
                self._state = desired
                self._hold_count = 0
        else:
            self._hold_count = max(0, self._hold_count - 2)

        # Compute target pan position and smoothing speed.
        if self._state == self.SOLO:
            src = active or valid
            tx = sum(fp.x for fp in src) // len(src) if src else self.vw // 2
            alpha = _ALPHA_SOLO
        elif self._state == self.GROUP:
            src = active or valid
            xs = [fp.x for fp in src]
            tx = (min(xs) + max(xs)) // 2 if xs else self.vw // 2
            alpha = _ALPHA_GROUP
        else:
            tx = self.vw // 2
            alpha = _ALPHA_BROLL

        # Clamp per-frame movement to prevent jarring jumps.
        raw_dx = int(alpha * (tx - self._smooth_x))
        self._smooth_x += max(-self._max_dx, min(self._max_dx, raw_dx))
        return self._crop_start()
