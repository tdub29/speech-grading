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



def test_count_syllables_and_articulation_sps():
    from speech_grading.analysis.pace import articulation_sps, count_syllables
    from speech_grading.schema import Transcript, Word, derive_transcript_fields

    assert [count_syllables(w) for w in ("cat", "table", "make", "beautiful", "the", "123")] == [1, 2, 1, 3, 1, 0]
    words = [Word(text="hello", start=0.0, end=0.5), Word(text="world", start=0.5, end=1.0),
             Word(text="again", start=2.0, end=2.5)]
    t = derive_transcript_fields(Transcript(words=words))
    # 5 syllables over 2.5s total minus the 1.0s pause = 1.5s
    assert articulation_sps(t) == round(5 / 1.5, 3)


def test_applause_gap_does_not_slow_pace(sample_transcript):
    """A 30s applause break mid-speech leaves listener pace unchanged."""
    base = compute_pace(sample_transcript, Config().thresholds).raw
    t = sample_transcript.model_copy(deep=True)
    for w in t.words[20:]:
        w.start += 30.0
        w.end += 30.0
    t.duration_sec += 30.0
    ds = compute_pace(t, Config().thresholds)
    assert abs(ds.raw - base) / base < 0.15
    assert ds.detail["wall_clock_wpm"] < ds.raw * 0.6
