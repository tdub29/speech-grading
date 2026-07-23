"""Tests for the readability analysis dimension."""

from __future__ import annotations

from speech_grading.analysis.readability import compute_readability
from speech_grading.schema import DimensionScore


def test_readability_basic_shape(sample_transcript):
    ds = compute_readability(sample_transcript)
    assert isinstance(ds, DimensionScore)
    assert ds.dimension == "readability"
    assert isinstance(ds.raw, (int, float))
    assert "flesch_reading_ease" in ds.detail
    assert ds.band in {"excellent", "good", "fair", "poor"}


def test_readability_detail_keys_and_relative_tracking(sample_transcript):
    ds = compute_readability(sample_transcript)
    # All four metrics are reported in detail.
    for key in ("flesch_reading_ease", "flesch_kincaid_grade", "smog_index", "gunning_fog"):
        assert key in ds.detail
        assert isinstance(ds.detail[key], (int, float))
    # raw mirrors the Flesch-Kincaid grade level.
    assert ds.raw == ds.detail["flesch_kincaid_grade"]
    # Relative-tracking dimension: zero weight, no findings, gently scored (never poor).
    assert ds.weight == 0.0
    assert ds.findings == []
    assert ds.band != "poor"
    assert ds.points >= 80.0


def test_readability_handles_empty_transcript():
    from speech_grading.schema import Transcript

    ds = compute_readability(Transcript())
    assert isinstance(ds.raw, (int, float))
    assert ds.band in {"excellent", "good", "fair", "poor"}
    assert "flesch_reading_ease" in ds.detail
