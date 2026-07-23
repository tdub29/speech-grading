"""Tests for the optional acoustic prosody track.

These run WITHOUT parselmouth/librosa/audio installed and assert that
:func:`compute_prosody` degrades gracefully to ``(None, [])`` on every disabled or
missing-audio path. No audio file is required.
"""

from __future__ import annotations

from speech_grading.analysis.prosody import compute_prosody
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
