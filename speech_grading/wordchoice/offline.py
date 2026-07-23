"""Deterministic offline word-choice + tripped-up detector.

This is the source of record for word-choice findings. It needs no network or model.
The signature feature lives here: :func:`detect_tripped_up` fuses several signals on a
shared time axis to surface moments where the speaker hesitated and reached for a
worse word, rather than firing on a lexical match alone.

  event_score = w_hedge*hedge + w_vague*vague + w_pause*pause_norm
              + w_low_conf*(low ASR confidence) + w_filled_pause*(filler just before)
              + w_repair*(repetition / restart just before)

A lexical flag by itself is NOT enough; it must co-occur with a timing/disfluency
signal (a pause, a low-confidence word, a filler, or a repair) to clear the threshold.
"""

from __future__ import annotations

from typing import Optional

from ..config import Config, DEFAULT_THRESHOLDS
from ..lexicons import (
    FILLED_PAUSES,
    HEDGES,
    INTENSIFIERS,
    PHRASE_TAGS,
    REPLACEMENTS,
    WEAK,
    WEASEL,
    classify_token,
)
from ..norms import concreteness, frequency, specificity_gain
from ..schema import Finding, Transcript, WordChoiceFinding
from .base import WordChoiceAnalyzer


def _pause_norm(gap: float, median: float) -> float:
    """0 below (median + 0.2s), ramping to 1.0 by (median + 1.0s)."""
    lo = median + 0.2
    return max(0.0, min(1.0, (gap - lo) / 0.8))


def _low_conf_signal(conf: Optional[float], threshold: float) -> float:
    if conf is None:
        return 0.0
    if conf >= threshold:
        return 0.0
    return min(1.0, (threshold - conf) / max(threshold, 1e-6))


def detect_tripped_up(
    t: Transcript,
    findings: Optional[list[Finding]] = None,
    weights: Optional[dict] = None,
) -> list[Finding]:
    """Fuse lexical + timing + disfluency signals into ranked tripped-up moments.

    ``findings`` is accepted for API compatibility but the signals are recomputed
    from the transcript so the detector is self-contained.
    """
    weights = weights or DEFAULT_THRESHOLDS["tripped_up_weights"]
    min_score = DEFAULT_THRESHOLDS["tripped_up_min_score"]
    low_conf_threshold = DEFAULT_THRESHOLDS["low_conf_threshold"]
    median = t.speaker_median_gap
    words = t.words
    out: list[Finding] = []

    for i, w in enumerate(words):
        if w.is_filled_pause:
            continue
        tok = w.normalized
        if not tok:
            continue
        tags = classify_token(tok)
        hedge = 1.0 if (tok in HEDGES or "hedge" in tags) else 0.0
        vague = 1.0 if (tok in WEASEL or tok in WEAK) else 0.0
        pause = _pause_norm(t.gap_before(i), median)
        low_conf = _low_conf_signal(w.confidence, low_conf_threshold)
        prev = words[i - 1] if i > 0 else None
        filled = 1.0 if (prev and (prev.is_filled_pause or prev.normalized in FILLED_PAUSES)) else 0.0
        repair = 1.0 if (prev and prev.normalized and prev.normalized == tok) else 0.0

        signals = {
            "hedge": hedge,
            "vague": vague,
            "pause": pause,
            "low_conf": low_conf,
            "filled_pause": filled,
            "repair": repair,
        }
        score = sum(weights.get(k, 0.0) * v for k, v in signals.items())
        if score < min_score:
            continue

        active = [k for k, v in signals.items() if v >= 0.5]
        rationale = _tripped_rationale(active, w.text)
        out.append(
            Finding(
                kind="tripped_up",
                word_index=i,
                start=w.start,
                end=w.end,
                original=w.text,
                suggestion=rank_replacement(tok),
                rationale=rationale,
                score=round(min(1.0, score), 3),
                source="rule",
            )
        )
    out.sort(key=lambda f: f.start)
    return out


def _tripped_rationale(active: list[str], word: str) -> str:
    bits = {
        "pause": "a long hesitation pause before it",
        "low_conf": "low recognition confidence (slurred or unclear)",
        "filled_pause": "a filler right before it",
        "repair": "a repeated/restarted word",
        "hedge": "hedging language",
        "vague": "a vague word choice",
    }
    reasons = [bits[a] for a in active if a in bits]
    if not reasons:
        return f"Possible word-finding stumble around '{word}'."
    return f"Stumble around '{word}': " + ", ".join(reasons) + "."


def rank_replacement(word: str) -> Optional[str]:
    """Suggest a stronger replacement, or None.

    Prefers the curated map; otherwise ranks WordNet synonyms by how much more
    concrete (and not absurdly rare) they are than the original.
    """
    repl = REPLACEMENTS.get(word)
    if repl:  # non-empty curated replacement
        return repl
    return _wordnet_replacement(word)


def _wordnet_replacement(word: str) -> Optional[str]:
    try:
        from nltk.corpus import wordnet as wn
    except Exception:  # noqa: BLE001 - WordNet data may be absent
        return None
    try:
        synsets = wn.synsets(word)
    except LookupError:
        return None
    candidates: set[str] = set()
    for syn in synsets[:6]:
        for lemma in syn.lemmas():
            name = lemma.name().replace("_", " ").lower()
            if name != word and " " not in name and name.isalpha():
                candidates.add(name)
    best: Optional[str] = None
    best_key = (0.0, -1.0)
    for cand in candidates:
        gain = specificity_gain(word, cand)
        freq = frequency(cand)
        if gain <= 0.0:  # only suggest a more concrete word
            continue
        key = (gain, freq if freq is not None else 0.0)
        if key > best_key:
            best_key = key
            best = cand
    return best


class OfflineWordChoice(WordChoiceAnalyzer):
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def analyze(self, t: Transcript) -> list[WordChoiceFinding]:
        out: list[WordChoiceFinding] = []
        seen: set[tuple[int, str]] = set()

        # Tripped-up moments (the signature signal).
        for f in detect_tripped_up(t, None, self.cfg.thresholds.get("tripped_up_weights")):
            key = (f.word_index, "tripped_up")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                WordChoiceFinding(
                    word_index=f.word_index,
                    issue_type="tripped_up",
                    original=f.original,
                    suggestion=f.suggestion,
                    rationale=f.rationale,
                    confidence=f.score,
                )
            )

        # Better-word suggestions for weak/hedge single tokens with a known replacement.
        for i, w in enumerate(t.words):
            tok = w.normalized
            if not tok:
                continue
            tags = classify_token(tok)
            issue = _issue_for_tags(tags)
            if issue is None:
                continue
            suggestion = rank_replacement(tok)
            if suggestion is None and tok not in REPLACEMENTS:
                continue
            if suggestion is None:  # curated empty replacement = "cut it"
                suggestion = ""
            key = (i, issue)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                WordChoiceFinding(
                    word_index=i,
                    issue_type=issue,
                    original=w.text,
                    suggestion=suggestion,
                    rationale=_weak_rationale(issue, tok, suggestion),
                    confidence=0.6,
                )
            )

        # Multiword weak/hedge phrases with curated replacements.
        out.extend(self._phrase_findings(t, seen))
        out.sort(key=lambda f: f.word_index)
        return out

    def _phrase_findings(self, t: Transcript, seen: set) -> list[WordChoiceFinding]:
        words = t.words
        n = len(words)
        results: list[WordChoiceFinding] = []
        for phrase, tags in PHRASE_TAGS.items():
            if not (tags & {"hedge", "weasel", "weak"}):
                continue
            toks = phrase.split()
            plen = len(toks)
            for i in range(0, n - plen + 1):
                window = [words[j].normalized for j in range(i, i + plen)]
                if window != toks:
                    continue
                key = (i, "phrase:" + phrase)
                if key in seen:
                    continue
                seen.add(key)
                suggestion = REPLACEMENTS.get(phrase, "")
                issue = "hedge" if "hedge" in tags else "weak"
                original = " ".join(words[j].text for j in range(i, i + plen))
                results.append(
                    WordChoiceFinding(
                        word_index=i,
                        issue_type=issue,
                        original=original,
                        suggestion=suggestion,
                        rationale=_weak_rationale(issue, phrase, suggestion),
                        confidence=0.6,
                    )
                )
        return results


def _issue_for_tags(tags: set) -> Optional[str]:
    if "hedge" in tags:
        return "hedge"
    if tags & {"weasel", "intensifier", "weak"}:
        return "weak"
    return None


def _weak_rationale(issue: str, original: str, suggestion: str) -> str:
    if suggestion == "":
        return f"'{original}' is filler/hedging that weakens the point; cut it."
    if issue == "hedge":
        return f"'{original}' hedges; state it directly (try '{suggestion}')."
    return f"'{original}' is vague; a stronger word like '{suggestion}' lands harder."
