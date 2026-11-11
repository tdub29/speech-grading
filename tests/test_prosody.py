"""Tests for the optional acoustic prosody track.

These run WITHOUT parselmouth/librosa/audio installed and assert that
:func:`compute_prosody` degrades gracefully to ``(None, [])`` on every disabled or
missing-audio path. No audio file is required.
"""

from __future__ import annotations

from speech_grading.analysis.prosody import _f0_semitone_stdev, compute_prosody
from speech_grading.config import Config


def test_disabled_by_default_returns_none(sample_transcript):
    """With default config (enable_acoustic=False) prosody is inert."""
    ds, finds = compute_prosody(sample_transcript, Config())
    assert ds is None
    assert finds == []


def test_enabled_but_no_audio_path_returns_none(sample_transcript):
    """Enabling acoustics with no audio_path still yields (None, [])."""
    sample_transcript.audio_path = None
    ds, finds = compute_prosody(sample_transcript, Config(enable_acoustic=True))
    assert ds is None
    assert finds == []


def test_enabled_but_missing_audio_file_returns_none(sample_transcript):
    """A non-existent audio file is treated like no audio at all."""
    sample_transcript.audio_path = "this/path/does/not/exist__orator.wav"
    ds, finds = compute_prosody(sample_transcript, Config(enable_acoustic=True))
    assert ds is None
    assert finds == []


def test_f0_keeps_speech_range_and_drops_octave_jumps():
    """A 150 Hz track with unvoiced, out-of-range and octave-jump frames stays ~150 Hz."""
    import numpy as np

    track = np.array([0, 148, 150, 152, 150, 30, 1200, 330, 149, 151], dtype=float)
    stdev, median = _f0_semitone_stdev(track, np)
    assert abs(median - 150) < 2
    assert stdev < 0.2  # 330 Hz octave jump excluded from variability


def test_f0_all_out_of_range_yields_nothing():
    """A 1200 Hz tone (above speech range) has no usable frames."""
    import numpy as np

    assert _f0_semitone_stdev(np.full(50, 1200.0), np) == (0.0, 0.0)
