"""Serving and evaluation ASR: Whisper medium with English decoding (model change orator-pace-pause-2026-11-20)."""
import sys
import types


def test_backend_pins_english_and_defaults_to_medium(monkeypatch):
    built, calls = [], []

    class StubModel:
        def __init__(self, size, **kw):
            built.append(size)

        def transcribe(self, path, **kw):
            calls.append(kw)
            return [], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=StubModel))
    from speech_grading.asr.faster_whisper_backend import FasterWhisperBackend
    from speech_grading.config import Config

    FasterWhisperBackend().transcribe("a.wav")
    assert built == ["medium"] and calls[-1]["language"] == "en"
    FasterWhisperBackend(language=None).transcribe("b.wav")
    assert calls[-1]["language"] is None  # explicit opt-out restores language detection
    assert Config().asr_model_size == "medium"
