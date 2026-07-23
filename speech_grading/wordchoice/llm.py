"""Claude-powered word-choice analyzer.

Uses the Anthropic structured-output path on Opus 4.8:
``client.messages.parse(model="claude-opus-4-8", output_format=WordChoiceFindingList)``
reading ``response.parsed_output``. Adaptive thinking is on; effort defaults to high.

Call-shape rules baked in (per the claude-api reference for Opus 4.8):
  * NO ``budget_tokens``, ``temperature``, ``top_p``, ``top_k`` (all 400 on Opus 4.8).
  * NO assistant prefill (400 on Opus 4.8) -> constraints go in the system prompt.
  * NO citations (incompatible with structured outputs).
Any error here raises so the dispatcher falls back to the offline analyzer.
"""

from __future__ import annotations

from ..config import Config
from ..schema import Transcript, WordChoiceFinding, WordChoiceFindingList
from .base import WordChoiceAnalyzer

_SYSTEM = """You are a precise speech-coaching analyst. You are given a verbatim \
transcript of spoken words, each tagged with its index, timing, and the silent gap \
before it. Identify moments where the speaker:
  - used a WEAK or vague word where a stronger, more specific one existed (issue_type "weak"),
  - HEDGED unnecessarily (issue_type "hedge"),
  - used a FILLER / discourse crutch (issue_type "filler"),
  - or clearly GOT TRIPPED UP: a long gap or repetition right before a word, where they \
seemed to reach for a worse word (issue_type "tripped_up").

For each, return the word_index it applies to, the original text, a stronger \
suggestion when one exists (else leave it null), a one-sentence rationale, and a \
confidence 0-1. Favor precision over volume: only flag genuinely improvable moments. \
For tripped_up, the long gap or repetition must actually be present in the timing data."""


class LLMWordChoice(WordChoiceAnalyzer):
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def build_user_message(self, t: Transcript) -> str:
        """Render an indexed, timing-annotated word list for the model (user turn only)."""
        lines = []
        for i, w in enumerate(t.words[: self.cfg.max_llm_words]):
            gap = t.gap_before(i)
            conf = "" if w.confidence is None else f" conf={w.confidence:.2f}"
            lines.append(f"[{i}] {w.text!r} gap_before={gap:.2f}s{conf}")
        body = "\n".join(lines)
        return (
            "Analyze this transcript and return word-choice findings.\n\n"
            f"Total words: {t.total_words}. Duration: {t.duration_sec:.1f}s. "
            f"Median inter-word gap: {t.speaker_median_gap:.2f}s.\n\n"
            f"{body}"
        )

    def analyze(self, t: Transcript) -> list[WordChoiceFinding]:
        import anthropic  # imported lazily so the package works without the dep

        client = anthropic.Anthropic()
        response = client.messages.parse(
            model=self.cfg.llm_model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": self.build_user_message(t)}],
            output_format=WordChoiceFindingList,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Claude returned no parseable structured output")
        # Clamp indices to the transcript so a hallucinated index can't crash downstream.
        n = len(t.words)
        return [f for f in parsed.findings if 0 <= f.word_index < n]


# --------------------------------------------------------------------------- #
# Agent-handoff workflow (no API key): orator emits a request packet, an agent
# (Claude in the loop) fills in the findings, orator merges them back.
# --------------------------------------------------------------------------- #

def build_handoff_request(t: Transcript, cfg: "Config | None" = None) -> dict:
    """Build the packet an agent fills in to provide word-choice findings.

    Write this to ``<input>.llm-request.json``. An agent reads it, returns a
    ``{"findings": [...]}`` object matching WordChoiceFinding, saved as the
    response; re-run orator with ``--wordchoice-json <response>`` to merge it.
    """
    cap = cfg.max_llm_words if cfg else 1200
    words = []
    for i, w in enumerate(t.words[:cap]):
        words.append(
            {
                "index": i,
                "text": w.text,
                "gap_before": round(t.gap_before(i), 2) if t.has_timing else None,
                "confidence": w.confidence,
            }
        )
    return {
        "instructions": _SYSTEM,
        "response_schema": {
            "findings": [
                {
                    "word_index": "int (index into words below)",
                    "issue_type": "weak | hedge | filler | tripped_up",
                    "original": "str",
                    "suggestion": "str or null (a stronger word, or null to just cut it)",
                    "rationale": "one sentence",
                    "confidence": "float 0-1",
                }
            ]
        },
        "has_timing": t.has_timing,
        "total_words": t.total_words,
        "duration_sec": t.duration_sec,
        "words": words,
    }


def load_handoff_response(path: str, t: Transcript) -> list[WordChoiceFinding]:
    """Load agent-provided word-choice findings from a response JSON file."""
    import json

    # utf-8-sig tolerates a BOM (Windows editors / PowerShell Set-Content add one).
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    parsed = WordChoiceFindingList.model_validate(data)
    n = len(t.words)
    return [f for f in parsed.findings if 0 <= f.word_index < n]
