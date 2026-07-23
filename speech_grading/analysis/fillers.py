"""Filler detection: filled pauses, discourse fillers, context-sensitive
discourse markers, and multiword filler phrases.

Pure function over a canonical :class:`Transcript` (no ASR, no network), driven
entirely by the tagged lexicons in :mod:`speech_grading.lexicons`. Every flagged
item is returned as a uniform :class:`Finding` with ``kind='filler'`` and
``source='lexicon'`` so the scorer and report renderer treat it like any other.

Detection tiers (severity reflected in ``score``):
  * filled pauses (``um``/``uh``/...) and any Word with ``is_filled_pause`` -> ~0.95
  * always-on discourse fillers (``basically``/``actually``/...) -> ~0.7
  * context-sensitive markers (``like``/``so``/...) only when
    :func:`is_context_filler` is True -> ~0.7
  * multiword filler phrases tagged ``filler`` (``you know``/``i mean``/...) -> ~0.7

PAUSE-GATING: when a filler is preceded by a hesitation pause -- a silent gap
larger than the speaker's median gap plus ``filler_pause_gate`` -- its severity is
upgraded to 1.0, because a filler that fills a long silence is a clearer tell.
"""

from __future__ import annotations

from typing import Any

from speech_grading.lexicons import (
    CONTEXT_FILLERS,
    DISCOURSE_FILLERS,
    FILLED_PAUSES,
    MAX_PHRASE_LEN,
    PHRASE_TAGS,
    is_context_filler,
)
from speech_grading.schema import Finding, Transcript

# Phrases (normalized) that carry the ``filler`` tag, scanned longest-first.
_FILLER_PHRASES: list[tuple[str, ...]] = sorted(
    (tuple(phrase.split()) for phrase, tags in PHRASE_TAGS.items() if "filler" in tags),
    key=len,
    reverse=True,
)

_FILLED_PAUSE_SCORE = 0.95
_DISCOURSE_SCORE = 0.7


def _hesitation_pause(t: Transcript, i: int, thresholds: dict[str, Any]) -> bool:
    """True when the silent gap before word ``i`` exceeds the speaker's median
    gap plus the configured ``filler_pause_gate`` slack."""
    gate = float(thresholds.get("filler_pause_gate", 0.3))
    return t.gap_before(i) > t.speaker_median_gap + gate


def _make_word_finding(
    t: Transcript, i: int, base_score: float, label: str, thresholds: dict[str, Any]
) -> Finding:
    """Build a single-token filler Finding, applying pause-gating."""
    word = t.words[i]
    score = base_score
    rationale = f"{label}: '{word.text}'."
    if _hesitation_pause(t, i, thresholds):
        score = 1.0
        rationale += " Preceded by a hesitation pause."
    return Finding(
        kind="filler",
        word_index=i,
        start=word.start,
        end=word.end,
        original=word.text,
        suggestion="",
        rationale=rationale,
        score=score,
        source="lexicon",
    )


def _make_phrase_finding(
    t: Transcript, i: int, j: int, thresholds: dict[str, Any]
) -> Finding:
    """Build a multiword filler-phrase Finding spanning words ``i..j``."""
    normalized = " ".join(t.words[k].normalized for k in range(i, j + 1))
    original = " ".join(t.words[k].text for k in range(i, j + 1))
    score = _DISCOURSE_SCORE
    rationale = f"Filler phrase: '{normalized}'."
    if _hesitation_pause(t, i, thresholds):
        score = 1.0
        rationale += " Preceded by a hesitation pause."
    return Finding(
        kind="filler",
        word_index=i,
        span=(i, j),
        start=t.words[i].start,
        end=t.words[j].end,
        original=original,
        suggestion="",
        rationale=rationale,
        score=score,
        source="lexicon",
    )


def _match_phrase(t: Transcript, i: int) -> int | None:
    """If a filler phrase starts at index ``i``, return its (inclusive) end index,
    preferring the longest match; otherwise None."""
    words = t.words
    n = len(words)
    for phrase in _FILLER_PHRASES:
        plen = len(phrase)
        if i + plen > n or plen > MAX_PHRASE_LEN:
            continue
        if all(words[i + k].normalized == phrase[k] for k in range(plen)):
            return i + plen - 1
    return None


def detect_fillers(t: Transcript, thresholds: dict[str, Any]) -> list[Finding]:
    """Detect fillers in ``t`` and return Findings sorted by start time.

    Multiword phrases are matched first (longest-preferred) and the tokens they
    consume are skipped, so ``you know`` is reported once as a phrase rather than
    twice as ambiguous single words.
    """
    findings: list[Finding] = []
    consumed: set[int] = set()
    n = len(t.words)

    # First pass: multiword filler phrases. Tokens inside a matched phrase are
    # marked consumed so the single-token pass ignores them.
    i = 0
    while i < n:
        if i in consumed:
            i += 1
            continue
        end = _match_phrase(t, i)
        if end is not None:
            findings.append(_make_phrase_finding(t, i, end, thresholds))
            for k in range(i, end + 1):
                consumed.add(k)
            i = end + 1
        else:
            i += 1

    # Second pass: single-token fillers on tokens not already inside a phrase.
    for idx in range(n):
        if idx in consumed:
            continue
        word = t.words[idx]
        tok = word.normalized
        if word.is_filled_pause or tok in FILLED_PAUSES:
            findings.append(
                _make_word_finding(t, idx, _FILLED_PAUSE_SCORE, "Filled pause", thresholds)
            )
        elif tok in DISCOURSE_FILLERS:
            findings.append(
                _make_word_finding(t, idx, _DISCOURSE_SCORE, "Discourse filler", thresholds)
            )
        elif tok in CONTEXT_FILLERS and is_context_filler(t, idx):
            findings.append(
                _make_word_finding(t, idx, _DISCOURSE_SCORE, "Discourse marker used as filler", thresholds)
            )

    findings.sort(key=lambda f: f.start)
    return findings
