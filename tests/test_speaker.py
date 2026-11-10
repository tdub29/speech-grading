"""Tests for multi-speaker labeling and --speaker filtering."""

from __future__ import annotations

import json
import pytest

from speech_grading import cli
from speech_grading.schema import Transcript, Word, derive_transcript_fields


def test_word_speaker_default_none():
    w = Word(text="hello", start=0.0, end=0.5)
    assert w.speaker is None


def test_transcript_filter_by_speaker_success():
    words = [
        Word(text="Hello", start=0.0, end=0.4, speaker="Alice"),
        Word(text="world.", start=0.5, end=0.9, speaker="Alice"),
        Word(text="Good", start=1.2, end=1.5, speaker="Bob"),
        Word(text="morning.", start=1.6, end=2.0, speaker="Bob"),
        Word(text="Thanks!", start=2.2, end=2.6, speaker="Alice"),
    ]
    t = Transcript(words=words, duration_sec=2.6, has_timing=True)
    derive_transcript_fields(t)

    alice = t.filter_by_speaker("Alice")
    assert alice.total_words == 3
    assert all(w.speaker == "Alice" for w in alice.words)
    assert alice.words[0].text == "Hello"
    assert alice.words[-1].text == "Thanks!"
    assert alice.duration_sec == round(0.9 + 0.4, 4)

    # Calling filter_by_speaker again with same speaker is a no-op
    alice_again = alice.filter_by_speaker("Alice")
    assert alice_again.total_words == 3


def test_transcript_filter_by_speaker_case_insensitive():
    words = [
        Word(text="One", start=0.0, end=0.3, speaker="Speaker_A"),
        Word(text="Two", start=0.4, end=0.7, speaker="Speaker_B"),
    ]
    t = Transcript(words=words, duration_sec=0.7)
    derive_transcript_fields(t)

    filtered = t.filter_by_speaker("speaker_a")
    assert len(filtered.words) == 1
    assert filtered.words[0].text == "One"


def test_transcript_filter_by_speaker_unknown_raises():
    words = [
        Word(text="One", start=0.0, end=0.3, speaker="Speaker_A"),
        Word(text="Two", start=0.4, end=0.7, speaker="Speaker_B"),
    ]
    t = Transcript(words=words)
    with pytest.raises(ValueError) as exc_info:
        t.filter_by_speaker("Speaker_Z")
    err = str(exc_info.value)
    assert "Speaker 'Speaker_Z' not found" in err
    assert "Speaker_A" in err
    assert "Speaker_B" in err


def test_transcript_filter_by_speaker_no_labels_raises():
    words = [
        Word(text="One", start=0.0, end=0.3),
        Word(text="Two", start=0.4, end=0.7),
    ]
    t = Transcript(words=words)
    with pytest.raises(ValueError) as exc_info:
        t.filter_by_speaker("Speaker_A")
    assert "has no speaker labels" in str(exc_info.value)


def test_cli_speaker_option(tmp_path):
    data = {
        "words": [
            {"text": "Hello", "start": 0.0, "end": 0.4, "confidence": 0.95, "speaker": "Alice"},
            {"text": "there.", "start": 0.5, "end": 0.9, "confidence": 0.95, "speaker": "Alice"},
            {"text": "General", "start": 1.2, "end": 1.5, "confidence": 0.95, "speaker": "Bob"},
            {"text": "Kenobi.", "start": 1.6, "end": 2.0, "confidence": 0.95, "speaker": "Bob"},
        ],
        "duration_sec": 2.0,
        "language": "en",
        "engine": "fixture",
    }
    fixture_path = tmp_path / "multi.json"
    fixture_path.write_text(json.dumps(data), encoding="utf-8")

    out_json = tmp_path / "out.json"
    rc = cli.main([str(fixture_path), "--speaker", "Bob", "--json", str(out_json)])
    assert rc == 0

    saved = json.loads(out_json.read_text(encoding="utf-8"))
    res_words = saved["transcript"]["words"]
    assert len(res_words) == 2
    assert all(w["speaker"] == "Bob" for w in res_words)


def test_filter_other_speaker_turn_is_not_a_pause_or_pace_time():
    words = [
        Word(text="Hi", start=0.0, end=0.5, speaker="A"),
        Word(text="Long", start=1.0, end=30.0, speaker="B"),
        Word(text="Back.", start=31.0, end=31.5, speaker="A"),
    ]
    a = derive_transcript_fields(Transcript(words=words)).filter_by_speaker("A")
    assert a.gap_before(1) == 0.0
    assert a.duration_sec == 1.0
