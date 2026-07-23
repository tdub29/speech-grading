"""Tests for the pause-analysis module against the canonical sample fixture."""

from __future__ import annotations

from speech_grading.analysis.pauses import detect_pauses
from speech_grading.config import Config


def test_detect_pauses_flags_midclause_long_pause(sample_transcript):
    ps = detect_pauses(sample_transcript, Config().thresholds)

    # At least one long pause is detected, and every finding is a long_pause.
    assert len(ps) >= 1
    assert all(f.kind == "long_pause" for f in ps)

    # A mid-clause long pause is surfaced with the awkward-hesitation rationale.
    assert any(f.rationale and "mid-clause" in f.rationale for f in ps)

    # The largest gap sits right before the weak verb 'utilize'.
    largest = max(ps, key=lambda f: f.end - f.start)
    assert sample_transcript.words[largest.word_index].normalized == "utilize"


def test_detect_pauses_sorted_and_well_formed(sample_transcript):
    thresholds = Config().thresholds
    ps = detect_pauses(sample_transcript, thresholds)

    # Findings are sorted by start time.
    assert ps == sorted(ps, key=lambda f: f.start)

    pause_long = thresholds["pause_long"]
    for f in ps:
        # Every flagged gap genuinely exceeds the long-pause threshold.
        gap = f.end - f.start
        assert gap > pause_long
        # Span boundaries match the surrounding words' timing.
        i = f.word_index
        assert f.start == sample_transcript.words[i - 1].end
        assert f.end == sample_transcript.words[i].start
        assert f.original == "(pause %.2fs)" % gap
        # Scores stay within the documented 0-1 range.
        assert 0.0 < f.score <= 1.0
