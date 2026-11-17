"""Tests for pace drift across the talk."""

from speech_grading.analysis.pace import pace_drift_wpm


def test_pace_drift_wpm_worked_example():
    assert pace_drift_wpm([120.0, 130.0, 150.0, 160.0]) == 30.0


def test_pace_drift_wpm_short_and_steady():
    assert pace_drift_wpm([]) == 0.0
    assert pace_drift_wpm([145.0]) == 0.0
    assert pace_drift_wpm([140.0, 140.0, 140.0, 140.0]) == 0.0


def test_pace_drift_wpm_odd_length_slowing_down():
    # mid = 1 -> first_half = [160.0], second_half = [140.0, 120.0] (mean 130.0)
    assert pace_drift_wpm([160.0, 140.0, 120.0]) == -30.0


def test_pace_drift_wpm_in_report_metrics(sample_transcript, tmp_path):
    from speech_grading.analysis.pace import _window_wpms
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.report import render_html

    cfg = Config()
    report = run_on_transcript(sample_transcript, cfg)
    expected = pace_drift_wpm(_window_wpms(sample_transcript, cfg.thresholds["wpm_window_sec"]))
    assert report.metrics["pace_drift_wpm"] == expected
    out_html = tmp_path / "r.html"
    render_html(report, str(out_html))
    assert "pace_drift_wpm" in out_html.read_text(encoding="utf-8")
