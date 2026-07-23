"""Tests for the vocabulary (lexical-diversity) dimension."""

from __future__ import annotations

from speech_grading.analysis.vocabulary import compute_vocabulary
from speech_grading.schema import Transcript, Word


def test_vocabulary_on_sample(sample_transcript):
    ds = compute_vocabulary(sample_transcript)

    assert ds.dimension == "vocabulary"
    # MATTR is a ratio in (0, 1]; the sample has real lexical variety.
    assert 0 < ds.raw <= 1.0
    assert ds.detail["total"] > 0
    assert ds.band in {"excellent", "good", "fair", "poor"}

    # raw mirrors MATTR; bands and points are internally consistent.
    assert ds.detail["mattr"] == ds.raw
    assert ds.weight == 0.0
    assert ds.findings == []
    assert 0 <= ds.detail["ttr"] <= 1.0
    assert ds.detail["unique"] <= ds.detail["total"]
    assert ds.detail["mtld"] >= 0.0
    assert 0 <= ds.points <= 100


def test_vocabulary_excludes_filled_pauses_and_punctuation():
    # Two filled pauses + a bare-punctuation token must not count toward totals.
    words = [
        Word(text="So,", start=0.0, end=0.2, normalized="so"),
        Word(text="um", start=0.2, end=0.6, is_filled_pause=True, normalized="um"),
        Word(text="hello", start=0.6, end=1.0, normalized="hello"),
        Word(text="world", start=1.0, end=1.4, normalized="world"),
    ]
    t = Transcript(words=words)
    ds = compute_vocabulary(t)
    # so / hello / world -> 3 lexical tokens, all unique.
    assert ds.detail["total"] == 3
    assert ds.detail["unique"] == 3
    assert ds.detail["ttr"] == 1.0


def test_vocabulary_empty_transcript_is_guarded():
    ds = compute_vocabulary(Transcript(words=[]))
    assert ds.detail["total"] == 0
    assert ds.raw == 0.0
    assert ds.band in {"excellent", "good", "fair", "poor"}
    assert ds.findings == []
