"""Word-choice analysis: an LLM pass (Claude) with a deterministic offline fallback.

Both implementations emit the same WordChoiceFinding schema, so they are
interchangeable and the pipeline never branches on which one ran.
"""
from .base import WordChoiceAnalyzer, analyze_word_choice

__all__ = ["WordChoiceAnalyzer", "analyze_word_choice"]
