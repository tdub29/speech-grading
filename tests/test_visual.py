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


def test_pitch_deg_sign_convention():
    import math
    import numpy as np

    # Nodding up tilts head backwards towards +Y / away from -Z:
    # A negative rotation around X in MediaPipe metric 3D space.
    rad = math.radians(-15.0)
    rx = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, math.cos(rad), -math.sin(rad), 0.0],
        [0.0, math.sin(rad), math.cos(rad), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ])
    f = v.face_features(None, {}, rx)
    assert f["pitch_deg"] is not None
    assert round(f["pitch_deg"], 1) == 15.0


def test_empty_matrix_does_not_crash():
    import numpy as np

    assert v.face_features(None, {}, np.empty((0,)))["pitch_deg"] is None


def test_extract_frames_synthetic_video_has_no_face(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    vid = tmp_path / "shapes.mp4"
    writer = cv2.VideoWriter(str(vid), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (160, 120))
    for i in range(30):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        cv2.circle(frame, (20 + i * 4, 60), 15, (0, 255, 0), -1)
        writer.write(frame)
    writer.release()
    try:
        frames = v.extract_frames(vid)
    except v.VisualUnavailable:
        pytest.skip("mediapipe models not installed")
    assert 8 <= len(frames) <= 12  # 1s at 30fps sampled to 10fps
    assert all(f["face_visible"] is False for f in frames)
    assert [f["t"] for f in frames] == sorted(f["t"] for f in frames)
