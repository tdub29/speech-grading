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
    face = {v._NOSE: lm(0.5, 0.5), v._CHIN: lm(0.5, 0.7), v._LEFT_FACE: lm(0.4, 0.5), v._RIGHT_FACE: lm(0.6, 0.5), v._TOP: lm(0.5, 0.55)}
    assert v.hand_face_dist(face, []) is None
    d = v.hand_face_dist(face, [[lm(0.5, 0.9), lm(0.5, 0.5)]])  # wrist below chin, finger on the nose
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


def test_hand_face_dist_turned_head_and_wide_frame():
    turned = {v._NOSE: lm(0.5, 0.5), v._CHIN: lm(0.5, 0.7), v._LEFT_FACE: lm(0.48, 0.5),
              v._RIGHT_FACE: lm(0.52, 0.5), v._TOP: lm(0.5, 0.3)}
    # width collapses to 0.04 on a head turn; height (0.4) keeps the scale sane
    assert abs(v.hand_face_dist(turned, [[lm(0.7, 0.5)]]) - 0.5) < 1e-9
    face = {v._NOSE: lm(0.5, 0.5), v._CHIN: lm(0.5, 0.7), v._LEFT_FACE: lm(0.4, 0.5),
            v._RIGHT_FACE: lm(0.6, 0.5), v._TOP: lm(0.5, 0.55)}
    # 16:9 frame: horizontal offsets scale with width/height on both sides of the ratio
    assert abs(v.hand_face_dist(face, [[lm(0.7, 0.5)]], aspect=16 / 9) - 1.0) < 1e-9


def test_gaze_pairs_by_direction():
    looking_right = {"eyeLookOutRight": 0.9, "eyeLookInLeft": 0.9, "eyeLookInRight": 0.0, "eyeLookOutLeft": 0.0}
    assert v.face_features(None, looking_right, None)["gaze_off"] == 0.9


def test_av_offset_shifts_sentence_ends(monkeypatch, sample_transcript):
    from speech_grading import pipeline
    from speech_grading.analysis import visual_events
    from speech_grading.cli import _build_parser, _config_from_args

    cfg = _config_from_args(_build_parser().parse_args(["x.mp4", "--av-offset", "1.5"]))
    assert cfg.av_offset_sec == 1.5
    seen = {}

    def fake(frames, ends, *a, **k):
        seen["ends"] = ends
        return {"findings": []}
    monkeypatch.setattr(v, "extract_frames", lambda p: [])
    monkeypatch.setattr(visual_events, "summarize", fake)
    rep = pipeline.run_on_transcript(sample_transcript, cfg)
    pipeline.add_visual(rep, sample_transcript, "x.mp4", cfg)
    t = sample_transcript
    assert seen["ends"] == [t.words[e].end + 1.5 for _, e in t.sentences if 0 <= e < len(t.words)]
    assert seen["ends"]


def test_hand_entirely_inside_face_is_rejected():
    face = {v._NOSE: lm(0.5, 0.5), v._CHIN: lm(0.5, 0.7), v._LEFT_FACE: lm(0.4, 0.5), v._RIGHT_FACE: lm(0.6, 0.5), v._TOP: lm(0.5, 0.3)}
    assert v.hand_face_dist(face, [[lm(0.45, 0.4), lm(0.55, 0.6)]]) is None  # detector false positive on the face


def test_face_crops_and_box():
    assert list(v._face_crops(1920, 1080, (1, 2, 3, 3))) == [(1, 2, 3, 3)]
    grid = list(v._face_crops(1920, 1080, None))
    assert len(grid) == 9 and grid[-1] == (1920 - 540, 1080 - 540, 540, 540)
    x, y, w, h = v._box_around([lm(0.5, 0.5), lm(0.52, 0.54)], 1000, 1000)
    assert w == h == 120 and x <= 500 and x + w >= 520 and y <= 500 and y + h >= 540
    assert v._box_around([lm(0.0, 0.0), lm(0.01, 0.01)], 1000, 1000)[:2] == (0, 0)  # clamped to frame


def test_pose_features_tilt_and_hidden_shoulder():
    pts = [P(x=0.5, y=0.5, visibility=0.9) for _ in range(33)]
    pts[11], pts[12] = P(x=0.6, y=0.5, visibility=0.9), P(x=0.4, y=0.5, visibility=0.9)
    f = v.pose_features(pts)
    assert abs(f["sh_w"] - 0.2) < 1e-9 and abs(f["sh_tilt_deg"]) < 1e-9 and f["sh_mid_x"] == 0.5
    pts[12] = P(x=0.4, y=0.5, visibility=0.1)
    assert v.pose_features(pts) is None
