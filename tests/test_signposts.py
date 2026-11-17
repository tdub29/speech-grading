"""Tests for signposting and transition phrase density."""

from speech_grading.analysis.vocabulary import count_signposts
from speech_grading.schema import Transcript, Word


def test_count_signposts_worked_example():
    words = [
        Word(text="First,", start=0.0, end=0.2, normalized="first"),
        Word(text="um", start=0.2, end=0.3, is_filled_pause=True, normalized="um"),
        Word(text="we", start=0.3, end=0.4, normalized="we"),
        Word(text="check", start=0.4, end=0.6, normalized="check"),
        Word(text="for", start=0.6, end=0.7, normalized="for"),
        Word(text="example", start=0.7, end=0.9, normalized="example"),
        Word(text="this,", start=0.9, end=1.1, normalized="this"),
        Word(text="finally", start=1.1, end=1.4, normalized="finally"),
        Word(text="done.", start=1.4, end=1.6, normalized="done"),
    ]
    t = Transcript(words=words)
    assert count_signposts(t) == {"signpost_count": 3, "signpost_rate_per_100w": 37.5}


def test_count_signposts_empty_and_no_hits():
    assert count_signposts(Transcript()) == {"signpost_count": 0, "signpost_rate_per_100w": 0.0}
    words = [
        Word(text="Plain", start=0.0, end=0.2, normalized="plain"),
        Word(text="words", start=0.2, end=0.4, normalized="words"),
        Word(text="only.", start=0.4, end=0.6, normalized="only"),
    ]
    assert count_signposts(Transcript(words=words)) == {
        "signpost_count": 0,
        "signpost_rate_per_100w": 0.0,
    }


def test_count_signposts_four_word_and_non_overlapping():
    toks = ["on", "the", "other", "hand", "however", "in", "conclusion", "thanks"]
    words = [Word(text=w, start=i * 0.2, end=i * 0.2 + 0.15, normalized=w) for i, w in enumerate(toks)]
    # 3 signposts in 8 words -> 37.5 per 100w
    assert count_signposts(Transcript(words=words)) == {
        "signpost_count": 3,
        "signpost_rate_per_100w": 37.5,
    }


def test_count_signposts_in_report_metrics(sample_transcript, tmp_path):
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.report import render_html

    report = run_on_transcript(sample_transcript, Config())
    expected = count_signposts(sample_transcript)
    assert report.metrics["signpost_count"] == expected["signpost_count"]
    assert report.metrics["signpost_rate_per_100w"] == expected["signpost_rate_per_100w"]
    out_html = tmp_path / "r.html"
    render_html(report, str(out_html))
    assert "signpost_rate_per_100w" in out_html.read_text(encoding="utf-8")
