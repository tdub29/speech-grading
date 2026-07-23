"""Tests for speech_grading.analysis.weak_words against the shared fixture."""

from __future__ import annotations

from speech_grading.analysis.weak_words import detect_weak_words
from speech_grading.schema import Finding


def test_detect_weak_words_fixture(sample_transcript):
    ws = detect_weak_words(sample_transcript)
    originals = [f.original.lower() for f in ws]

    # Intensifier and hedge single tokens are surfaced.
    assert any("really" in o for o in originals)
    assert any("maybe" in o for o in originals)

    # 'utilize' is a weak word with a concrete replacement.
    util = [f for f in ws if "utilize" in f.original.lower()]
    assert util and util[0].suggestion == "use"

    # Every finding uses one of the owned kinds.
    assert all(f.kind in {"hedge", "weasel", "intensifier", "weak_word"} for f in ws)


def test_returns_findings_sorted_by_start(sample_transcript):
    ws = detect_weak_words(sample_transcript)
    assert all(isinstance(f, Finding) for f in ws)
    starts = [f.start for f in ws]
    assert starts == sorted(starts)


def test_excludes_pure_filler_tokens_and_phrases(sample_transcript):
    ws = detect_weak_words(sample_transcript)
    originals = [f.original.lower().strip(",. ") for f in ws]
    # Filled pauses and filler-only discourse markers must NOT appear here.
    assert not any(o in {"um", "uh"} for o in originals)
    assert "basically" not in originals
    # 'you know' is filler-only -> excluded.
    assert not any("you know" in o for o in originals)


def test_phrase_hedges_and_weak_verb(sample_transcript):
    ws = detect_weak_words(sample_transcript)
    originals = [f.original.lower() for f in ws]
    # 'I think' is a hedge phrase; 'I guess' carries a hedge tag too.
    assert any("i think" in o for o in originals)
    assert any("i guess" in o for o in originals)
    # Weasel placeholder noun and weak adjective.
    assert any(o.strip(",. ") == "thing" for o in originals)
    assert any(o.strip(",. ") == "good" for o in originals)
