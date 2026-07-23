"""Lexical norm tables for ranking better-word suggestions.

Looks up word *concreteness* (Brysbaert et al. 2014) and *frequency* (SUBTLEX-US)
to rank candidate replacements: a stronger word is usually more concrete and not
absurdly rare. Full norm CSVs are large, so they are optional drop-ins under
``speech_grading/data/`` (``concreteness.csv`` with columns ``Word,Conc.M`` and
``subtlex.csv`` with columns ``Word,Lg10WF``). A small built-in table keeps the
offline path useful without the downloads. All lookups return ``None`` when unknown,
so callers degrade gracefully.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from typing import Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Tiny built-in fallback (concreteness 1-5 scale, Brysbaert-style). Enough to rank a
# few common abstract->concrete swaps when the full CSV is absent.
_BUILTIN_CONCRETENESS: dict[str, float] = {
    "thing": 1.4, "things": 1.4, "stuff": 1.6, "something": 1.3, "aspect": 1.6,
    "factor": 1.7, "issue": 1.8, "area": 2.4, "way": 1.8, "part": 2.3,
    "nice": 1.6, "good": 1.7, "bad": 1.8, "great": 1.9, "important": 1.6,
    "data": 2.6, "result": 2.2, "report": 3.6, "document": 4.0, "chart": 4.4,
    "dashboard": 4.2, "model": 3.2, "budget": 3.3, "deadline": 3.0,
    "dog": 5.0, "table": 4.9, "car": 4.9, "house": 4.9, "money": 4.4,
}

_BUILTIN_FREQ: dict[str, float] = {  # Lg10 word frequency (higher = more common)
    "thing": 4.6, "things": 4.5, "stuff": 4.0, "good": 5.1, "nice": 4.3,
    "data": 3.4, "report": 3.3, "document": 2.9, "model": 3.1, "budget": 2.9,
    "use": 4.6, "many": 4.5, "because": 4.9, "now": 5.2, "several": 3.3,
}


@lru_cache(maxsize=1)
def _concreteness_table() -> dict[str, float]:
    table = dict(_BUILTIN_CONCRETENESS)
    path = os.path.join(_DATA_DIR, "concreteness.csv")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            wcol = _pick(reader.fieldnames, ("Word", "word"))
            ccol = _pick(reader.fieldnames, ("Conc.M", "concreteness", "Conc_M"))
            if wcol and ccol:
                for row in reader:
                    try:
                        table[row[wcol].strip().lower()] = float(row[ccol])
                    except (ValueError, KeyError, TypeError):
                        continue
    return table


@lru_cache(maxsize=1)
def _frequency_table() -> dict[str, float]:
    table = dict(_BUILTIN_FREQ)
    path = os.path.join(_DATA_DIR, "subtlex.csv")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            wcol = _pick(reader.fieldnames, ("Word", "word"))
            fcol = _pick(reader.fieldnames, ("Lg10WF", "Lg10Wf", "frequency"))
            if wcol and fcol:
                for row in reader:
                    try:
                        table[row[wcol].strip().lower()] = float(row[fcol])
                    except (ValueError, KeyError, TypeError):
                        continue
    return table


def _pick(fieldnames, candidates) -> Optional[str]:
    if not fieldnames:
        return None
    lookup = {f.lower(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None


def concreteness(word: str) -> Optional[float]:
    """Concreteness rating (≈1 abstract .. 5 concrete), or None if unknown."""
    return _concreteness_table().get(word.strip().lower())


def frequency(word: str) -> Optional[float]:
    """Lg10 word frequency (higher = more common), or None if unknown."""
    return _frequency_table().get(word.strip().lower())


def specificity_gain(orig: str, cand: str) -> float:
    """How much more specific/concrete ``cand`` is than ``orig``.

    Positive => candidate is the stronger (more concrete) word. Returns 0.0 when
    either concreteness value is unknown so ranking falls back to other signals.
    """
    co = concreteness(orig)
    cc = concreteness(cand)
    if co is None or cc is None:
        return 0.0
    return cc - co
