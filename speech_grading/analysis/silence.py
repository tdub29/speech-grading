"""Acoustic silences that the ASR word timestamps hide.

faster-whisper stretches or compresses word times across a silence: a 1.5 s stall inserted
mid-clause read as a 0.00 s word gap on 3 of 5 test clips (one word held 2.56 s). This reads the
silence from the audio and pins it to the word boundary it sits on, so ``Transcript.gap_before``
and every pause and pace reader see it.
"""

from __future__ import annotations

from ..schema import Transcript

# Quiet = this many dB below the loud-speech level (95th-percentile frame RMS). A share of the
# max RMS read 34 to 86% of frames as silence on peaky recordings (applause, shouted lines).
_BELOW_SPEECH_DB = 35.0
_HOP = 512


def find_silences(audio_path: str, min_sec: float) -> list[tuple[float, float]]:
    """(start, end) of every run of quiet frames lasting at least ``min_sec``."""
    import librosa  # type: ignore
    import numpy as np  # type: ignore

    y, sr = librosa.load(audio_path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y, hop_length=_HOP)[0]
    if rms.size == 0 or float(rms.max()) <= 0:
        return []
    db = 20 * np.log10(np.maximum(rms, 1e-10))
    quiet = db < float(np.percentile(db, 95)) - _BELOW_SPEECH_DB
    times = librosa.frames_to_time(np.arange(rms.size), sr=sr, hop_length=_HOP)
    spans, run = [], None
    for k, q in enumerate(quiet):
        if q and run is None:
            run = k
        elif not q and run is not None:
            spans.append((float(times[run]), float(times[k])))
            run = None
    if run is not None:
        spans.append((float(times[run]), float(times[-1])))
    return [(a, b) for a, b in spans if b - a >= min_sec]


def _boundary_for(t: Transcript, c: float) -> int | None:
    """Boundary index (silence before word i) for an instant ``c``: the gap holding it, else the
    nearer edge of the word whose ASR span swallowed it."""
    words = t.words
    for k, w in enumerate(words):
        if c < w.start:
            return k  # in the gap before word k
        if c <= w.end:
            return k + 1 if c > (w.start + w.end) / 2 else k
    return None


def attach_silences(t: Transcript, spans: list[tuple[float, float]]) -> None:
    """Pin each silence hidden inside ASR word spans to the boundary at its centre. A silence the
    word gaps already show is skipped (no double count), as are leading and trailing silence and
    turn changes."""
    words = t.words
    if len(words) < 2:
        return
    for a, b in spans:
        if a < words[0].start or b > words[-1].end:
            continue
        shown = sum(max(0.0, min(b, words[j].start) - max(a, words[j - 1].end)) for j in range(1, len(words)))
        if shown >= 0.5 * (b - a):
            continue
        i = _boundary_for(t, (a + b) / 2)
        if i is None or not 0 < i < len(words) or i in t.turn_starts:
            continue
        if b - a > t.gap_before(i):
            t.acoustic_gaps[i] = (a, b)
