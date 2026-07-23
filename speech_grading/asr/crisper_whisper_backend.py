"""Opt-in high-accuracy ASR backend (CrisperWhisper).

CrisperWhisper natively emits explicit [UM]/[UH] filler tokens with disfluency-robust
word timestamps and beats Whisper large-v3 on WER. Its weights are CC BY-NC 4.0
(NON-COMMERCIAL), so this backend refuses to load unless ``config.allow_noncommercial``
is True and logs a clear license warning. Never ship it as the default in a paid product.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..lexicons import FILLED_PAUSES
from ..schema import Transcript, Word, normalize_token
from .base import ASRBackend, LicenseError

logger = logging.getLogger(__name__)

_MODEL_ID = "nyrahealth/CrisperWhisper"


class CrisperWhisperBackend(ASRBackend):
    engine_id = "crisper-whisper"

    def __init__(self, cfg: Config) -> None:
        if not cfg.allow_noncommercial:
            raise LicenseError(
                "CrisperWhisper weights are CC BY-NC 4.0 (non-commercial). "
                "Set allow_noncommercial=True (CLI: --allow-noncommercial) to use it, "
                "and do NOT ship it in a commercial product."
            )
        logger.warning(
            "Loading CrisperWhisper (CC BY-NC 4.0): non-commercial use only."
        )
        self.cfg = cfg

    def transcribe(self, audio_path: str) -> Transcript:
        # Lazy: requires torch + the nyrahealth transformers fork.
        from transformers import (  # type: ignore
            AutoModelForSpeechSeq2Seq,
            AutoProcessor,
            pipeline,
        )

        processor = AutoProcessor.from_pretrained(_MODEL_ID)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(_MODEL_ID)
        asr = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            return_timestamps="word",
        )
        result = asr(audio_path)

        words = []
        for chunk in result.get("chunks", []):
            text = (chunk.get("text") or "").strip()
            ts = chunk.get("timestamp") or (0.0, 0.0)
            start = float(ts[0] or 0.0)
            end = float(ts[1] or start)
            norm = normalize_token(text)
            words.append(
                Word(
                    text=text,
                    start=start,
                    end=end,
                    confidence=None,  # not exposed natively; tripped-up fusion is None-safe
                    is_filled_pause=norm in FILLED_PAUSES,
                    normalized=norm,
                )
            )
        return Transcript(words=words, audio_path=audio_path, engine=self.engine_id)
