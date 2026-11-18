"""Regression coverage for measurement validity, not invented optimal bands."""

import pytest

from speech_grading.analysis.pace import _window_wpms, compute_pace
from speech_grading.config import Config
from speech_grading.group import group_metrics
from speech_grading.schema import Transcript, Word, derive_transcript_fields
from speech_grading.scorer import score


def _steady_words():
    return [Word(text="word", start=i * 0.5, end=(i + 1) * 0.5) for i in range(50)]


def test_partial_window_uses_observed_duration():
    t = derive_transcript_fields(Transcript(words=_steady_words()))
    # Each 10-second window and the final 5-second window contain 120 WPM.
    assert _window_wpms(t, 10.0) == pytest.approx([120.0, 120.0, 120.0])
    ds = compute_pace(t, Config().thresholds)
    assert ds.detail["consistency"] == pytest.approx(0.0)
    assert ds.detail["pace_drift_wpm"] == pytest.approx(0.0)


def test_partial_windows_use_each_turn_duration():
    t = derive_transcript_fields(Transcript(words=_steady_words()))
    # End the first turn after 12.5 seconds. The listening gap is not a window.
    for w in t.words[25:]:
        w.start += 10.0
        w.end += 10.0
    t.turn_starts = [0, 25]
    assert _window_wpms(t, 10.0) == pytest.approx([120.0] * 4)


def test_single_channel_cannot_establish_uninterrupted_streak():
    t = derive_transcript_fields(Transcript(words=[
        Word(text="A", speaker="Alice", start=0.0, end=2.0),
        Word(text="B", speaker="Bob", start=3.0, end=5.0),
        Word(text="C", speaker="Alice", start=6.0, end=8.0),
    ]))
    unavailable = group_metrics(t, overlap=False)
    assert all(p["interruption_free_streak"] is None for p in unavailable["per_speaker"].values())
    observable = group_metrics(t, overlap=True)
    assert observable["per_speaker"]["Alice"]["interruption_free_streak"] == 2
    assert observable["per_speaker"]["Bob"]["interruption_free_streak"] == 1


def test_report_identifies_unvalidated_quality_rubric():
    report = score(Transcript(), [], [], Config())
    assert report.metadata["rubric_status"] == "uncalibrated_heuristic"
    assert report.metadata["rubric_evidence"] == "docs/evidence-map.md"
