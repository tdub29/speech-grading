"""Optional Apache-2.0 streaming/CPU ASR backend (Vosk).

Lightweight, fully offline, no GPU. Vosk emits per-word ``conf`` (0-1) and timing
when ``SetWords(True)`` is enabled. Requires a downloaded Vosk model directory; the
path is read from the ``VOSK_MODEL_PATH`` environment variable.
"""

from __future__ import annotations

import json
import os
import wave

from ..lexicons import FILLED_PAUSES
from ..schema import Transcript, Word, normalize_token
from .base import ASRBackend, normalize_confidence


class VoskBackend(ASRBackend):
    engine_id = "vosk"

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or os.environ.get("VOSK_MODEL_PATH")

    def transcribe(self, audio_path: str) -> Transcript:
        from vosk import KaldiRecognizer, Model  # lazy optional dep

        if not self.model_path:
            raise RuntimeError(
                "Vosk needs a model directory; set VOSK_MODEL_PATH or pass model_path."
            )
        wf = wave.open(audio_path, "rb")
        rec = KaldiRecognizer(Model(self.model_path), wf.getframerate())
        rec.SetWords(True)

        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                results.append(json.loads(rec.Result()))
        results.append(json.loads(rec.FinalResult()))

        raw = []
        confs = []
        for r in results:
            for tok in r.get("result", []):
                raw.append((tok["word"], float(tok["start"]), float(tok["end"])))
                confs.append(float(tok.get("conf", 1.0)))

        confidences = normalize_confidence(confs, self.engine_id)
        words = []
        for (text, start, end), conf in zip(raw, confidences):
            norm = normalize_token(text)
            words.append(
                Word(text=text, start=start, end=end, confidence=conf,
                     is_filled_pause=norm in FILLED_PAUSES, normalized=norm)
            )
        return Transcript(words=words, audio_path=audio_path, engine=self.engine_id,
                          sample_rate=wf.getframerate())
