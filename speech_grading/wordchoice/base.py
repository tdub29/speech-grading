"""Word-choice dispatcher: try the LLM analyzer, fall back to the offline one.

The offline analyzer is the source of record and always works with no network or
API key. The LLM analyzer is enrichment: if it errors (no key, network failure,
rate limit, schema mismatch after retries), we fall back so the pipeline never breaks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..schema import Transcript, WordChoiceFinding


class WordChoiceAnalyzer(ABC):
    @abstractmethod
    def analyze(self, t: Transcript) -> list[WordChoiceFinding]:
        raise NotImplementedError


def analyze_word_choice(t: Transcript, cfg: Config) -> tuple[list[WordChoiceFinding], str]:
    """Return ``(findings, mode)`` where ``mode`` is the analyzer that actually ran.

    Precedence: an agent-handoff response file (Claude in the loop, no API key) >
    the Claude API path > the deterministic offline analyzer. Any failure in a
    higher tier falls through to the next, and the returned mode reflects the real
    outcome so report provenance is trustworthy.
    """
    import os

    from .offline import OfflineWordChoice

    offline = OfflineWordChoice(cfg)

    # 1. Agent handoff: an agent already filled in a findings file. No key needed.
    if cfg.wordchoice_json and os.path.exists(cfg.wordchoice_json):
        try:
            from .llm import load_handoff_response

            findings = load_handoff_response(cfg.wordchoice_json, t)
            return findings, "claude-agent"
        except Exception:  # noqa: BLE001 - a bad handoff file must not break grading
            pass

    if cfg.use_llm:
        try:
            from .llm import LLMWordChoice

            findings = LLMWordChoice(cfg).analyze(t)
            if findings:
                return findings, "claude"
            # Empty result is suspicious for a non-trivial sample; fall through.
        except Exception:  # noqa: BLE001 - any LLM failure must degrade gracefully
            pass

    return offline.analyze(t), "offline-lexicon"
