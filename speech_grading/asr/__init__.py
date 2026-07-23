"""Pluggable ASR backends. Heavy engines (faster-whisper, torch) import lazily."""
from .base import ASRBackend, LicenseError, normalize_confidence

__all__ = ["ASRBackend", "LicenseError", "normalize_confidence"]
