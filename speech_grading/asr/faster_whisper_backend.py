"""Default MIT-licensed ASR backend (faster-whisper), tuned for verbatim output.

Standard Whisper deletes fillers; we counteract that with verbatim decode settings:
``word_timestamps=True`` (gives per-word start/end/probability),
``condition_on_previous_text=False`` (stops cross-window "cleanup"), and a
filler-laden ``initial_prompt`` to prime the model to keep um/uh. faster-whisper is
installed only when this backend is actually used (lazy import).
"""

from __future__ import annotations

from ..lexicons import FILLED_PAUSES
from ..schema import Transcript, Word, normalize_token
from .base import ASRBackend, normalize_confidence

_VERBATIM_PROMPT = "Umm, uh, like, you know, I mean, so, basically, er, hmm..."


class FasterWhisperBackend(ASRBackend):
    engine_id = "faster-whisper"

    def __init__(self, model_size: str = "large-v3", device: str = "cpu",
                 compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: str) -> Transcript:
        from faster_whisper import WhisperModel  # lazy: heavy optional dep

        model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        segments, _info = model.transcribe(
            audio_path,
            word_timestamps=True,
            condition_on_previous_text=False,
            initial_prompt=_VERBATIM_PROMPT,
        )

        raw_words = []
        probs = []
        for seg in segments:
            for w in seg.words or []:
                raw_words.append((w.word, float(w.start), float(w.end)))
                probs.append(float(w.probability))

        confidences = normalize_confidence(probs, self.engine_id)
        words = []
        for (text, start, end), conf in zip(raw_words, confidences):
            norm = normalize_token(text)
            words.append(
                Word(
                    text=text.strip(),
                    start=start,
                    end=end,
                    confidence=conf,
                    is_filled_pause=norm in FILLED_PAUSES,
                    normalized=norm,
                )
            )
        return Transcript(words=words, audio_path=audio_path, engine=self.engine_id)
