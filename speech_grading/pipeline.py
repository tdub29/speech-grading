"""End-to-end orchestration: (transcribe | load) -> analyze -> word-choice -> score -> report.

Two entry points:
  * :func:`run_pipeline` -- full run from an audio file or a Transcript JSON fixture.
  * :func:`run_on_transcript` -- analysis-only path over an in-memory Transcript
    (no ASR, no network). This is what the tests exercise.
"""

from __future__ import annotations

import os

from .analysis.fillers import detect_fillers
from .analysis.pace import compute_pace
from .analysis.pauses import detect_pauses
from .analysis.readability import compute_readability
from .analysis.repetitions import detect_repetitions
from .analysis.vocabulary import compute_vocabulary
from .analysis.weak_words import detect_weak_words
from .analysis.prosody import compute_prosody
from .config import Config
from .schema import (
    Finding,
    Report,
    Transcript,
    WordChoiceFinding,
    derive_transcript_fields,
    load_transcript_json,
    load_transcript_text,
)
from .scorer import score
from .wordchoice.base import analyze_word_choice

# WordChoiceFinding.issue_type -> Finding.kind
_ISSUE_KIND = {"tripped_up": "tripped_up", "weak": "weak_word", "hedge": "hedge", "filler": "filler"}


def _wordchoice_to_findings(t: Transcript, wcs: list[WordChoiceFinding]) -> list[Finding]:
    out: list[Finding] = []
    n = len(t.words)
    for wc in wcs:
        if not (0 <= wc.word_index < n):
            continue
        w = t.words[wc.word_index]
        out.append(
            Finding(
                kind=_ISSUE_KIND.get(wc.issue_type, "weak_word"),
                word_index=wc.word_index,
                start=w.start,
                end=w.end,
                original=wc.original or w.text,
                suggestion=wc.suggestion,
                rationale=wc.rationale,
                score=wc.confidence,
                source="wordchoice",
            )
        )
    return out


def run_on_transcript(t: Transcript, cfg: Config) -> Report:
    """Run the full analysis + scoring stack over an already-built Transcript."""
    findings: list[Finding] = []
    findings += detect_fillers(t, cfg.thresholds)
    findings += detect_repetitions(t)
    findings += detect_weak_words(t)

    dim_scores = [
        compute_vocabulary(t),
        compute_readability(t),
    ]

    # Timing-dependent dimensions only apply when the transcript carries word
    # timestamps (audio or a timed JSON fixture); a text-only transcript skips them
    # and the scorer redistributes their weight.
    if t.has_timing:
        findings += detect_pauses(t, cfg.thresholds)
        dim_scores.append(compute_pace(t, cfg.thresholds))

    prosody_ds, prosody_findings = compute_prosody(t, cfg)
    if prosody_ds is not None:
        dim_scores.append(prosody_ds)
        findings += prosody_findings

    # Word choice (LLM with deterministic offline fallback) -> tripped-up + suggestions.
    wcs, wc_mode = analyze_word_choice(t, cfg)
    findings += _wordchoice_to_findings(t, wcs)

    return score(t, findings, dim_scores, cfg, word_choice_mode=wc_mode)


def load_input(input_path: str, cfg: Config) -> Transcript:
    """Resolve an input path to a canonical Transcript.

    ``.json`` -> timed Transcript fixture; ``.txt/.md/.vtt/.srt`` -> text-only
    Transcript (no timestamps); anything else -> transcribe via the ASR backend.
    """
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".json":
        return load_transcript_json(input_path)
    if ext in (".txt", ".md", ".vtt", ".srt"):
        return load_transcript_text(input_path)
    backend = _make_backend(cfg)
    t = backend.transcribe(input_path)
    if not t.audio_path:
        t.audio_path = input_path
    return derive_transcript_fields(t)


def run_pipeline(input_path: str, cfg: Config) -> Report:
    """Full run. If ``input_path`` is a Transcript JSON/text, skip ASR; else transcribe."""
    return run_on_transcript(load_input(input_path, cfg), cfg)


def _make_backend(cfg: Config):
    name = cfg.asr_backend
    if name == "faster-whisper":
        from .asr.faster_whisper_backend import FasterWhisperBackend

        return FasterWhisperBackend(
            model_size=cfg.asr_model_size,
            device=cfg.asr_device,
            compute_type=cfg.asr_compute_type,
        )
    if name == "crisper-whisper":
        from .asr.crisper_whisper_backend import CrisperWhisperBackend

        return CrisperWhisperBackend(cfg)
    if name == "vosk":
        from .asr.vosk_backend import VoskBackend

        return VoskBackend()
    raise ValueError(f"Unknown ASR backend: {name!r}")
