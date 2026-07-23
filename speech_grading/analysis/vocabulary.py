"""Vocabulary / lexical-diversity dimension.

Measures how varied a speaker's word choice is, independent of *whether* any
single word is weak (that is the ``word_choice`` dimension's job). We lean on the
``lexicalrichness`` package for the standard measures:

* **MATTR** (Moving-Average Type-Token Ratio) -- the headline metric. Unlike raw
  TTR it is largely insensitive to transcript length, so it compares fairly across
  short and long samples. We band off MATTR.
* **MTLD** (Measure of Textual Lexical Diversity) -- a complementary, length-robust
  measure reported in ``detail`` for context.
* **TTR** (Type-Token Ratio) -- unique / total, reported for transparency.

This dimension is informational: ``weight=0`` and it emits no :class:`Finding`
objects (there is nothing to point at in the transcript -- it is a whole-sample
property). The band thresholds below are **heuristic**, tuned for short spoken
monologues where natural repetition (function words, topic nouns) pulls MATTR
well below what you'd see in edited prose.
"""

from __future__ import annotations

from lexicalrichness import LexicalRichness

from speech_grading.schema import DimensionScore, Transcript

#: Heuristic MATTR cut-points for spoken monologues (see module docstring).
_BAND_EXCELLENT = 0.85
_BAND_GOOD = 0.72
_BAND_FAIR = 0.60

#: Points awarded per band. Even "poor" lexical diversity is not a hard failure,
#: so the floor is generous relative to other dimensions.
_BAND_POINTS = {
    "excellent": 100.0,
    "good": 82.0,
    "fair": 64.0,
    "poor": 45.0,
}

#: MATTR window used by the literature; we clamp it to the token count for short text.
_MATTR_WINDOW = 50


def _band_for_mattr(mattr: float) -> str:
    """Map a MATTR value to one of the four rubric bands."""
    if mattr >= _BAND_EXCELLENT:
        return "excellent"
    if mattr >= _BAND_GOOD:
        return "good"
    if mattr >= _BAND_FAIR:
        return "fair"
    return "poor"


def compute_vocabulary(t: Transcript) -> DimensionScore:
    """Score lexical diversity of ``t`` using ``lexicalrichness``.

    Tokens are the normalized surface forms of real lexical words: filled pauses
    (``um``/``uh``) and non-alphabetic tokens are excluded so punctuation and
    disfluencies do not inflate or deflate diversity.
    """
    tokens = [
        w.normalized
        for w in t.words
        if w.normalized and not w.is_filled_pause and any(c.isalpha() for c in w.normalized)
    ]
    total = len(tokens)
    unique = len(set(tokens))

    # Guard short/empty transcripts: nothing to measure -> neutral "fair".
    if total == 0:
        detail = {"mattr": 0.0, "mtld": 0.0, "ttr": 0.0, "unique": 0, "total": 0}
        return DimensionScore(
            dimension="vocabulary",
            raw=0.0,
            band="fair",
            points=_BAND_POINTS["fair"],
            weight=0.0,
            findings=[],
            detail=detail,
        )

    text = " ".join(tokens)
    ttr = unique / total

    if total >= 2:
        lex = LexicalRichness(text)
        # LexicalRichness re-tokenizes ``text``; clamp the window to its own word
        # count so mattr() never raises "window > text size".
        window = min(_MATTR_WINDOW, total, max(1, lex.words))
        try:
            mattr = float(lex.mattr(window_size=window))
        except (ValueError, ZeroDivisionError):
            mattr = ttr
        try:
            mtld = float(lex.mtld())
        except (ValueError, ZeroDivisionError):
            mtld = 0.0
    else:
        # A single token: every measure degenerates to the TTR-like value 1.0.
        mattr = ttr
        mtld = 0.0

    band = _band_for_mattr(mattr)
    detail = {
        "mattr": mattr,
        "mtld": mtld,
        "ttr": ttr,
        "unique": unique,
        "total": total,
    }
    return DimensionScore(
        dimension="vocabulary",
        raw=mattr,
        band=band,
        points=_BAND_POINTS[band],
        weight=0.0,
        findings=[],
        detail=detail,
    )
