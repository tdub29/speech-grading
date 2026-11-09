"""Visual event detectors over per-frame face/hand/pose features.

Pure functions: no mediapipe import, no IO. A frame is a dict with keys
t, smile, brow_raise, brow_furrow, jaw_open, gaze_off, pitch_deg,
hand_face_dist, wrist_y_rel, face_visible (any may be None when untracked).
Events are behavior counts, not verdicts: the cues are tendencies, not
reliable indicators of confidence or nervousness.
"""
from __future__ import annotations

from statistics import mean
from typing import Callable, Optional

from ..schema import Finding

_BASE_KEYS = ("smile", "brow_raise", "brow_furrow", "jaw_open", "gaze_off", "pitch_deg")


def baseline(frames: list[dict], first_sec: float = 30.0) -> dict:
    """Per-speaker mean of each feature over the first `first_sec` seconds."""
    if not frames:
        return {}
    t0 = frames[0]["t"]
    head = [f for f in frames if f["t"] - t0 <= first_sec and f.get("face_visible")]
    out = {}
    for k in _BASE_KEYS:
        vals = [f[k] for f in head if f.get(k) is not None]
        if vals:
            out[k] = mean(vals)
    return out


def data_quality(frames: list[dict]) -> dict:
    """Fraction of frames with a visible face and with a tracked hand."""
    n = len(frames)
    if not n:
        return {"face_visible_pct": 0.0, "hands_visible_pct": 0.0}
    face = sum(1 for f in frames if f.get("face_visible"))
    hands = sum(1 for f in frames if f.get("hand_face_dist") is not None)
    return {"face_visible_pct": 100 * face / n, "hands_visible_pct": 100 * hands / n}


def _runs(frames: list[dict], pred: Callable[[dict], bool], min_dur: float, max_gap: float):
    """Yield (start, end) of runs where pred holds; a gap > max_gap breaks a run."""
    start = last = None
    for f in frames:
        if pred(f):
            if start is None:
                start = f["t"]
            elif f["t"] - last > max_gap:
                if last - start >= min_dur:
                    yield start, last
                start = f["t"]
            last = f["t"]
        elif start is not None and f["t"] - last > max_gap:
            if last - start >= min_dur:
                yield start, last
            start = None
    if start is not None and last - start >= min_dur:
        yield start, last


def _finding(kind: str, start: float, end: float, rationale: str, score: float = 1.0) -> Finding:
    return Finding(kind=kind, word_index=-1, start=start, end=end,
                   rationale=rationale, score=score, source="rule")


def detect_face_touch(frames, touch_dist=0.15, min_dur=0.4, max_gap=0.3) -> list[Finding]:
    def touching(f):
        d = f.get("hand_face_dist")
        return d is not None and d < touch_dist
    return [_finding("face_touch", s, e, f"hand near face for {e - s:.1f}s")
            for s, e in _runs(frames, touching, min_dur, max_gap)]


def detect_chin_up(frames, base, thresh_deg=8.0, min_dur=1.0, max_gap=0.3) -> list[Finding]:
    b = base.get("pitch_deg")
    if b is None:
        return []
    def up(f):
        p = f.get("pitch_deg")
        return p is not None and p >= b + thresh_deg
    return [_finding("chin_up", s, e, f"head pitched up >{thresh_deg:.0f} deg for {e - s:.1f}s")
            for s, e in _runs(frames, up, min_dur, max_gap)]


def smile_after_sentence(frames, sentence_end_times, base, window=0.6, rise=0.25) -> list[Finding]:
    b = base.get("smile")
    if b is None:
        return []
    out = []
    for end in sentence_end_times:
        vals = [f["smile"] for f in frames
                if end <= f["t"] <= end + window and f.get("smile") is not None]
        if vals and max(vals) - b >= rise:
            out.append(_finding("auto_smile", end, end + window, "smile rise right after a sentence"))
    return out


def gaze_check_after_sentence(frames, sentence_end_times, window=0.6, off=0.5) -> list[Finding]:
    out = []
    for end in sentence_end_times:
        vals = [f["gaze_off"] for f in frames
                if end <= f["t"] <= end + window and f.get("gaze_off") is not None]
        if vals and sum(v > off for v in vals) / len(vals) > 0.5:
            out.append(_finding("reaction_check", end, end + window, "gaze left camera right after a sentence"))
    return out


# Per-mode thresholds and which cues are valid. Modes differ: a seated Zoom call
# crops hands and looks at a screen; a stage talk is wide, hands visible, gaze
# sweeps the room; a phone selfie is close and handheld. Tune from labeled data.
PROFILES: dict[str, dict] = {
    "default":   dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.5, need_hands=0.2, cues={"face_touch", "chin_up", "auto_smile", "reaction_check"}),
    "zoom":      dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.6, need_hands=0.2, cues={"face_touch", "chin_up", "auto_smile"}),   # gaze unreliable: screen below lens
    "phone":     dict(touch_dist=0.20, chin_thresh=10.0, gaze_off=0.5, need_hands=0.2, cues={"face_touch", "chin_up", "auto_smile", "reaction_check"}),
    "stage":     dict(touch_dist=0.12, chin_thresh=8.0, gaze_off=0.8, need_hands=0.2, cues={"face_touch", "chin_up"}),                 # audience scan is normal
    "interview": dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.7, need_hands=0.2, cues={"face_touch", "chin_up", "auto_smile"}),   # looks at interviewer
}


def summarize(frames: list[dict], sentence_ends: list[float], mode: str = "default") -> dict:
    """Run every valid cue for `mode`; return findings, per-minute rates, quality, skipped cues."""
    p = PROFILES.get(mode, PROFILES["default"])
    q = data_quality(frames)
    base = baseline(frames)
    skipped = {}
    if q["face_visible_pct"] < 60:
        return {"mode": mode, "quality": q, "findings": [], "rates_per_min": {},
                "skipped": {c: "face visible <60%" for c in p["cues"]}}
    found: list[Finding] = []
    for cue in sorted(p["cues"]):
        if cue == "face_touch":
            if q["hands_visible_pct"] < 100 * p["need_hands"]:
                skipped[cue] = "hands rarely in frame"; continue
            found += detect_face_touch(frames, touch_dist=p["touch_dist"])
        elif cue == "chin_up":
            found += detect_chin_up(frames, base, thresh_deg=p["chin_thresh"])
        elif cue == "auto_smile":
            found += smile_after_sentence(frames, sentence_ends, base)
        elif cue == "reaction_check":
            found += gaze_check_after_sentence(frames, sentence_ends, off=p["gaze_off"])
    minutes = max((frames[-1]["t"] - frames[0]["t"]) / 60, 1e-9) if len(frames) > 1 else 1e-9
    rates: dict[str, float] = {}
    for f in found:
        rates[f.kind] = rates.get(f.kind, 0) + 1
    return {"mode": mode, "quality": q, "findings": found, "skipped": skipped,
            "rates_per_min": {k: round(n / minutes, 2) for k, n in rates.items()}}


def feature_rows(frames: list[dict], win: float = 5.0, mode: str = "default") -> list[dict]:
    """Fixed-window mean features, one dict per window: JSONL-ready rows for training."""
    rows, i = [], 0
    while i < len(frames):
        t0 = frames[i]["t"]
        w = [f for f in frames[i:] if f["t"] < t0 + win]
        i += len(w)
        row = {"t0": t0, "t1": w[-1]["t"], "mode": mode, "n": len(w)}
        for k in _BASE_KEYS + ("hand_face_dist",):
            vals = [f[k] for f in w if f.get(k) is not None]
            row[k] = mean(vals) if vals else None
        row["face_visible"] = sum(1 for f in w if f.get("face_visible")) / len(w)
        rows.append(row)
    return rows
