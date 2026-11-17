"""Tests for sentence-length variety metric."""

from speech_grading.analysis.readability import sentence_length_stats
from speech_grading.schema import Transcript, Word


def test_sentence_length_stats_worked_example():
    words = [
        Word(text="Hello", start=0.0, end=0.2),
        Word(text="um", start=0.2, end=0.4, is_filled_pause=True),
        Word(text="world.", start=0.4, end=0.6),
        Word(text="This", start=0.7, end=0.9),
        Word(text="is", start=0.9, end=1.1),
        Word(text="clear.", start=1.1, end=1.4),
    ]
    t = Transcript(words=words, sentences=[(0, 2), (3, 5)])
    assert sentence_length_stats(t) == {
        "sentence_count": 2,
        "mean_sentence_words": 2.5,
        "sentence_length_stdev": 0.5,
    }


def test_sentence_length_stats_empty_and_filler_only():
    assert sentence_length_stats(Transcript()) == {
        "sentence_count": 0,
        "mean_sentence_words": 0.0,
        "sentence_length_stdev": 0.0,
    }
    words = [
        Word(text="um", start=0.0, end=0.2, is_filled_pause=True),
        Word(text="One.", start=0.3, end=0.5),
    ]
    t = Transcript(words=words, sentences=[(0, 0), (1, 1)])
    assert sentence_length_stats(t) == {
        "sentence_count": 1,
        "mean_sentence_words": 1.0,
        "sentence_length_stdev": 0.0,
    }


def test_sentence_length_stats_varied_lengths():
    words = [Word(text=f"w{i}", start=i * 0.2, end=i * 0.2 + 0.1) for i in range(9)]
    t = Transcript(words=words, sentences=[(0, 0), (1, 3), (4, 8)])
    # lengths = [1, 3, 5] -> mean = 3.0, pstdev = sqrt((4+0+4)/3) = 1.63
    assert sentence_length_stats(t) == {
        "sentence_count": 3,
        "mean_sentence_words": 3.0,
        "sentence_length_stdev": 1.63,
    }


def test_sentence_length_stats_in_report_metrics(sample_transcript, tmp_path):
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.report import render_html

    report = run_on_transcript(sample_transcript, Config())
    expected = sentence_length_stats(sample_transcript)
    for k, v in expected.items():
        assert report.metrics[k] == v
    out_html = tmp_path / "r.html"
    render_html(report, str(out_html))
    assert "sentence_length_stdev" in out_html.read_text(encoding="utf-8")
