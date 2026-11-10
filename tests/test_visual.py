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


def test_extract_frames_synthetic_video(tmp_path):
    import math
    import struct
    import subprocess
    import wave
    import cv2
    import numpy as np
    from speech_grading.pipeline import find_ffmpeg

    vid_raw = tmp_path / "raw.mp4"
    audio_raw = tmp_path / "audio.wav"
    muxed_mp4 = tmp_path / "synthetic.mp4"

    # 15 frames at 10 fps with moving shape
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(vid_raw), fourcc, 10.0, (320, 240))
    for i in range(15):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (40 + i * 15, 120), 20, (0, 255, 0), -1)
        writer.write(frame)
    writer.release()

    # Audio sine wave
    with wave.open(str(audio_raw), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        for i in range(24000):  # 1.5s
            val = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * 440.0 * i / 16000))
            wf.writeframes(struct.pack("<h", val))

    ffmpeg = find_ffmpeg()
    target_video = vid_raw
    if ffmpeg:
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(vid_raw), "-i", str(audio_raw),
               "-c:v", "copy", "-c:a", "aac", str(muxed_mp4)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            target_video = muxed_mp4

    try:
        frames = v.extract_frames(target_video)
        assert len(frames) > 0
        assert "face_visible" in frames[0]
        assert "t" in frames[0]
    except v.VisualUnavailable:
        pytest.skip("Visual dependencies or models not available in this environment")
