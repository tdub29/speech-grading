"""Tests for the repetition / false-start detector against the canonical fixture."""

from __future__ import annotations

from speech_grading.analysis.repetitions import detect_repetitions


def test_detects_immediate_repetitions(sample_transcript):
    rs = detect_repetitions(sample_transcript)
    assert len(rs) >= 2

    reps = [f for f in rs if f.kind == "repetition"]
    joined = " ".join(f.original.lower() for f in reps)
    # The fixture contains "the the" and "We, we".
    assert "the the" in joined or any("the" in f.original.lower() for f in reps)
    assert any("we" in f.original.lower() for f in reps)


def test_findings_are_sorted_by_start(sample_transcript):
    rs = detect_repetitions(sample_transcript)
    starts = [f.start for f in rs]
    assert starts == sorted(starts)


def test_repetition_spans_are_well_formed(sample_transcript):
    rs = detect_repetitions(sample_transcript)
    for f in rs:
        assert f.kind in {"repetition", "false_start"}
        assert f.source == "rule"
        a, b = f.resolved_span()
        assert a <= b
        assert f.start == sample_transcript.words[a].start
        assert f.end == sample_transcript.words[b].end


def test_single_token_repeats_present(sample_transcript):
    rs = detect_repetitions(sample_transcript)
    reps = [f for f in rs if f.kind == "repetition"]
    # Both "we" and "the" doubled tokens should be caught.
    lowered = [f.original.lower() for f in reps]
    assert any("we" in o for o in lowered)
    assert any("the" in o for o in lowered)
