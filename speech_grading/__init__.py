"""orator: a maximal, open-source speech-grading system.

Tracks fillers (um/uh/like/you know), weak/hedging words, and the signature
"got-tripped-up" moments where a speaker hesitated and reached for a worse word,
plus pace, pauses, repetitions, vocabulary richness, readability, and optional
acoustic prosody. ASR is a pluggable backend; all analysis runs on a canonical
in-memory Transcript so it is testable offline with no model download.
"""

from __future__ import annotations

__version__ = "0.1.0"


def grade(audio_or_transcript: str, config=None):
    """End-to-end convenience entry point used by the CLI.

    ``audio_or_transcript`` is an audio file or a canonical Transcript JSON path.
    Returns a :class:`~speech_grading.schema.Report`.
    """
    from .config import Config
    from .pipeline import run_pipeline

    return run_pipeline(audio_or_transcript, config or Config())


__all__ = ["grade", "__version__"]
