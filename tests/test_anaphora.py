"""Tests for rhetorical anaphora / tricolon detection."""

from speech_grading.analysis.repetitions import detect_anaphora
from speech_grading.schema import Transcript, Word


def test_detect_anaphora_worked_example():
    words = [
        Word(text="We", start=0.0, end=0.2, normalized="we"),
        Word(text="build.", start=0.2, end=0.5, normalized="build"),
        Word(text="We", start=0.6, end=0.8, normalized="we"),
        Word(text="ship.", start=0.8, end=1.0, normalized="ship"),
        Word(text="We", start=1.1, end=1.3, normalized="we"),
        Word(text="learn.", start=1.3, end=1.6, normalized="learn"),
    ]
    t = Transcript(words=words, sentences=[(0, 1), (2, 3), (4, 5)])
    assert detect_anaphora(t) == [
        {"word": "we", "count": 3, "start_word": 0, "end_word": 5}
    ]


def test_detect_anaphora_skips_leading_filled_pause_and_short_runs():
    words = [
        Word(text="um", start=0.0, end=0.1, is_filled_pause=True, normalized="um"),
        Word(text="Now", start=0.1, end=0.3, normalized="now"),
        Word(text="act.", start=0.3, end=0.5, normalized="act"),
        Word(text="Now", start=0.6, end=0.8, normalized="now"),
        Word(text="lead.", start=0.8, end=1.0, normalized="lead"),
        Word(text="Now", start=1.1, end=1.3, normalized="now"),
        Word(text="win.", start=1.3, end=1.5, normalized="win"),
        Word(text="They", start=1.6, end=1.8, normalized="they"),
        Word(text="go.", start=1.8, end=2.0, normalized="go"),
        Word(text="They", start=2.1, end=2.3, normalized="they"),
        Word(text="stay.", start=2.3, end=2.5, normalized="stay"),
    ]
    t = Transcript(words=words, sentences=[(0, 2), (3, 4), (5, 6), (7, 8), (9, 10)])
    assert detect_anaphora(t) == [
        {"word": "now", "count": 3, "start_word": 0, "end_word": 6}
    ]


def test_detect_anaphora_empty_and_multiple_runs():
    assert detect_anaphora(Transcript()) == []
    words = [
        Word(text="A", start=0.0, end=0.1, normalized="a"),
        Word(text="x.", start=0.1, end=0.2, normalized="x"),
        Word(text="A", start=0.3, end=0.4, normalized="a"),
        Word(text="y.", start=0.4, end=0.5, normalized="y"),
        Word(text="B", start=0.6, end=0.7, normalized="b"),
        Word(text="z.", start=0.7, end=0.8, normalized="z"),
        Word(text="B", start=0.9, end=1.0, normalized="b"),
        Word(text="w.", start=1.0, end=1.1, normalized="w"),
    ]
    t = Transcript(words=words, sentences=[(0, 1), (2, 3), (4, 5), (6, 7)])
    assert detect_anaphora(t, min_run=2) == [
        {"word": "a", "count": 2, "start_word": 0, "end_word": 3},
        {"word": "b", "count": 2, "start_word": 4, "end_word": 7},
    ]


def test_detect_anaphora_in_report_metrics(tmp_path):
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.report import render_html
    from speech_grading.schema import load_transcript_text

    t = load_transcript_text("We rise today. We work hard. We finish strong.")
    report = run_on_transcript(t, Config())
    assert report.metrics["anaphora_count"] == 1
    out_html = tmp_path / "r.html"
    render_html(report, str(out_html))
    assert "anaphora_count" in out_html.read_text(encoding="utf-8")
