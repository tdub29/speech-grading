from speech_grading.analysis import visual_events as v


def fr(t, **kw):
    d = dict(t=t, smile=0.1, brow_raise=0, brow_furrow=0, jaw_open=0, gaze_off=0.0,
             pitch_deg=0.0, hand_face_dist=None, wrist_y_rel=None, face_visible=True)
    d.update(kw)
    return d


def series(n, **kw):
    return [fr(i * 0.1, **kw) for i in range(n)]


def test_baseline_and_quality():
    b = v.baseline(series(400, smile=0.2, pitch_deg=2.0))
    assert abs(b["smile"] - 0.2) < 1e-9 and b["pitch_deg"] == 2.0
    q = v.data_quality([fr(0), fr(0.1, face_visible=False)])
    assert q["face_visible_pct"] == 50.0 and q["hands_visible_pct"] == 0.0


def test_face_touch_needs_min_duration():
    short = [fr(i * 0.1, hand_face_dist=0.05) for i in range(3)]  # 0.2s
    long = [fr(i * 0.1, hand_face_dist=0.05) for i in range(8)]   # 0.7s
    assert v.detect_face_touch(short) == []
    out = v.detect_face_touch(long)
    assert len(out) == 1 and out[0].kind == "face_touch"


def test_two_separate_touches_are_two_findings():
    a = [fr(i * 0.1, hand_face_dist=0.05) for i in range(6)]
    gap = [fr(0.6 + i * 0.1, hand_face_dist=0.5) for i in range(10)]
    b = [fr(1.6 + i * 0.1, hand_face_dist=0.05) for i in range(6)]
    assert len(v.detect_face_touch(a + gap + b)) == 2


def test_chin_up_vs_baseline_and_none_pitch():
    frames = [fr(i * 0.1, pitch_deg=12.0) for i in range(15)]
    assert len(v.detect_chin_up(frames, {"pitch_deg": 0.0})) == 1
    assert v.detect_chin_up(frames, {}) == []
    assert v.detect_chin_up([fr(0, pitch_deg=None)], {"pitch_deg": 0.0}) == []


def test_auto_smile_and_reaction_check():
    frames = [fr(i * 0.1, smile=0.1 if i < 10 else 0.6, gaze_off=0.9 if i >= 10 else 0.0)
              for i in range(30)]
    assert len(v.smile_after_sentence(frames, [1.0], {"smile": 0.1})) == 1
    assert v.smile_after_sentence(frames, [0.0], {"smile": 0.1}) == []
    assert len(v.gaze_check_after_sentence(frames, [1.0])) == 1
    assert v.gaze_check_after_sentence(frames, [0.0]) == []


def test_summarize_modes_and_gates():
    frames = [fr(i * 0.1, hand_face_dist=0.05 if 10 <= i < 40 else None) for i in range(100)]
    phone = v.summarize(frames, [], "phone")
    assert phone["findings"] and phone["rates_per_min"]["face_touch"] > 0
    nohands = v.summarize(series(100), [], "phone")
    assert "face_touch" in nohands["skipped"]
    assert "reaction_check" not in v.summarize(frames, [1.0], "zoom")["skipped"]
    dark = v.summarize([fr(i * 0.1, face_visible=False) for i in range(50)], [], "stage")
    assert dark["findings"] == [] and dark["skipped"]


def test_feature_rows_windows():
    rows = v.feature_rows(series(120), win=5.0, mode="stage")
    assert len(rows) == 3 and rows[0]["mode"] == "stage" and rows[0]["n"] == 50
