"""Visual event detectors over per-frame face/hand/pose features.

Pure functions: no mediapipe import, no IO. A frame is a dict with keys
t, smile, brow_raise, brow_furrow, jaw_open, gaze_off, pitch_deg,
hand_face_dist, wrist_y_rel, face_visible (any may be None when untracked).
Events are behavior counts, not verdicts: the cues are tendencies, not
reliable indicators of confidence or nervousness.
"""
from __future__ import annotations

from statistics import mean, median
from typing import Callable, Optional

from ..schema import Finding

_BASE_KEYS = ("smile", "brow_raise", "brow_furrow", "jaw_open", "gaze_off", "pitch_deg")


def baseline(frames: list[dict], first_sec: float = 30.0, min_face_sec: float = 10.0) -> dict:
    """Per-speaker median of each feature over the first `first_sec` seconds.

    Empty when the face spans under `min_face_sec` there: too little to trust.
    ponytail: a behavior held from the very start (chin up the whole talk) is absorbed
    into the baseline and never flagged; cues measure change from the speaker's norm.
    """
    if not frames:
        return {}
    t0 = frames[0]["t"]
    head = [f for f in frames if f["t"] - t0 <= first_sec and f.get("face_visible")]
    if not head or head[-1]["t"] - head[0]["t"] < min_face_sec:
        return {}
    out = {}
    for k in _BASE_KEYS:
        vals = [f[k] for f in head if f.get(k) is not None]
        if vals:
            out[k] = median(vals)
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
    return [_finding("face_touch", s, e, f"self-touch: hand near face for {e - s:.1f}s (a count, not a confidence signal)")
            for s, e in _runs(frames, touching, min_dur, max_gap)]


def detect_chin_up(frames, base, thresh_deg=8.0, min_dur=1.0, max_gap=0.3) -> list[Finding]:
    b = base.get("pitch_deg")
    if b is None:
        return []
    def up(f):
        p = f.get("pitch_deg")
        return p is not None and p >= b + thresh_deg
    return [_finding("chin_up", s, e, f"head pitched up >{thresh_deg:.0f} deg vs own baseline for {e - s:.1f}s")
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
            out.append(_finding("end_sentence_smile", end, end + window, "smile rise right after a sentence (neutral count)"))
    return out


# Per-mode thresholds and which cues are valid. Modes differ: a seated Zoom call
# crops hands and looks at a screen; a stage talk is wide, hands visible, gaze
# sweeps the room; a phone selfie is close and handheld. Tune from labeled data.
PROFILES: dict[str, dict] = {
    "default":   dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.5, need_hands=0.2, cues={"face_touch", "chin_up", "end_sentence_smile"}),
    "zoom":      dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.6, need_hands=0.2, cues={"face_touch", "chin_up", "end_sentence_smile"}),   # gaze unreliable: screen below lens
    "phone":     dict(touch_dist=0.20, chin_thresh=10.0, gaze_off=0.5, need_hands=0.2, cues={"face_touch", "chin_up", "end_sentence_smile"}),
    "stage":     dict(touch_dist=0.12, chin_thresh=8.0, gaze_off=0.8, need_hands=0.2, cues={"face_touch", "chin_up"}),                 # audience scan is normal
    "interview": dict(touch_dist=0.15, chin_thresh=8.0, gaze_off=0.7, need_hands=0.2, cues={"face_touch", "chin_up", "end_sentence_smile"}),   # looks at interviewer
}


MIN_RATE_SEC = 60.0  # per-minute rates from shorter clips are mostly noise


def summarize(frames: list[dict], sentence_ends: list[float], mode: str = "default",
              speaking_sec: Optional[float] = None, camera_level: bool = False) -> dict:
    """Run every valid cue for `mode`; return findings, per-minute rates, quality, skipped cues.

    `speaking_sec` (set with a speaker filter) is the rate denominator instead of video length.
    `camera_level`: chin up only runs when the camera is known to sit at eye level, since
    camera height alone changes how head angle reads (nonverbal-confidence-cues skill).
    Gaze is reported as an on-camera share, never as a per-sentence fault.
    """
    p = PROFILES.get(mode, PROFILES["default"])
    if not frames:
        return {"mode": mode, "quality": data_quality(frames), "findings": [], "rates_per_min": {},
                "skipped": {c: "no video frames decoded" for c in p["cues"]}}
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
        elif cue == "chin_up" and not camera_level:
            skipped[cue] = "camera height unknown (pass --camera-level)"
        elif cue in ("chin_up", "end_sentence_smile") and not base:
            skipped[cue] = "under 10s of face in the first 30s: no baseline"
        elif cue == "chin_up":
            found += detect_chin_up(frames, base, thresh_deg=p["chin_thresh"])
        elif cue == "end_sentence_smile":
            found += smile_after_sentence(frames, sentence_ends, base)
    counts: dict[str, int] = {}
    for f in found:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    secs = speaking_sec if speaking_sec else frames[-1]["t"] - frames[0]["t"]
    gz = [f["gaze_off"] for f in frames if f.get("face_visible") and f.get("gaze_off") is not None]
    out = {"mode": mode, "quality": q, "findings": found, "skipped": skipped,
           "counts": counts, "rates_per_min": {},
           "gaze_on_camera_pct": round(100 * sum(g < p["gaze_off"] for g in gz) / len(gz), 1) if gz else None}
    if secs < MIN_RATE_SEC:
        out["rates_note"] = f"under {MIN_RATE_SEC:.0f}s: counts only, no per-minute rates"
    else:
        out["rates_per_min"] = {k: round(n / (secs / 60), 2) for k, n in counts.items()}
    return out


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
