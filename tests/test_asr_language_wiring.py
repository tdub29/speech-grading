from speech_grading import pipeline
from speech_grading.cli import _build_parser, _config_from_args
from speech_grading.config import Config


def test_make_backend_passes_language_and_model(monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, **kw):
            seen.update(kw)

    import speech_grading.asr.faster_whisper_backend as fw
    monkeypatch.setattr(fw, "FasterWhisperBackend", Fake)
    pipeline._make_backend(Config(asr_model_size="small.en", asr_language=None))
    assert seen["model_size"] == "small.en" and seen["language"] is None
    pipeline._make_backend(Config())
    assert seen["language"] == "en"


def test_cli_language_and_model_overrides():
    cfg = _config_from_args(_build_parser().parse_args(["x.wav", "--asr-language", "auto", "--asr-model", "small"]))
    assert cfg.asr_language is None and cfg.asr_model_size == "small"
    cfg = _config_from_args(_build_parser().parse_args(["x.wav", "--asr-language", "es"]))
    assert cfg.asr_language == "es" and cfg.asr_model_size == "medium"
    assert _config_from_args(_build_parser().parse_args(["x.wav"])).asr_language == "en"
