"""Pace analysis: speaking rate and its consistency over time.

Computes two complementary rates from a canonical :class:`Transcript`:

* ``overall_wpm`` -- real lexical words over wall-clock duration (the listener's
  felt pace, silences included).
* ``articulation_wpm`` -- real lexical words over phonation time only (raw
  articulation speed with silence removed).

Consistency is the population standard deviation of rolling-window WPM across the
sample: a low value means an even, controlled delivery; a high value means the
speaker surges and stalls. Banding and points reward staying inside the ideal WPM
band *and* keeping that pace steady.

Pure function, no external dependencies beyond the foundation modules and stdlib.
"""

from __future__ import annotations

import re
import statistics

from speech_grading.schema import DimensionScore, Transcript


def _rate(n_words: int, seconds: float) -> float:
    """Words per minute for ``n_words`` over ``seconds`` (0.0 when no time)."""
    return n_words / (seconds / 60.0) if seconds > 0 else 0.0


def _window_wpms(t: Transcript, window_sec: float) -> list[float]:
    """Rolling-window WPM across [first word start, last word end].

    Each window is ``window_sec`` long; its WPM counts the real lexical words whose
    *start* falls inside the window, divided by the window length in minutes. Windows
    are non-overlapping and tile the span; a partial final window is included.
    Filled-pause tokens never contribute to the word count.
    """
    if not t.words or window_sec <= 0:
        return []

    # Tile each of this speaker's turns separately (one turn when unfiltered), so time
    # spent listening to another speaker never reads as a 0-WPM window.
    bounds = sorted({0, *t.turn_starts}) + [len(t.words)]
    wpms: list[float] = []
    for a, b in zip(bounds, bounds[1:]):
        seg = t.words[a:b]
        if not seg:
            continue
        span_start = min(w.start for w in seg)
        span_end = max(w.end for w in seg)
        starts = [w.start for w in seg if not w.is_filled_pause]
        lo = span_start
        while lo < span_end:
            hi = lo + window_sec
            count = sum(1 for s in starts if lo <= s < hi)
            wpms.append(_rate(count, window_sec))
            lo = hi
    return wpms


_VOWEL_RUN = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    """Rough English syllable count: vowel groups, silent final e dropped, min 1.

    ponytail: heuristic (about 90% on common words); swap for a CMUdict lookup if
    articulation rate ever drives a score rather than a detail metric.
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n = len(_VOWEL_RUN.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def articulation_sps(t: Transcript, pause_sec: float = 0.25) -> float:
    """Syllables per second of speaking time: total time minus silent pauses >= pause_sec.

    de Jong and Wempe 2009 definition (speech-fluency-measurement skill). Turn gaps after a
    speaker filter already read 0 in gap_before, so they never count as speaking time
    because duration_sec already excludes them.
    """
    syl = sum(count_syllables(w.text) for w in t.words if not w.is_filled_pause)
    pauses = sum(g for i in range(1, len(t.words)) if (g := t.gap_before(i)) >= pause_sec)
    speak = t.duration_sec - pauses
    return round(syl / speak, 3) if speak > 0 else 0.0


def compute_pace(t: Transcript, thresholds: dict) -> DimensionScore:
    """Score speaking pace (WPM) and its consistency.

    Returns a :class:`DimensionScore` with ``weight=0`` and no findings; pace is a
    measured dimension, not a per-word flag track. ``raw`` is the overall WPM.
    """
    ideal_low = thresholds.get("wpm_ideal_low", 130.0)
    ideal_high = thresholds.get("wpm_ideal_high", 160.0)
    fair_low = thresholds.get("wpm_fair_low", 110.0)
    fair_high = thresholds.get("wpm_fair_high", 180.0)
    window_sec = thresholds.get("wpm_window_sec", 10.0)
    consistency_full = thresholds.get("wpm_consistency_full", 15.0)
    consistency_dock = thresholds.get("wpm_consistency_dock", 35.0)

    # Gaps longer than the cap are applause, crowd or dead air, not the speaker's pacing:
    # counting them dragged every applause-heavy political speech in the corpus to "poor".
    # ASR may instead hang the applause on a word's end time (a 16.6 s "and" under
    # Whisper small, where medium puts the same applause in a gap), so a word held past
    # word_cap is trimmed to the median word length and its overhang joins the next gap:
    # one applause break then costs the same clock either way.
    gap_cap = thresholds.get("wpm_gap_cap_sec", 2.0)
    word_cap = thresholds.get("wpm_word_cap_sec", 1.5)
    ws = t.words
    typical = statistics.median(w.end - w.start for w in ws) if ws else 0.0
    eff_end = [w.start + typical if w.end - w.start > word_cap else w.end for w in ws]
    held = sum(w.end - e for w, e in zip(ws, eff_end))
    excess = sum(max(0.0, ws[i].start - eff_end[i - 1] - gap_cap)
                 for i in range(1, len(ws)) if i not in t.turn_starts)  # turns: other speaker's time
    excess += max(0.0, ws[-1].end - eff_end[-1] - gap_cap) if ws else 0.0  # held last word
    wall_wpm = _rate(t.total_words, t.duration_sec)
    overall_wpm = _rate(t.total_words, t.duration_sec - excess)
    articulation_wpm = _rate(t.total_words, t.speaking_sec - held)

    window_wpms = _window_wpms(t, window_sec)
    k = len(window_wpms)
    consistency = statistics.pstdev(window_wpms) if k >= 2 else 0.0

    # --- Band ---------------------------------------------------------------- #
    in_ideal = ideal_low <= overall_wpm <= ideal_high
    in_fair = (fair_low <= overall_wpm < ideal_low) or (ideal_high < overall_wpm <= fair_high)
    if in_ideal and consistency <= consistency_full:
        band = "excellent"
    elif in_ideal:
        band = "good"
    elif in_fair:
        band = "fair"
    else:
        band = "poor"

    # --- Points (0-100) ------------------------------------------------------ #
    points = 100.0

    # Distance penalty: how far overall_wpm sits outside the ideal band, scaled by
    # the fair margin so reaching the fair edge costs ~50 points on that side.
    if overall_wpm < ideal_low:
        margin = ideal_low - fair_low
        over = ideal_low - overall_wpm
        points -= 50.0 * (over / margin) if margin > 0 else 50.0
    elif overall_wpm > ideal_high:
        margin = fair_high - ideal_high
        over = overall_wpm - ideal_high
        points -= 50.0 * (over / margin) if margin > 0 else 50.0

    # Consistency penalty: linear between the full (no penalty) and dock (full
    # penalty) stdev thresholds, worth up to 50 points.
    span = consistency_dock - consistency_full
    if consistency > consistency_full and span > 0:
        frac = min(1.0, (consistency - consistency_full) / span)
        points -= 50.0 * frac
    elif consistency > consistency_full:
        points -= 50.0

    points = max(0.0, min(100.0, points))

    return DimensionScore(
        dimension="pace",
        raw=overall_wpm,
        band=band,
        points=points,
        weight=0.0,
        findings=[],
        detail={
            "wpm": overall_wpm,
            "wall_clock_wpm": wall_wpm,
            "articulation_wpm": articulation_wpm,
            "articulation_sps": articulation_sps(t, thresholds.get("pause_micro", 0.25)),
            "consistency": consistency,
            "n_windows": k,
        },
    )
