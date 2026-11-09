from types import SimpleNamespace as P

import pytest

from speech_grading.analysis import visual as v


def lm(x, y):
    return P(x=x, y=y)


def test_is_video():
    assert v.is_video("a.MP4") and not v.is_video("a.wav")


def test_face_features_blend_and_none_matrix():
    f = v.face_features(None, {"mouthSmileLeft": 0.4, "mouthSmileRight": 0.6, "eyeLookOutLeft": 0.9}, None)
    assert f["smile"] == 0.5 and f["gaze_off"] == 0.9 and f["pitch_deg"] is None and f["jaw_open"] is None


def test_hand_face_dist_normalised():
    face = {v._NOSE: lm(0.5, 0.5), v._CHIN: lm(0.5, 0.7), v._LEFT_FACE: lm(0.4, 0.5), v._RIGHT_FACE: lm(0.6, 0.5)}
    assert v.hand_face_dist(face, []) is None
    d = v.hand_face_dist(face, [[lm(0.5, 0.5)]])  # on the nose
    assert d == 0.0
    assert abs(v.hand_face_dist(face, [[lm(0.7, 0.5)]]) - 1.0) < 1e-9  # 0.2 away / 0.2 width


def test_missing_models_raise(tmp_path):
    with pytest.raises(v.VisualUnavailable):
        v.extract_frames(tmp_path / "x.mp4", models=tmp_path)
