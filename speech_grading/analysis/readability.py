"""Readability analysis: textstat grade-level metrics over the surface transcript.

This dimension is **relative-tracking only** (``weight == 0`` in the default rubric).
Spoken language is normally simple/low-grade, so the band is scored *gently*: a
Flesch-Kincaid grade in a broad conversational band counts as ``excellent``/``good``,
and only genuine extremes drop to ``fair``. Readability never hard-penalizes — a
plain-spoken talk is not a defect — so ``points`` stay mostly high. No findings are
emitted (there is nothing to flag word-by-word here).
"""

from __future__ import annotations

from typing import Callable

import textstat

from speech_grading.schema import DimensionScore, Transcript


def _safe(fn: Callable[[str], float], text: str) -> float:
    """Run a textstat metric, returning 0.0 on any failure (empty text, etc.)."""
    try:
        return float(fn(text))
    except Exception:  # pragma: no cover - defensive guard around textstat
        return 0.0


def compute_readability(t: Transcript) -> DimensionScore:
    """Score readability from textstat grade-level metrics on the surface text.

    ``raw`` is the Flesch-Kincaid grade level. Banding is deliberately lenient
    because conversational speech sits at a low grade by nature:

    - FK grade in ``[7, 9]``            -> ``excellent`` (clear, well-pitched)
    - FK grade in ``[5, 11]``           -> ``good``      (normal spoken range)
    - anything outside that             -> ``fair``      (very simple or very dense)

    ``poor`` is never assigned. Even ``fair`` keeps ``points`` high since this is a
    low-weight, relative-tracking dimension.
    """
    # Surface text: original tokens (with punctuation) joined by spaces.
    text = " ".join(w.text for w in t.words)

    flesch_reading_ease = _safe(textstat.flesch_reading_ease, text)
    flesch_kincaid_grade = _safe(textstat.flesch_kincaid_grade, text)
    smog_index = _safe(textstat.smog_index, text)
    gunning_fog = _safe(textstat.gunning_fog, text)

    raw = flesch_kincaid_grade

    if 7.0 <= raw <= 9.0:
        band, points = "excellent", 100.0
    elif 5.0 <= raw <= 11.0:
        band, points = "good", 92.0
    else:
        # Very simple or very dense for the spoken context — note it, don't punish it.
        band, points = "fair", 80.0

    return DimensionScore(
        dimension="readability",
        raw=raw,
        band=band,
        points=points,
        weight=0.0,
        findings=[],
        detail={
            "flesch_reading_ease": flesch_reading_ease,
            "flesch_kincaid_grade": flesch_kincaid_grade,
            "smog_index": smog_index,
            "gunning_fog": gunning_fog,
        },
    )
