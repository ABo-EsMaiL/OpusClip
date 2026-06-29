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
def speaking_face_centre() -> FaceResult:
    return FaceResult(bbox=(700, 200, 400, 500), landmarks=[], mouth_open_score=0.8)


@pytest.fixture
def non_speaking_face_centre() -> FaceResult:
    return FaceResult(bbox=(700, 200, 400, 500), landmarks=[], mouth_open_score=0.0)


class TestSmartDirectorInitialState:
    def test_initial_state_is_broll(self, director_1080p):
        assert director_1080p.state == SmartDirector.BROLL

    def test_initial_crop_centred(self, director_1080p):
        crop = director_1080p.update([])
        assert crop == 420


class TestSmartDirectorSingleFace:
    def test_speaker_triggers_solo_after_debounce(self, director_1080p, speaking_face_centre):
        for _ in range(20):
            director_1080p.update([speaking_face_centre])
        assert director_1080p.state == SmartDirector.SOLO

    def test_non_speaker_stays_in_broll(self, director_1080p, non_speaking_face_centre):
        for _ in range(30):
            director_1080p.update([non_speaking_face_centre])
        assert director_1080p.state == SmartDirector.BROLL

    def test_crop_tracks_speaking_face(self, director_1080p):
        face = FaceResult(bbox=(800, 200, 400, 500), landmarks=[], mouth_open_score=0.8)
        for _ in range(30):
            director_1080p.update([face])
        crop = director_1080p.update([face])
        assert 0 <= crop <= 1920 - 1080


class TestSmartDirectorMultipleFaces:
    def test_two_speakers_groups_when_wide(self, director_1080p):
        left = FaceResult(bbox=(100, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        right = FaceResult(bbox=(1500, 200, 300, 400), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_1080p.update([left, right])
        assert director_1080p.state == SmartDirector.GROUP

    def test_two_close_speakers_stays_solo(self, director_1080p):
        left = FaceResult(bbox=(500, 200, 200, 300), landmarks=[], mouth_open_score=0.8)
        right = FaceResult(bbox=(750, 200, 200, 300), landmarks=[], mouth_open_score=0.8)
        for _ in range(20):
            director_1080p.update([left, right])
        assert director_1080p.state == SmartDirector.SOLO

    def test_mixed_speaking_non_speaking(self, director_1080p):
        speaking = FaceResult(bbox=(500, 200, 200, 300), landmarks=[], mouth_open_score=0.8)
        silent = FaceResult(bbox=(800, 200, 200, 300), landmarks=[], mouth_open_score=0.0)
        for _ in range(20):
            director_1080p.update([speaking, silent])
        assert director_1080p.state == SmartDirector.SOLO


class TestSmartDirectorTransitions:
    def test_solo_to_broll_and_back(self, director_1080p, speaking_face_centre):
        for _ in range(20):
            director_1080p.update([speaking_face_centre])
        assert director_1080p.state == SmartDirector.SOLO
        for _ in range(30):
            director_1080p.update([])
        assert director_1080p.state == SmartDirector.BROLL

    def test_broll_to_solo_needs_debounce(self, director_1080p, speaking_face_centre):
        director_1080p.update([speaking_face_centre])
        assert director_1080p.state == SmartDirector.BROLL


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