"""Tests for SmartDirector v2.1-style logic with active speaker detection."""

import pytest

from opusclip.face_detection.smart_director import SmartDirector
from opusclip.face_detection.base import FaceResult


# Fixture with speaking_mar=0 so ALL faces are considered active speakers
@pytest.fixture
def director_no_mar() -> SmartDirector:
    return SmartDirector(
        vid_w=1920,
        vid_h=1080,
        src_crop_w=1080,
        fps=30.0,
        speaking_mar=0.0,
        min_face_area=0.003,
        debounce_s=0.3,
    )


# Fixture with realistic MAR threshold
@pytest.fixture
def director_1080p() -> SmartDirector:
    return SmartDirector(
        vid_w=1920,
        vid_h=1080,
        src_crop_w=1080,
        fps=30.0,
        speaking_mar=0.3,
        min_face_area=0.003,
        debounce_s=0.3,
    )


@pytest.fixture
def face_centre() -> FaceResult:
    return FaceResult(bbox=(700, 200, 400, 500), landmarks=[], mouth_open_score=0.8)


class TestSmartDirectorInitialState:
    def test_initial_state_is_broll(self, director_no_mar):
        assert director_no_mar.state == SmartDirector.BROLL

    def test_initial_crop_centred(self, director_no_mar):
        crop = director_no_mar.update([])
        assert crop == 420


class TestSmartDirectorSingleFace:
    def test_one_face_triggers_solo_after_debounce(self, director_no_mar, face_centre):
        for _ in range(20):
            director_no_mar.update([face_centre])
        assert director_no_mar.state == SmartDirector.SOLO

    def test_crop_tracks_single_face(self, director_no_mar):
        face = FaceResult(bbox=(800, 200, 400, 500), landmarks=[], mouth_open_score=0.8)
        for _ in range(30):
            director_no_mar.update([face])
        crop = director_no_mar.update([face])
        assert 0 <= crop <= 1920 - 1080

    def test_single_face_any_mouth_score(self, director_1080p):
        """Face with low mouth_open_score should not trigger SOLO (no active speaker)."""
        silent = FaceResult(bbox=(700, 200, 400, 500), landmarks=[], mouth_open_score=0.0)
        for _ in range(20):
            director_1080p.update([silent])
        # No active speaker -> keep current state (BROLL)
        assert director_1080p.state == SmartDirector.BROLL


class TestSmartDirectorMultipleFaces:
    def test_two_active_faces_triggers_group(self, director_no_mar):
        """Two faces with spread > GRP_SPREAD (0.55*1080=594) -> GROUP."""
        left = FaceResult(bbox=(100, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        right = FaceResult(bbox=(1500, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_no_mar.update([left, right])
        assert director_no_mar.state == SmartDirector.GROUP

    def test_two_faces_close_together_stay_solo(self, director_no_mar):
        """Two faces close together should stay in SOLO mode."""
        left = FaceResult(bbox=(400, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        right = FaceResult(bbox=(700, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_no_mar.update([left, right])
        assert director_no_mar.state == SmartDirector.SOLO

    def test_two_faces_low_mouth_score_stay_broll(self, director_1080p):
        """No active speakers -> keep current state."""
        left = FaceResult(bbox=(100, 200, 300, 400), landmarks=[], mouth_open_score=0.0)
        right = FaceResult(bbox=(1500, 200, 300, 400), landmarks=[], mouth_open_score=0.0)
        for _ in range(20):
            director_1080p.update([left, right])
        assert director_1080p.state == SmartDirector.BROLL


class TestSmartDirectorTransitions:
    def test_solo_to_broll_after_hold(self, director_no_mar, face_centre):
        for _ in range(20):
            director_no_mar.update([face_centre])
        assert director_no_mar.state == SmartDirector.SOLO
        for _ in range(30):
            director_no_mar.update([])
        assert director_no_mar.state == SmartDirector.BROLL

    def test_broll_to_solo_needs_debounce(self, director_no_mar, face_centre):
        director_no_mar.update([face_centre])
        assert director_no_mar.state == SmartDirector.BROLL

    def test_solo_stays_during_brief_no_face(self, director_no_mar, face_centre):
        for _ in range(20):
            director_no_mar.update([face_centre])
        assert director_no_mar.state == SmartDirector.SOLO
        for _ in range(5):
            director_no_mar.update([])
        assert director_no_mar.state == SmartDirector.SOLO


class TestSmartDirectorSmallFaces:
    def test_tiny_face_ignored(self, director_no_mar):
        tiny = FaceResult(bbox=(700, 200, 10, 10), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_no_mar.update([tiny])
        assert director_no_mar.state == SmartDirector.BROLL

    def test_large_face_accepted(self, director_no_mar):
        large = FaceResult(bbox=(700, 200, 500, 600), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_no_mar.update([large])
        assert director_no_mar.state == SmartDirector.SOLO


class TestSmartDirectorZeroDivision:
    def test_no_crash_on_empty_faces_after_solo(self, director_no_mar, face_centre):
        for _ in range(20):
            director_no_mar.update([face_centre])
        for _ in range(40):
            crop = director_no_mar.update([])
            assert 0 <= crop <= 1920 - 1080

    def test_no_crash_on_single_face_always(self, director_no_mar, face_centre):
        for _ in range(30):
            crop = director_no_mar.update([face_centre])
            assert 0 <= crop <= 1920 - 1080


class TestSmartDirectorGroupCenter:
    def test_group_centers_between_active_faces(self, director_no_mar):
        """GROUP mode: tx = (min(x) + max(x)) // 2 of active faces."""
        face1 = FaceResult(bbox=(200, 300, 100, 120), landmarks=[], mouth_open_score=0.5)
        face2 = FaceResult(bbox=(1400, 300, 100, 120), landmarks=[], mouth_open_score=0.5)

        # face1 center = 250, face2 center = 1450
        # spread = 1200 > 594 (GRP_SPREAD of 1080*0.55) -> GROUP
        # tx = (250 + 1450) // 2 = 850
        for _ in range(20):
            director_no_mar.update([face1, face2])
        assert director_no_mar.state == SmartDirector.GROUP

        # Run more frames for smoothing convergence
        for _ in range(100):
            crop = director_no_mar.update([face1, face2])

        # With float smoothing, smooth_x should converge close to 850
        # crop_start = 850 - 1080//2 = 850 - 540 = 310
        # Allow tolerance for float smoothing convergence
        assert 300 <= crop <= 320
