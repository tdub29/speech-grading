"""Tests for question count and question rate."""

from speech_grading.analysis.readability import question_stats
from speech_grading.schema import Transcript, Word


def test_question_stats_worked_example():
    words = [
        Word(text="Wait", start=0.0, end=0.2),
        Word(text="Why?", start=0.2, end=0.5),
        Word(text="Are", start=0.6, end=0.8),
        Word(text='really?"', start=0.8, end=1.0),
        Word(text="All", start=1.1, end=1.3),
        Word(text="Done.", start=1.3, end=1.5),
    ]
    t = Transcript(words=words, sentences=[(0, 1), (2, 3), (4, 5)])
    assert question_stats(t) == {"question_count": 2, "question_rate": 0.6667}


def test_question_stats_empty_and_no_questions():
    assert question_stats(Transcript()) == {"question_count": 0, "question_rate": 0.0}
    words = [
        Word(text="Hello", start=0.0, end=0.2),
        Word(text="world.", start=0.2, end=0.5),
    ]
    t = Transcript(words=words, sentences=[(0, 1)])
    assert question_stats(t) == {"question_count": 0, "question_rate": 0.0}


def test_question_stats_closing_paren_and_all_questions():
    words = [
        Word(text="What", start=0.0, end=0.2),
        Word(text="(now?)", start=0.2, end=0.4),
        Word(text="Who?", start=0.5, end=0.7),
    ]
    t = Transcript(words=words, sentences=[(0, 1), (2, 2)])
    assert question_stats(t) == {"question_count": 2, "question_rate": 1.0}


def test_question_stats_in_report_metrics(sample_transcript, tmp_path):
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.report import render_html

    report = run_on_transcript(sample_transcript, Config())
    expected = question_stats(sample_transcript)
    assert report.metrics["question_count"] == expected["question_count"]
    assert report.metrics["question_rate"] == expected["question_rate"]
    out_html = tmp_path / "r.html"
    render_html(report, str(out_html))
    assert "question_rate" in out_html.read_text(encoding="utf-8")
