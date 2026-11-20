"""Descriptive delivery metrics with no score bands (see docs/evidence-map.md).

Pure functions over primitives so they unit-test without a Transcript.
"""

from __future__ import annotations


def mean_length_of_run(starts: list[float], ends: list[float], min_pause: float = 0.25) -> float:
    if len(starts) == 0:
        return 0.0

    n_runs = 1
    for i in range(1, len(starts)):
        if starts[i] - ends[i - 1] >= min_pause:
            n_runs += 1

    return round(len(starts) / n_runs, 2)


def opening_body_contrast(starts: list[float], is_filler: list[bool], opening_sec: float = 30.0) -> dict:
    if not starts:
        return {}

    t0 = starts[0]
    opening_indices = [i for i, s in enumerate(starts) if s - t0 < opening_sec]
    body_indices = [i for i, s in enumerate(starts) if s - t0 >= opening_sec]

    opening_words = sum(1 for i in opening_indices if not is_filler[i])
    opening_fillers = sum(1 for i in opening_indices if is_filler[i])
    body_words = sum(1 for i in body_indices if not is_filler[i])
    body_fillers = sum(1 for i in body_indices if is_filler[i])

    if body_words == 0:
        return {}

    opening_rate = round(100 * opening_fillers / opening_words, 2) if opening_words > 0 else 0.0
    body_rate = round(100 * body_fillers / body_words, 2) if body_words > 0 else 0.0

    return {
        "opening_filler_per_100": opening_rate,
        "body_filler_per_100": body_rate,
        "opening_filler_delta": round(opening_rate - body_rate, 2)
    }


def count_tricolons(sentences: list[str], max_item_words: int = 6) -> int:
    count = 0
    for s in sentences:
        s = s.strip().rstrip(".!?").strip()
        parts = [p.strip() for p in s.split(",")]
        if len(parts) < 3:
            continue
        items = parts[-3:]
        joined = False
        if items[2].lower().startswith("and ") or items[2].lower().startswith("or "):
            joined = True
            items[2] = items[2].split(" ", 1)[1].strip()
        if any(len(item.split()) > max_item_words or not item.strip() for item in items):
            continue
        firsts = [item.split()[0].lower() for item in items]
        same_start = firsts[0] == firsts[1] == firsts[2]
        if joined or same_start:
            count += 1
    return count


def mid_clause_pause_share(gaps: list[float], at_boundary: list[bool], min_pause: float = 0.25):
    pauses = [i for i, gap in enumerate(gaps) if gap >= min_pause]
    if not pauses:
        return None

    mid = sum(1 for i in pauses if not at_boundary[i])
    return round(mid / len(pauses), 3)
