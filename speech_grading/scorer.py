"""Construct-driven 0-100 composite scorer.

Each rubric dimension produces a :class:`DimensionScore`. Four dimensions are
measured by leaf modules (pace, vocabulary, readability, prosody) and passed in as
``dim_scores``; the other four are derived here from the flat finding list
(fillers, pauses/fluency, hedging, word_choice). Weights come from the config and
are normalized so the composite is always on a 0-100 scale even when a dimension is
absent (e.g. prosody when there is no audio) -- its weight is redistributed
proportionally across the dimensions that are present.

To avoid penalizing the same underlying problem four times, fillers / pauses /
hedging / repetitions are kept as *separate* dimensions but each is scored once,
and the report always shows the timestamped evidence behind every sub-score.
"""

from __future__ import annotations

from typing import Optional

from .config import Config
from .schema import DimensionScore, Finding, Report, Transcript

_BAND_POINTS = {"excellent": 100.0, "good": 82.0, "fair": 58.0, "poor": 28.0}

# Dimensions measured by leaf modules and supplied via dim_scores.
_MEASURED = ("pace", "vocabulary", "readability", "prosody")


def _per_minute(count: float, minutes: float) -> float:
    return count / minutes if minutes > 0 else 0.0


def _fillers_dim(findings: list[Finding], t: Transcript, cfg: Config) -> DimensionScore:
    # Real filler detectors (lexicon + acoustic), not LLM word-choice fillers.
    items = [f for f in findings if f.kind == "filler" and f.source != "wordchoice"]
    total = max(1, t.total_words)
    rate = len(items) / total * 100.0
    th = cfg.thresholds
    if rate < th.get("filler_excellent", 2.0):
        band = "excellent"
    elif rate < th.get("filler_good", 4.0):
        band = "good"
    elif rate < th.get("filler_fair", 6.0):
        band = "fair"
    else:
        band = "poor"
    return DimensionScore(
        dimension="fillers",
        raw=round(rate, 2),
        band=band,
        points=_BAND_POINTS[band],
        weight=0.0,
        findings=items,
        detail={
            "filler_count": len(items),
            "filler_rate_per_100w": round(rate, 2),
            "fillers_per_minute": round(_per_minute(len(items), t.minutes), 2),
        },
    )


def _pauses_dim(findings: list[Finding], t: Transcript) -> DimensionScore:
    long_pauses = [f for f in findings if f.kind == "long_pause"]
    repeats = [f for f in findings if f.kind in ("repetition", "false_start")]
    # Disfluency load per minute: long pauses count full, repairs count a bit less.
    load = len(long_pauses) + 0.7 * len(repeats)
    per_min = _per_minute(load, t.minutes)
    if per_min < 1.0:
        band = "excellent"
    elif per_min < 2.5:
        band = "good"
    elif per_min < 4.0:
        band = "fair"
    else:
        band = "poor"
    return DimensionScore(
        dimension="pauses",
        raw=round(per_min, 2),
        band=band,
        points=_BAND_POINTS[band],
        weight=0.0,
        findings=long_pauses + repeats,
        detail={
            "long_pauses": len(long_pauses),
            "repetitions": len(repeats),
            "disfluency_per_minute": round(per_min, 2),
        },
    )


def _hedging_dim(findings: list[Finding], t: Transcript) -> DimensionScore:
    # Lexical hedge/booster track (from the weak_words module), not the LLM/offline
    # word-choice suggestions (those carry source='wordchoice').
    items = [
        f
        for f in findings
        if f.kind in ("hedge", "weasel", "intensifier", "weak_word")
        and f.source != "wordchoice"
    ]
    total = max(1, t.total_words)
    density = len(items) / total * 100.0
    if density < 3.0:
        band = "excellent"
    elif density < 6.0:
        band = "good"
    elif density < 10.0:
        band = "fair"
    else:
        band = "poor"
    return DimensionScore(
        dimension="hedging",
        raw=round(density, 2),
        band=band,
        points=_BAND_POINTS[band],
        weight=0.0,
        findings=items,
        detail={"hedge_count": len(items), "hedge_density_per_100w": round(density, 2)},
    )


def _word_choice_dim(findings: list[Finding], t: Transcript) -> DimensionScore:
    tripped = [f for f in findings if f.kind == "tripped_up"]
    high = [f for f in tripped if f.score >= 0.6]
    severity = sum(f.score for f in tripped)
    if not tripped:
        band = "excellent"  # no word-finding stumbles at all
    elif not high and severity < 1.5:
        band = "good"       # a few low-severity moments
    elif len(high) <= 2:
        band = "fair"
    else:
        band = "poor"
    suggestions = sum(1 for f in findings if f.suggestion)
    return DimensionScore(
        dimension="word_choice",
        raw=round(severity, 2),
        band=band,
        points=_BAND_POINTS[band],
        weight=0.0,
        findings=tripped,
        detail={
            "tripped_up": len(tripped),
            "high_severity": len(high),
            "severity_sum": round(severity, 2),
            "suggestions_offered": suggestions,
        },
    )


def score(
    t: Transcript,
    all_findings: list[Finding],
    dim_scores: list[DimensionScore],
    cfg: Config,
    word_choice_mode: Optional[str] = None,
) -> Report:
    """Combine findings and measured dimensions into a weighted 0-100 Report.

    ``word_choice_mode`` is the analyzer that actually produced the word-choice
    findings ('claude' or 'offline-lexicon'); when omitted it is inferred from the
    config (used by callers that score pre-built finding lists directly).
    """
    measured = {ds.dimension: ds for ds in dim_scores if ds is not None}

    dims: dict[str, DimensionScore] = {
        "fillers": _fillers_dim(all_findings, t, cfg),
        "pace": measured.get("pace"),
        # Pauses need word timing; on a text-only transcript we can't assess them,
        # so the dimension is omitted (its weight is redistributed) rather than
        # claiming a perfect score.
        "pauses": _pauses_dim(all_findings, t) if t.has_timing else None,
        "word_choice": _word_choice_dim(all_findings, t),
        "vocabulary": measured.get("vocabulary"),
        "hedging": _hedging_dim(all_findings, t),
        "readability": measured.get("readability"),
        "prosody": measured.get("prosody"),
    }

    # Keep only present dimensions and attach configured weights.
    present: list[DimensionScore] = []
    for name, ds in dims.items():
        if ds is None:
            continue
        ds.weight = cfg.weights.get(name, 0.0)
        present.append(ds)

    total_weight = sum(ds.weight for ds in present) or 1.0
    overall = sum(ds.points * (ds.weight / total_weight) for ds in present)
    # Reflect the normalized (post-redistribution) weight back onto each dimension.
    # Keep full precision so the weights sum to 1.0; round only for display.
    for ds in present:
        ds.weight = ds.weight / total_weight

    report = Report(
        overall_score=round(overall, 1),
        dimensions=present,
        findings=sorted(all_findings, key=lambda f: f.start),
        transcript=t,
        metrics=_metrics(present, t),
        metadata={
            "engine": t.engine,
            "word_choice_mode": word_choice_mode
            or ("claude" if cfg.use_llm else "offline-lexicon"),
            "weights": {ds.dimension: round(ds.weight, 4) for ds in present},
            "version": "0.1.0",
        },
        summary=_summary(round(overall, 1), present),
    )
    return report


def _metrics(present: list[DimensionScore], t: Transcript) -> dict:
    bag: dict = {
        "total_words": t.total_words,
        "duration_sec": round(t.duration_sec, 2),
        "speaking_sec": round(t.speaking_sec, 2),
    }
    for ds in present:
        for k, v in ds.detail.items():
            bag[k] = v
    return bag


def _summary(overall: float, present: list[DimensionScore]) -> str:
    grade = (
        "excellent" if overall >= 90 else
        "strong" if overall >= 78 else
        "solid" if overall >= 65 else
        "developing" if overall >= 50 else
        "needs work"
    )
    weak = sorted(present, key=lambda d: d.points)[:2]
    focus = ", ".join(d.dimension.replace("_", " ") for d in weak) if weak else "nothing major"
    return (
        f"Overall {overall}/100 ({grade}). "
        f"Biggest opportunities: {focus}."
    )
