"""Integration tests for the end-to-end offline pipeline and scorer."""

from __future__ import annotations

from speech_grading.config import Config
from speech_grading.pipeline import run_on_transcript
from speech_grading.report import highlight_transcript_html, render_html, render_json


def test_run_on_transcript_offline(sample_transcript):
    cfg = Config()  # offline word-choice, no acoustic
    report = run_on_transcript(sample_transcript, cfg)

    # Composite is a real 0-100 number.
    assert 0.0 <= report.overall_score <= 100.0

    # Prosody is absent (no audio) so its weight is redistributed: the remaining
    # dimension weights must renormalize to ~1.0.
    dims = {d.dimension for d in report.dimensions}
    assert "prosody" not in dims
    assert {"fillers", "pace", "pauses", "word_choice", "vocabulary", "hedging", "readability"} <= dims
    assert abs(sum(d.weight for d in report.dimensions) - 1.0) < 1e-6

    assert report.metadata["word_choice_mode"] == "offline-lexicon"


def test_pipeline_flags_the_tripped_up_word(sample_transcript):
    report = run_on_transcript(sample_transcript, Config())
    tripped = [f for f in report.findings if f.kind == "tripped_up"]
    assert tripped, "expected at least one tripped-up moment"
    # The 1.35s low-confidence pause before 'utilize' is the planted stumble.
    words = sample_transcript.words
    assert any(words[f.word_index].normalized == "utilize" for f in tripped)
    util = next(f for f in tripped if words[f.word_index].normalized == "utilize")
    assert util.suggestion == "use"  # curated stronger word


def test_render_outputs(sample_transcript, tmp_path):
    report = run_on_transcript(sample_transcript, Config())

    html_str = highlight_transcript_html(report)
    assert "<span" in html_str and "f-tripped" in html_str  # the stumble is highlighted

    html_path = tmp_path / "r.html"
    json_path = tmp_path / "r.json"
    render_html(report, str(html_path))
    render_json(report, str(json_path))
    assert html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert '"overall_score"' in json_path.read_text(encoding="utf-8")


def test_prosody_weight_redistribution_keeps_scale(sample_transcript):
    # With acoustic enabled but no audio, prosody still returns None and the
    # composite stays on a 0-100 scale (no divide-by-zero, no weight leak).
    cfg = Config(enable_acoustic=True)
    report = run_on_transcript(sample_transcript, cfg)
    assert 0.0 <= report.overall_score <= 100.0
