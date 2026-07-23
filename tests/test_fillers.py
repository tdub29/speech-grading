"""Tests for speech_grading.analysis.fillers against the shared fixture."""

from __future__ import annotations

from speech_grading.analysis.fillers import detect_fillers
from speech_grading.config import Config


def test_detect_fillers_finds_expected(sample_transcript):
    t = sample_transcript
    findings = detect_fillers(t, Config().thresholds)

    # Fixture has 4 filled pauses (um/uh x... ), 'So' (sentence-initial),
    # 'Basically', and the 'you know' phrase -> at least 6 fillers.
    assert len(findings) >= 6

    # Every finding is a filler from the lexicon source.
    assert all(f.kind == "filler" for f in findings)
    assert all(f.source == "lexicon" for f in findings)

    # At least one filled-pause finding starts with 'um'.
    assert any(f.original.lower().startswith("um") for f in findings)

    # The 'you know' phrase is detected as a multiword span finding.
    you_know = [
        f
        for f in findings
        if f.span is not None and "you know" in f.original.lower()
    ]
    assert you_know, "expected a 'you know' phrase finding"
    assert you_know[0].span is not None


def test_findings_sorted_by_start(sample_transcript):
    findings = detect_fillers(sample_transcript, Config().thresholds)
    starts = [f.start for f in findings]
    assert starts == sorted(starts)


def test_pause_gating_upgrades_score(sample_transcript):
    """A filler preceded by a clear hesitation pause is upgraded to score 1.0."""
    findings = detect_fillers(sample_transcript, Config().thresholds)
    gated = [f for f in findings if "hesitation pause" in f.rationale.lower()]
    assert gated, "expected at least one pause-gated filler"
    assert all(f.score == 1.0 for f in gated)
