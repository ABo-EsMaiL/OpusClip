import pytest

from opusclip.face_detection.smart_director import SmartDirector
from opusclip.face_detection.base import FaceResult


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
    def test_initial_state_is_broll(self, director_1080p):
        assert director_1080p.state == SmartDirector.BROLL

    def test_initial_crop_centred(self, director_1080p):
        crop = director_1080p.update([])
        assert crop == 420


class TestSmartDirectorSingleFace:
    def test_one_face_triggers_solo_after_debounce(self, director_1080p, face_centre):
        for _ in range(20):
            director_1080p.update([face_centre])
        assert director_1080p.state == SmartDirector.SOLO

    def test_crop_tracks_single_face(self, director_1080p):
        face = FaceResult(bbox=(800, 200, 400, 500), landmarks=[], mouth_open_score=0.8)
        for _ in range(30):
            director_1080p.update([face])
        crop = director_1080p.update([face])
        assert 0 <= crop <= 1920 - 1080

    def test_single_face_any_mouth_score(self, director_1080p):
        silent = FaceResult(bbox=(700, 200, 400, 500), landmarks=[], mouth_open_score=0.0)
        for _ in range(20):
            director_1080p.update([silent])
        assert director_1080p.state == SmartDirector.SOLO


class TestSmartDirectorMultipleFaces:
    def test_two_faces_triggers_group(self, director_1080p):
        left = FaceResult(bbox=(100, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        right = FaceResult(bbox=(1500, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_1080p.update([left, right])
        assert director_1080p.state == SmartDirector.GROUP

    def test_two_faces_any_mouth_score_triggers_group(self, director_1080p):
        left = FaceResult(bbox=(100, 200, 300, 400), landmarks=[], mouth_open_score=0.0)
        right = FaceResult(bbox=(1500, 200, 300, 400), landmarks=[], mouth_open_score=0.0)
        for _ in range(20):
            director_1080p.update([left, right])
        assert director_1080p.state == SmartDirector.GROUP


class TestSmartDirectorTransitions:
    def test_solo_to_broll_after_hold(self, director_1080p, face_centre):
        for _ in range(20):
            director_1080p.update([face_centre])
        assert director_1080p.state == SmartDirector.SOLO
        for _ in range(30):
            director_1080p.update([])
        assert director_1080p.state == SmartDirector.BROLL

    def test_broll_to_solo_needs_debounce(self, director_1080p, face_centre):
        director_1080p.update([face_centre])
        assert director_1080p.state == SmartDirector.BROLL

    def test_no_face_temporal_hold(self, director_1080p, face_centre):
        for _ in range(20):
            director_1080p.update([face_centre])
        assert director_1080p.state == SmartDirector.SOLO
        for _ in range(5):
            director_1080p.update([])
        assert director_1080p.state == SmartDirector.SOLO


class TestSmartDirectorSmallFaces:
    def test_tiny_face_ignored(self, director_1080p):
        tiny = FaceResult(bbox=(700, 200, 10, 10), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_1080p.update([tiny])
        assert director_1080p.state == SmartDirector.BROLL

    def test_large_face_accepted(self, director_1080p):
        large = FaceResult(bbox=(700, 200, 500, 600), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_1080p.update([large])
        assert director_1080p.state == SmartDirector.SOLO


class TestSmartDirectorZeroDivision:
    def test_no_crash_on_empty_faces_after_solo(self, director_1080p, face_centre):
        for _ in range(20):
            director_1080p.update([face_centre])
        for _ in range(40):
            crop = director_1080p.update([])
            assert 0 <= crop <= 1920 - 1080

    def test_no_crash_on_single_face_always(self, director_1080p, face_centre):
        for _ in range(30):
            crop = director_1080p.update([face_centre])
            assert 0 <= crop <= 1920 - 1080
