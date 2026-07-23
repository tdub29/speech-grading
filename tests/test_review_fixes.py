"""Regression tests for the four verified fixes from the adversarial review pass."""

from __future__ import annotations

from speech_grading.analysis.repetitions import detect_repetitions
from speech_grading.asr.base import normalize_confidence
from speech_grading.config import Config
from speech_grading.lexicons import is_context_filler
from speech_grading.schema import Transcript, Word, derive_transcript_fields


def _tx(surface_words: list[str], gaps: list[float] | None = None) -> Transcript:
    """Build a derived Transcript from surface tokens with optional inter-word gaps."""
    gaps = gaps or [0.05] * len(surface_words)
    words, t = [], 0.0
    for text, gap in zip(surface_words, gaps):
        t += gap
        words.append(Word(text=text, start=round(t, 3), end=round(t + 0.25, 3)))
        t += 0.25
    return derive_transcript_fields(Transcript(words=words))


def _index_of(t: Transcript, norm: str) -> int:
    return next(i for i, w in enumerate(t.words) if w.normalized == norm)


# --- Fix #4: 'like' is not flagged in its content (verb/preposition) senses ---- #

def test_like_main_verb_is_not_a_filler():
    t = _tx(["I", "like", "pizza."])
    assert is_context_filler(t, _index_of(t, "like")) is False


def test_like_preposition_is_not_a_filler():
    t = _tx(["cities", "like", "the", "ones", "here."])
    assert is_context_filler(t, _index_of(t, "like")) is False


def test_like_sentence_initial_is_a_filler():
    t = _tx(["Like,", "I", "was", "there."])
    assert is_context_filler(t, 0) is True


def test_like_after_hesitation_pause_is_a_filler():
    t = _tx(["it", "was", "like", "huge."], gaps=[0.05, 0.05, 0.9, 0.05])
    assert is_context_filler(t, _index_of(t, "like")) is True


# --- Fix #3: false-start prefix rule no longer flags legitimate adjacent words -- #

def test_no_false_start_on_common_word_prefixes():
    for pair in (["to", "today."], ["we", "went."], ["the", "theater."], ["a", "about."]):
        t = _tx(pair)
        fs = [f for f in detect_repetitions(t) if f.kind == "false_start"]
        assert not fs, f"{pair} wrongly flagged: {fs}"


def test_genuine_clip_still_flagged():
    t = _tx(["comp", "company", "is", "big."])
    fs = [f for f in detect_repetitions(t) if f.kind == "false_start"]
    assert fs, "a real clipped fragment should still be a false start"


# --- Fix #2: confidence normalization is unambiguous per engine ---------------- #

def test_linear_engine_keeps_zero_as_zero():
    assert normalize_confidence([0.0, 0.5, 1.0], "faster-whisper") == [0.0, 0.5, 1.0]


def test_logprob_engine_maps_zero_to_one():
    out = normalize_confidence([0.0, -0.69314718], "some-logprob-engine")
    assert out[0] == 1.0           # log-prob 0 -> probability 1
    assert abs(out[1] - 0.5) < 0.01  # log-prob ln(0.5) -> 0.5


def test_none_confidence_passes_through():
    assert normalize_confidence([None, 0.4], "faster-whisper") == [None, 0.4]


# --- Fix #1: word-choice mode reflects the analyzer that actually ran ----------- #

def test_offline_mode_reported_when_llm_disabled(sample_transcript):
    from speech_grading.pipeline import run_on_transcript

    report = run_on_transcript(sample_transcript, Config(use_llm=False))
    assert report.metadata["word_choice_mode"] == "offline-lexicon"


def test_llm_failure_falls_back_and_reports_offline(sample_transcript, monkeypatch):
    # use_llm=True but no API key -> LLM raises -> dispatcher falls back to offline,
    # and the provenance label must say so (not lie "claude").
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    from speech_grading.pipeline import run_on_transcript

    report = run_on_transcript(sample_transcript, Config(use_llm=True))
    assert report.metadata["word_choice_mode"] == "offline-lexicon"
