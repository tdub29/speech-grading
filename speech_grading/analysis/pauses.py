"""Pause analysis: classify silent inter-word gaps and surface awkward long pauses.

Pure function over a canonical :class:`Transcript` (no ASR, no network). Gaps are
classified into micro / normal / long bands using the configured thresholds. Only
``long`` pauses become :class:`Finding` objects, because micro and normal gaps are the
ordinary rhythm of fluent speech and carry no penalty.

A long pause *in the middle of a clause* reads as hesitation or a memory lapse, so it
is weighted more heavily than a long pause at a sentence boundary (where a breath or
beat is rhetorically natural).
"""

from __future__ import annotations

from speech_grading.schema import (
    Finding,
    Transcript,
    is_sentence_final,
    is_sentence_initial,
)


def detect_pauses(t: Transcript, thresholds: dict) -> list[Finding]:
    """Return a list of ``long_pause`` Findings, sorted by start time.

    For each adjacent word pair the silent gap is classified:

    * ``micro``  -- gap < ``pause_micro`` (sub-perceptual; ignored)
    * ``normal`` -- between the micro and long thresholds (ignored)
    * ``long``   -- gap > ``pause_long`` (flagged)

    Long pauses are scored by how far the gap exceeds ``pause_long``; mid-clause long
    pauses (not adjacent to a sentence boundary) are additionally weighted by
    ``long_pause_midclause_weight`` because they read as hesitation.
    """
    pause_micro = thresholds.get("pause_micro", 0.2)
    pause_long = thresholds.get("pause_long", 0.7)
    midclause_weight = thresholds.get("long_pause_midclause_weight", 1.5)

    findings: list[Finding] = []
    for i in range(1, len(t.words)):
        gap = t.gap_before(i)
        # Classify; only long gaps are actionable.
        if gap < pause_micro:
            continue  # micro
        if gap <= pause_long:
            continue  # normal
        # Long pause. Base score scales with how far the gap exceeds the threshold.
        base = min(1.0, 0.5 + (gap - pause_long))

        # Mid-clause = the boundary between words i-1 and i is NOT a sentence edge.
        at_boundary = is_sentence_final(t, i - 1) or is_sentence_initial(t, i)
        mid_clause = not at_boundary
        if mid_clause:
            score = min(1.0, base * midclause_weight)
            rationale = "Long mid-clause pause (awkward)"
        else:
            score = base
            rationale = "Long pause at a sentence boundary"

        findings.append(
            Finding(
                kind="long_pause",
                word_index=i,
                start=t.words[i - 1].end,
                end=t.words[i].start,
                original="(pause %.2fs)" % gap,
                rationale=rationale,
                score=score,
                source="rule",
            )
        )

    findings.sort(key=lambda f: f.start)
    return findings
