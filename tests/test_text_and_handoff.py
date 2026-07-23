"""Tests for text-transcript ingestion, the agent-handoff word-choice workflow,
and the central grading ledger."""

from __future__ import annotations

import json

from speech_grading.cli import _append_log
from speech_grading.config import Config
from speech_grading.pipeline import run_on_transcript
from speech_grading.schema import load_transcript_text
from speech_grading.wordchoice.base import analyze_word_choice
from speech_grading.wordchoice.llm import build_handoff_request

SAMPLE = "So, um, I think the results were, like, really good. We we saw a big increase in stuff."


def test_text_transcript_has_no_timing_and_skips_timing_dims():
    t = load_transcript_text(SAMPLE)
    assert t.has_timing is False
    assert t.total_words > 0

    report = run_on_transcript(t, Config())
    dims = {d.dimension for d in report.dimensions}
    # Timing-only dimensions are omitted (not faked) on a text transcript.
    assert "pace" not in dims
    assert "pauses" not in dims
    # Lexical dimensions still run.
    assert {"fillers", "hedging", "vocabulary", "readability", "word_choice"} <= dims
    assert abs(sum(d.weight for d in report.dimensions) - 1.0) < 1e-6


def test_text_transcript_still_flags_fillers_and_weak_words():
    t = load_transcript_text(SAMPLE)
    report = run_on_transcript(t, Config())
    kinds = {f.kind for f in report.findings}
    assert "filler" in kinds          # um, So, like, ...
    assert "repetition" in kinds      # "we we"
    assert "hedge" in kinds or "weak_word" in kinds  # "I think", "really", "stuff"


def test_emit_request_packet_shape():
    t = load_transcript_text(SAMPLE)
    req = build_handoff_request(t, Config())
    assert req["has_timing"] is False
    assert req["words"] and req["words"][0]["index"] == 0
    assert "response_schema" in req and "findings" in req["response_schema"]


def test_agent_handoff_takes_precedence(tmp_path):
    t = load_transcript_text(SAMPLE)
    resp = {"findings": [
        {"word_index": 3, "issue_type": "weak", "original": "think",
         "suggestion": "know", "rationale": "commit instead of hedging.", "confidence": 0.8},
        {"word_index": 8, "issue_type": "tripped_up", "original": "really",
         "suggestion": "", "rationale": "empty intensifier.", "confidence": 0.6},
    ]}
    p = tmp_path / "resp.json"
    p.write_text(json.dumps(resp), encoding="utf-8")

    findings, mode = analyze_word_choice(t, Config(wordchoice_json=str(p)))
    assert mode == "claude-agent"
    issues = {f.issue_type for f in findings}
    assert "weak" in issues and "tripped_up" in issues


def test_bad_handoff_file_falls_back_to_offline(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{ not valid json", encoding="utf-8")
    t = load_transcript_text(SAMPLE)
    findings, mode = analyze_word_choice(t, Config(wordchoice_json=str(p)))
    assert mode == "offline-lexicon"  # graceful fallback, no crash


def test_handoff_tolerates_utf8_bom(tmp_path):
    # Windows tools (PowerShell Set-Content -Encoding utf8) prepend a BOM.
    t = load_transcript_text(SAMPLE)
    resp = {"findings": [{"word_index": 3, "issue_type": "weak", "original": "think",
                          "suggestion": "know", "rationale": "x.", "confidence": 0.8}]}
    p = tmp_path / "bom.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps(resp).encode("utf-8"))
    findings, mode = analyze_word_choice(t, Config(wordchoice_json=str(p)))
    assert mode == "claude-agent" and findings


def test_ledger_append(tmp_path):
    t = load_transcript_text(SAMPLE)
    report = run_on_transcript(t, Config())
    log = tmp_path / "graded-log.md"
    _append_log(str(log), "answer.txt", report)
    _append_log(str(log), "answer2.txt", report)
    content = log.read_text(encoding="utf-8")
    assert "orator grading ledger" in content
    assert content.count("answer") == 2  # header written once, two rows
