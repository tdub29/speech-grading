"""Tests for the deterministic offline word-choice analyzer and tripped-up fusion."""

from __future__ import annotations

from speech_grading.config import Config
from speech_grading.wordchoice.offline import (
    OfflineWordChoice,
    detect_tripped_up,
    rank_replacement,
)


def test_detect_tripped_up_requires_co_occurring_signal(sample_transcript):
    findings = detect_tripped_up(sample_transcript)
    # The planted stumble (long pause + low confidence + filler before 'utilize').
    words = sample_transcript.words
    hits = {words[f.word_index].normalized for f in findings}
    assert "utilize" in hits
    assert all(f.kind == "tripped_up" and 0.0 < f.score <= 1.0 for f in findings)


def test_rank_replacement_curated_and_wordnet():
    assert rank_replacement("utilize") == "use"        # curated map
    assert rank_replacement("in order to") == "to"      # curated phrase-free token? n/a
    # An out-of-map word returns either a stronger WordNet synonym or None (never raises).
    assert rank_replacement("zzzznotaword") is None


def test_offline_analyzer_emits_interchangeable_schema(sample_transcript):
    findings = OfflineWordChoice(Config()).analyze(sample_transcript)
    assert findings, "expected some word-choice findings"
    issue_types = {f.issue_type for f in findings}
    assert issue_types <= {"weak", "hedge", "filler", "tripped_up"}
    # Every finding validates against the shared schema fields.
    for f in findings:
        assert isinstance(f.word_index, int)
        assert 0.0 <= f.confidence <= 1.0
    # The tripped-up suggestion for 'utilize' should be present and strong.
    util = [f for f in findings if f.issue_type == "tripped_up" and "utilize" in f.original.lower()]
    assert util and util[0].suggestion == "use"
