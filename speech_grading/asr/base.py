"""ASR backend interface + cross-engine confidence normalization.

Recognition is decoupled from analysis: every backend returns a canonical
:class:`~speech_grading.schema.Transcript`, so the analysis layer never knows or
cares which engine produced it. Per-word confidence is engine-specific (Whisper
logprob vs Vosk lattice vs alignment frame probability), so it is normalized to a
comparable 0-1 scale before any thresholding downstream.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from ..schema import Transcript


class LicenseError(RuntimeError):
    """Raised when a non-commercially-licensed backend is requested without opt-in."""


class ASRBackend(ABC):
    """Abstract recognizer. Implementations must keep fillers (verbatim decode)."""

    #: stable id written into Transcript.engine
    engine_id: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str) -> Transcript:
        """Transcribe an audio file into a canonical, verbatim Transcript."""
        raise NotImplementedError


# Engines whose per-word score is already a linear probability in [0, 1].
_LINEAR_PROB_ENGINES = {"faster-whisper", "vosk"}


def normalize_confidence(values: list[float], engine: str) -> list[float]:
    """Map engine-specific per-word scores onto a comparable 0-1 confidence.

    The scale is decided by ``engine``, not inferred from sign (a 0.0 is ambiguous:
    worst probability vs. best log-prob):

    * Linear-probability engines (faster-whisper, vosk) -> clamp to [0, 1].
    * Any other engine -> treat a non-positive value as a log-probability and map
      via exp() (so a log-prob of 0.0 -> probability 1.0); clamp positives.

    ``None`` entries pass through unchanged (downstream fusion is None-safe).
    """
    linear = engine in _LINEAR_PROB_ENGINES
    out: list[float] = []
    for v in values:
        if v is None:
            out.append(None)  # type: ignore[arg-type]
        elif linear:
            out.append(_clamp(v))
        elif v <= 0.0:
            out.append(_clamp(math.exp(v)))  # log-prob domain
        else:
            out.append(_clamp(v))
    return out


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
