"""Weak-word / hedging / weasel / booster detection.

Pure function over a canonical :class:`Transcript`. Flags HEDGE / WEASEL /
INTENSIFIER / WEAK single tokens and multi-word phrases, plus a best-effort
``proselint`` pass for extra weasel/hedging coverage.

This module deliberately does **not** flag pure filled-pause fillers (``um``/``uh``)
or discourse fillers whose only tag is ``filler`` (e.g. ``basically``, ``you know``) —
those belong to the fillers module. Densities/scoring happen later in the scorer;
this function only returns raw :class:`Finding` objects sorted by start time.
"""

from __future__ import annotations

from speech_grading.lexicons import (
    MAX_PHRASE_LEN,
    PHRASE_TAGS,
    REPLACEMENTS,
    classify_token,
)
from speech_grading.schema import Finding, Transcript

# Tags this module owns (filler-only tokens/phrases are handled elsewhere).
_OWNED_TAGS = {"hedge", "weasel", "intensifier", "weak"}
# Single-token kind priority: highest-priority owned tag wins.
_KIND_PRIORITY = ("hedge", "weasel", "intensifier", "weak")
# Map an owned tag to a Finding.kind.
_KIND_FOR_TAG = {
    "hedge": "hedge",
    "weasel": "weasel",
    "intensifier": "intensifier",
    "weak": "weak_word",
}


def _suggestion_and_rationale(key: str) -> tuple[str | None, str]:
    """Resolve a replacement for ``key`` (normalized token/phrase).

    Returns ``(suggestion, rationale)``. A replacement of ``""`` means "delete it";
    a missing key means "no concrete swap" (suggestion stays ``None``).
    """
    if key in REPLACEMENTS:
        repl = REPLACEMENTS[key]
        if repl == "":
            return "", "filler/booster — cut it"
        return repl, f"weak word — prefer '{repl}'"
    return None, "weak/hedging word — tighten or cut"


def detect_weak_words(t: Transcript) -> list[Finding]:
    """Detect weak/hedging/weasel/booster words and phrases in ``t``.

    Single tokens are classified via :func:`classify_token`; only the owned tags
    (hedge/weasel/intensifier/weak) trigger a Finding, with kind chosen by the
    priority hedge > weasel > intensifier > weak. Multi-word phrases from
    ``PHRASE_TAGS`` whose tags intersect {hedge, weasel, weak} are matched on the
    normalized token stream (longest-first, non-overlapping). A best-effort
    ``proselint`` pass adds extra weasel/hedging hits mapped back to the nearest
    word by character offset.
    """
    words = t.words
    findings: list[Finding] = []
    consumed: set[int] = set()

    # --- Multi-word phrases first (longest-first), so phrase spans win over the
    #     single tokens they contain. ---
    phrases_by_len = sorted(
        (p for p, tags in PHRASE_TAGS.items() if tags & {"hedge", "weasel", "weak"}),
        key=lambda p: len(p.split()),
        reverse=True,
    )
    n = len(words)
    for i in range(n):
        if i in consumed:
            continue
        for phrase in phrases_by_len:
            ptoks = phrase.split()
            plen = len(ptoks)
            if plen > MAX_PHRASE_LEN:
                continue
            j = i + plen - 1
            if j >= n:
                continue
            if any(k in consumed for k in range(i, j + 1)):
                continue
            if [words[k].normalized for k in range(i, j + 1)] != ptoks:
                continue
            tags = PHRASE_TAGS[phrase]
            # Pick kind by priority among the owned tags this phrase carries.
            kind = next(
                (_KIND_FOR_TAG[tag] for tag in _KIND_PRIORITY if tag in tags),
                "weak_word",
            )
            suggestion, rationale = _suggestion_and_rationale(phrase)
            findings.append(
                Finding(
                    kind=kind,
                    word_index=i,
                    span=(i, j),
                    start=words[i].start,
                    end=words[j].end,
                    original=" ".join(words[k].text for k in range(i, j + 1)),
                    suggestion=suggestion,
                    rationale=rationale,
                    source="lexicon",
                )
            )
            consumed.update(range(i, j + 1))
            break

    # --- Single tokens. ---
    for i, w in enumerate(words):
        if i in consumed:
            continue
        owned = classify_token(w.normalized) & _OWNED_TAGS
        if not owned:
            continue
        tag = next(tag for tag in _KIND_PRIORITY if tag in owned)
        suggestion, rationale = _suggestion_and_rationale(w.normalized)
        findings.append(
            Finding(
                kind=_KIND_FOR_TAG[tag],
                word_index=i,
                span=None,
                start=w.start,
                end=w.end,
                original=w.text,
                suggestion=suggestion,
                rationale=rationale,
                source="lexicon",
            )
        )

    # --- Best-effort proselint pass for extra weasel/hedging coverage. ---
    findings.extend(_proselint_findings(t))

    findings.sort(key=lambda f: f.start)
    return findings


def _proselint_findings(t: Transcript) -> list[Finding]:
    """Run proselint over the surface text and map weasel/hedging hits back to
    the nearest word by character offset. Returns ``[]`` on any error."""
    try:
        from proselint.tools import lint  # type: ignore
    except Exception:
        return []

    words = t.words
    if not words:
        return []

    # Build the surface string and remember each word's character span.
    parts: list[str] = []
    spans: list[tuple[int, int]] = []  # (char_start, char_end) per word index
    pos = 0
    for idx, w in enumerate(words):
        if idx:
            parts.append(" ")
            pos += 1
        start = pos
        parts.append(w.text)
        pos += len(w.text)
        spans.append((start, pos))
    text = "".join(parts)

    try:
        suggestions = lint(text)
    except Exception:
        return []

    out: list[Finding] = []
    for hit in suggestions:
        try:
            check = hit[0]
            offset = int(hit[2])
        except (TypeError, IndexError, ValueError):
            continue
        # Only surface weasel/hedging-style checks to avoid noisy overlap.
        if not any(tag in check for tag in ("weasel", "hedg", "uncomparable", "redundancy")):
            continue
        wi = _nearest_word_index(spans, offset)
        if wi is None:
            continue
        w = words[wi]
        out.append(
            Finding(
                kind="weak_word",
                word_index=wi,
                span=None,
                start=w.start,
                end=w.end,
                original=w.text,
                suggestion=None,
                rationale=str(hit[3]) if len(hit) > 3 else "proselint: weak/weasel phrasing",
                source="rule",
            )
        )
    return out


def _nearest_word_index(spans: list[tuple[int, int]], offset: int) -> int | None:
    """Map a character ``offset`` to the index of the word whose span contains it,
    or the nearest word by distance to its span."""
    if not spans:
        return None
    best_idx = None
    best_dist = None
    for idx, (a, b) in enumerate(spans):
        if a <= offset < b:
            return idx
        dist = a - offset if offset < a else offset - b + 1
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx
