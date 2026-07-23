"""Prosody analysis: the OPTIONAL acoustic track.

Unlike every other analysis module, prosody needs the raw audio (not just the
canonical :class:`Transcript`) and two heavyweight, optional native libraries
(``praat-parselmouth`` for pitch tracking, ``librosa`` for spectral/energy
features). The whole offline scoring pipeline must keep working when neither the
audio nor those libraries are present, so this module **degrades gracefully**:

* If acoustics are disabled, there is no audio path, or the file is missing, it
  returns ``(None, [])`` -- the scorer then redistributes prosody's weight.
* The heavy deps are imported *lazily inside* :func:`compute_prosody`; an
  ``ImportError`` is treated exactly like missing audio (``(None, [])``). They are
  never imported at module top level, so importing this module is always cheap and
  safe even on a machine without parselmouth/librosa.

When audio *is* available it measures:

* ``monotone`` -- the standard deviation of fundamental frequency (F0) in
  *semitones* over voiced frames. Higher = more pitch variation = more expressive;
  near-zero = monotone. This is the dimension's ``raw`` value.
* ``energy_dynamics`` -- the coefficient of variation of frame RMS energy
  (``std/mean``). Higher = more dynamic loudness contour.
* ``articulation_rate`` -- a syllable-count proxy over phonation time.
* acoustic filled-pause ``Finding`` objects (``kind='filler'``,
  ``source='acoustic'``) for long, sustained voiced segments with little spectral
  change -- an approximate "drawn-out um/uh" heuristic, clearly documented below as
  a coarse signal rather than ground truth.
"""

from __future__ import annotations

import math
import os
from typing import Optional

from speech_grading.config import Config
from speech_grading.schema import DimensionScore, Finding, Transcript

# --------------------------------------------------------------------------- #
# Banding thresholds for the prosody dimension.
#
# Expressive speech has clear pitch movement (F0 stdev of several semitones) and a
# dynamic energy contour. A flat, monotone delivery sits near zero on both. The
# combined band rewards having *both*; lacking both = 'poor' (monotone + flat).
# --------------------------------------------------------------------------- #
_MONOTONE_EXCELLENT = 4.0   # F0 stdev (semitones) at/above this = highly expressive
_MONOTONE_GOOD = 2.5
_MONOTONE_FAIR = 1.5        # below this is essentially monotone
_ENERGY_DYNAMIC = 0.35      # RMS coefficient-of-variation considered "dynamic"

# Acoustic filled-pause heuristic (approximate, see _acoustic_filled_pauses).
_FP_MIN_DURATION = 0.6      # a sustained voiced stretch must last at least this long
_FP_MAX_FLUX = 0.04         # mean spectral flux below this = "low spectral change"


def _band(monotone: float, energy_dynamics: float) -> str:
    """Combine pitch variation and energy dynamics into a rubric band.

    Pitch variation is the primary axis; a dynamic energy contour can lift an
    otherwise borderline-flat delivery, while a flat contour drags it down.
    """
    if monotone >= _MONOTONE_EXCELLENT and energy_dynamics >= _ENERGY_DYNAMIC:
        return "excellent"
    if monotone >= _MONOTONE_GOOD:
        return "good"
    if monotone >= _MONOTONE_FAIR or energy_dynamics >= _ENERGY_DYNAMIC:
        return "fair"
    return "poor"  # monotone + flat


def _points(monotone: float, energy_dynamics: float) -> float:
    """Map the two acoustic signals onto a 0-100 sub-score.

    Pitch variation is worth up to 70 points (scaled linearly to the "excellent"
    threshold) and energy dynamics up to 30, so an expressive, dynamic delivery
    approaches 100 and a monotone, flat one approaches 0.
    """
    pitch_pts = 70.0 * min(1.0, monotone / _MONOTONE_EXCELLENT) if _MONOTONE_EXCELLENT > 0 else 0.0
    energy_pts = 30.0 * min(1.0, energy_dynamics / _ENERGY_DYNAMIC) if _ENERGY_DYNAMIC > 0 else 0.0
    return max(0.0, min(100.0, pitch_pts + energy_pts))


def _f0_semitone_stdev(pitch_values, np) -> tuple[float, float]:
    """Std-dev of voiced F0 in semitones relative to the median voiced F0.

    ``pitch_values`` is the per-frame F0 array from parselmouth (0 == unvoiced).
    Returns ``(stdev_semitones, median_f0_hz)``; ``(0.0, 0.0)`` if there is not
    enough voiced material to be meaningful.
    """
    voiced = pitch_values[pitch_values > 0]
    if voiced.size < 2:
        return 0.0, 0.0
    median_f0 = float(np.median(voiced))
    if median_f0 <= 0:
        return 0.0, 0.0
    semitones = 12.0 * np.log2(voiced / median_f0)
    return float(np.std(semitones)), median_f0


def _acoustic_filled_pauses(t: Transcript, rms, flux, frame_times, np) -> list[Finding]:
    """Flag long, sustained, low-flux voiced segments as approximate filled pauses.

    This is a deliberately coarse heuristic: a drawn-out "ummm"/"uhhh" tends to be a
    long stretch of steady voicing with little spectral movement. We scan for
    contiguous runs of voiced frames (RMS above a noise floor) lasting at least
    ``_FP_MIN_DURATION`` whose mean spectral flux is below ``_FP_MAX_FLUX``, and emit
    one ``Finding`` per run, mapped back to the nearest transcript word. It is an
    approximate acoustic signal, NOT ground truth, and is intended to complement --
    not replace -- the lexical filled-pause detector.
    """
    findings: list[Finding] = []
    if rms.size == 0 or flux.size == 0 or frame_times.size == 0:
        return findings

    n = min(rms.size, flux.size, frame_times.size)
    rms = rms[:n]
    flux = flux[:n]
    frame_times = frame_times[:n]

    # Voiced = RMS above a low fraction of the peak (a simple noise gate).
    floor = 0.10 * float(np.max(rms)) if np.max(rms) > 0 else 0.0
    voiced = rms > floor

    i = 0
    while i < n:
        if not voiced[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and voiced[j + 1]:
            j += 1
        seg_start = float(frame_times[i])
        seg_end = float(frame_times[j])
        duration = seg_end - seg_start
        if duration >= _FP_MIN_DURATION:
            mean_flux = float(np.mean(flux[i : j + 1]))
            if mean_flux <= _FP_MAX_FLUX:
                wi = _nearest_word_index(t, (seg_start + seg_end) / 2.0)
                findings.append(
                    Finding(
                        kind="filler",
                        word_index=wi,
                        start=seg_start,
                        end=seg_end,
                        original=t.words[wi].text if 0 <= wi < len(t.words) else "",
                        rationale=(
                            f"Sustained {duration:.1f}s voiced segment with low spectral "
                            "change (approximate acoustic filled pause)."
                        ),
                        score=1.0,
                        source="acoustic",
                    )
                )
        i = j + 1
    return findings


def _nearest_word_index(t: Transcript, time_sec: float) -> int:
    """Index of the transcript word whose midpoint is closest to ``time_sec``."""
    if not t.words:
        return 0
    best_i = 0
    best_d = float("inf")
    for idx, w in enumerate(t.words):
        mid = (w.start + w.end) / 2.0
        d = abs(mid - time_sec)
        if d < best_d:
            best_d = d
            best_i = idx
    return best_i


def compute_prosody(t: Transcript, cfg: Config) -> tuple[Optional[DimensionScore], list[Finding]]:
    """Score prosody from raw audio, degrading to ``(None, [])`` when unavailable.

    Returns ``(None, [])`` -- meaning "this dimension does not apply" -- whenever
    acoustics are disabled, there is no audio path, the file is missing, or the
    optional native libraries cannot be imported. Otherwise returns a
    :class:`DimensionScore` (``dimension='prosody'``, ``weight=0``, ``raw`` = F0
    std-dev in semitones) plus the acoustic filled-pause findings (also embedded in
    the score's ``findings``).
    """
    # --- Graceful gates (cheap, no heavy imports) --------------------------- #
    if not cfg.enable_acoustic:
        return None, []
    if not t.audio_path or not os.path.exists(t.audio_path):
        return None, []

    # --- Lazy heavy imports; absence == "dimension does not apply" ---------- #
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore
        import parselmouth  # type: ignore
    except ImportError:
        return None, []

    # --- Pitch (F0) variation in semitones via parselmouth ------------------ #
    try:
        sound = parselmouth.Sound(t.audio_path)
        pitch = sound.to_pitch()
        pitch_values = pitch.selected_array["frequency"]
        monotone, median_f0 = _f0_semitone_stdev(pitch_values, np)
    except Exception:  # pragma: no cover - defensive: bad/short audio
        monotone, median_f0 = 0.0, 0.0

    # --- Energy dynamics + spectral flux via librosa ------------------------ #
    energy_dynamics = 0.0
    articulation_rate = 0.0
    acoustic_findings: list[Finding] = []
    try:
        y, sr = librosa.load(t.audio_path, sr=None, mono=True)
        rms = librosa.feature.rms(y=y)[0]
        mean_rms = float(np.mean(rms)) if rms.size else 0.0
        if mean_rms > 0:
            energy_dynamics = float(np.std(rms) / mean_rms)

        # Spectral flux: frame-to-frame magnitude-spectrum change (onset strength is
        # a robust, normalized proxy available in librosa).
        flux = librosa.onset.onset_strength(y=y, sr=sr)
        if flux.size and float(np.max(flux)) > 0:
            flux = flux / float(np.max(flux))  # normalize to 0-1 for the flux gate

        hop = 512  # librosa default hop length for rms/onset_strength
        frame_times = librosa.frames_to_time(
            np.arange(max(rms.size, flux.size)), sr=sr, hop_length=hop
        )

        # Articulation-rate proxy: estimated syllables (onset-strength peaks) over
        # phonation time. A simple, documented approximation -- not a phonetic count.
        peaks = librosa.util.peak_pick(
            flux, pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.1, wait=3
        )
        n_syllables = int(peaks.size) if hasattr(peaks, "size") else len(peaks)
        if t.speaking_sec > 0:
            articulation_rate = n_syllables / t.speaking_sec

        acoustic_findings = _acoustic_filled_pauses(t, rms, flux, frame_times, np)
    except Exception:  # pragma: no cover - defensive: decode/feature failure
        pass

    band = _band(monotone, energy_dynamics)
    points = _points(monotone, energy_dynamics)

    score = DimensionScore(
        dimension="prosody",
        raw=monotone,
        band=band,
        points=points,
        weight=0.0,
        findings=acoustic_findings,
        detail={
            "monotone_semitones": monotone,
            "median_f0_hz": median_f0,
            "energy_dynamics": energy_dynamics,
            "articulation_rate": articulation_rate,
            "n_acoustic_fillers": len(acoustic_findings),
        },
    )
    return score, acoustic_findings
