"""Tests for speech_grading.analysis.pace against the sample_transcript fixture."""

from __future__ import annotations

from speech_grading.analysis.pace import compute_pace
from speech_grading.config import Config


def test_compute_pace_on_fixture(sample_transcript):
    ds = compute_pace(sample_transcript, Config().thresholds)

    # Dimension identity and contract.
    assert ds.dimension == "pace"
    assert ds.weight == 0.0
    assert ds.findings == []

    # Raw = overall WPM; the ~24s / 57-word monologue lands in a plausible range.
    assert 100 < ds.raw < 200
    assert ds.detail["wpm"] == ds.raw

    # Band is one of the allowed values.
    assert ds.band in {"excellent", "good", "fair", "poor"}

    # Detail surface is fully populated.
    assert "articulation_wpm" in ds.detail
    assert "consistency" in ds.detail
    assert "n_windows" in ds.detail

    # Articulation (silence removed) is at least as fast as overall pace.
    assert ds.detail["articulation_wpm"] >= ds.raw > 0

    # Consistency is a non-negative stdev; points are clamped to 0-100.
    assert ds.detail["consistency"] >= 0.0
    assert 0.0 <= ds.points <= 100.0
    assert ds.detail["n_windows"] >= 2


def test_zero_duration_is_safe():
    """A transcript with no words yields zero rates and no crash."""
    from speech_grading.schema import Transcript

    ds = compute_pace(Transcript(), Config().thresholds)
    assert ds.raw == 0.0
    assert ds.detail["articulation_wpm"] == 0.0
    assert ds.detail["consistency"] == 0.0
    assert ds.detail["n_windows"] == 0
    assert ds.band == "poor"
