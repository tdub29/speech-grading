"""Detect verbatim repetitions and false starts in a Transcript.

Pure, deterministic, offline rule pass over the normalized token stream. Catches
three disfluency patterns a fluent speaker would edit out:

  (a) Immediate single-token repeats  -- "we we", "the the".
  (b) Immediate bigram repeats        -- "in the in the".
  (c) Partial-word / false starts     -- a clipped token ("rev-") or a token that
      is a strict prefix of the next ("comp" -> "company"), i.e. a self-correction.

Each pattern yields a uniform :class:`~speech_grading.schema.Finding`. Overlapping
(a)/(b) emissions are suppressed (a bigram repeat absorbs the single-token repeat
that would otherwise fire inside it). Results are returned sorted by ``start``.
"""

from __future__ import annotations

from speech_grading.schema import Finding, Transcript

# Very common short words that are real words, not clipped fragments. A bare
# prefix match against the next word ("to" before "today", "we" before "went")
# must NOT be read as a self-correction when the prefix is one of these.
_COMMON_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "for", "go",
    "he", "i", "if", "in", "is", "it", "me", "my", "no", "of", "on", "or", "so",
    "to", "up", "us", "we", "the", "was", "you", "all", "can", "her", "him",
    "his", "how", "its", "let", "our", "out", "see", "she", "the", "too", "use",
    "way", "who", "why", "win", "yes", "yet", "your", "this", "that", "they",
    "them", "then", "than", "with", "have", "from", "were", "want", "well",
}


def _make_finding(t: Transcript, i: int, j: int, kind: str, rationale: str) -> Finding:
    """Build a Finding spanning words i..j (inclusive). word_index anchors on i."""
    return Finding(
        kind=kind,
        word_index=i,
        span=(i, j),
        start=t.words[i].start,
        end=t.words[j].end,
        original=" ".join(t.words[k].text for k in range(i, j + 1)),
        rationale=rationale,
        source="rule",
    )


def detect_repetitions(t: Transcript) -> list[Finding]:
    """Return repetition / false-start findings for ``t``, sorted by start time."""
    words = t.words
    n = len(words)
    findings: list[Finding] = []

    # Track word indices already consumed by a bigram repeat so the single-token
    # rule does not double-emit inside them.
    bigram_consumed: set[int] = set()

    # (b) Immediate bigram repeat: normalized [i-3, i-2] == [i-1, i].
    for i in range(3, n):
        a, b = words[i - 3].normalized, words[i - 2].normalized
        c, d = words[i - 1].normalized, words[i].normalized
        if not (a and b and c and d):
            continue
        if a == c and b == d:
            findings.append(
                _make_finding(
                    t,
                    i - 3,
                    i,
                    "repetition",
                    f"Immediate repetition of '{a} {b}'",
                )
            )
            bigram_consumed.update(range(i - 3, i + 1))

    # (a) Immediate single-token repeat: normalized[i] == normalized[i-1].
    for i in range(1, n):
        tok = words[i].normalized
        if not tok or len(tok) < 1:
            continue
        if tok != words[i - 1].normalized:
            continue
        # Skip if this pair is already covered by a bigram repeat.
        if i in bigram_consumed and (i - 1) in bigram_consumed:
            continue
        findings.append(
            _make_finding(
                t,
                i - 1,
                i,
                "repetition",
                f"Immediate repetition of '{tok}'",
            )
        )

    # (c) Partial-word / false start.
    for i in range(n):
        surface = words[i].text.strip()
        cur = words[i].normalized
        is_false_start = False
        if surface.endswith("-"):
            is_false_start = True  # explicitly clipped token from the ASR
        elif i + 1 < n:
            nxt = words[i + 1].normalized
            # A no-hyphen prefix match is only a real restart when the prefix is
            # itself NOT a common word (so "comp"->"company" fires but "to"->"today"
            # and "we"->"went" do not) and the continuation adds a real suffix.
            if (
                2 <= len(cur) <= 4
                and nxt
                and cur != nxt
                and nxt.startswith(cur)
                and cur not in _COMMON_WORDS
                and 1 <= (len(nxt) - len(cur)) <= 6
            ):
                is_false_start = True
        if is_false_start:
            findings.append(
                _make_finding(
                    t,
                    i,
                    i,
                    "false_start",
                    "Self-correction / restart",
                )
            )

    findings.sort(key=lambda f: f.start)
    return findings
