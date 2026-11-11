from speech_grading.analysis import visual_events as v


def fr(t, **kw):
    d = dict(t=t, smile=0.1, brow_raise=0, brow_furrow=0, jaw_open=0, gaze_off=0.0,
             pitch_deg=0.0, hand_face_dist=None, face_visible=True)
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


def test_end_sentence_smile():
    frames = [fr(i * 0.1, smile=0.1 if i < 10 else 0.6, gaze_off=0.9 if i >= 10 else 0.0)
              for i in range(30)]
    assert len(v.smile_after_sentence(frames, [1.0], {"smile": 0.1})) == 1
    assert v.smile_after_sentence(frames, [0.0], {"smile": 0.1}) == []
    assert v.smile_after_sentence(frames, [1.0], {"smile": 0.1})[0].kind == "end_sentence_smile"


def test_summarize_modes_and_gates():
    frames = [fr(i * 0.1, hand_face_dist=0.05 if 10 <= i < 40 else 0.5) for i in range(700)]
    phone = v.summarize(frames, [], "phone")
    assert phone["findings"] and phone["rates_per_min"]["face_touch"] > 0
    short = v.summarize(frames[:100], [], "phone")
    assert short["counts"]["face_touch"] == 1 and short["rates_per_min"] == {}
    nohands = v.summarize(series(100), [], "phone")
    assert "face_touch" in nohands["skipped"]
    gaze_away = [fr(i * 0.1, gaze_off=0.9 if i >= 10 else 0.0) for i in range(700)]
    s = v.summarize(gaze_away, [1.0], "default")
    assert "reaction_check" not in s["counts"]  # glancing away at turn end is never a fault
    assert s["gaze_on_camera_pct"] == round(100 * 10 / 700, 1)
    dark = v.summarize([fr(i * 0.1, face_visible=False) for i in range(50)], [], "stage")
    assert dark["findings"] == [] and dark["skipped"]


def test_feature_rows_windows():
    rows = v.feature_rows(series(120), win=5.0, mode="stage")
    assert len(rows) == 3 and rows[0]["mode"] == "stage" and rows[0]["n"] == 50



def test_baseline_needs_ten_seconds_of_face():
    assert v.baseline(series(50, pitch_deg=2.0)) == {}  # 5s of face
    s = v.summarize(series(50, pitch_deg=2.0), [], "default")
    assert "end_sentence_smile" in s["skipped"]
    assert "camera height" in s["skipped"]["chin_up"]
    assert "baseline" in v.summarize(series(50, pitch_deg=2.0), [], "default", camera_level=True)["skipped"]["chin_up"]


def test_chin_up_runs_only_with_camera_level():
    frames = [fr(i * 0.1, pitch_deg=0.0 if i < 300 else 15.0) for i in range(700)]
    assert "chin_up" not in v.summarize(frames, [], "default")["counts"]
    assert v.summarize(frames, [], "default", camera_level=True)["counts"]["chin_up"] == 1


def test_baseline_median_ignores_early_spike():
    frames = series(200, pitch_deg=0.0)
    for f in frames[:20]:
        f["pitch_deg"] = 40.0
    assert v.baseline(frames)["pitch_deg"] == 0.0


def test_speaking_sec_is_rate_denominator():
    frames = [fr(i * 0.1, hand_face_dist=0.05 if 10 <= i < 40 else 0.5) for i in range(1200)]
    full = v.summarize(frames, [], "phone")["rates_per_min"]["face_touch"]
    spk = v.summarize(frames, [], "phone", speaking_sec=60.0)["rates_per_min"]["face_touch"]
    assert spk == 1.0 and full < spk


def test_no_frames_reports_reason():
    assert "no video frames" in next(iter(v.summarize([], [], "default")["skipped"].values()))


def test_smile_rise_is_per_mode():
    # 0.28 rise after a sentence: counts under default (0.25), not under phone (0.30)
    frames = [fr(i * 0.1, smile=0.38 if 50 <= i <= 55 else 0.1) for i in range(150)]
    assert v.summarize(frames, [5.0], "default")["counts"].get("end_sentence_smile") == 1
    assert "end_sentence_smile" not in v.summarize(frames, [5.0], "phone")["counts"]
