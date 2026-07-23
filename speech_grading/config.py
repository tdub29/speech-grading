"""Typed configuration for orator.

Holds the ASR backend choice, license gates, the online/offline LLM toggle, scoring
weights, and all numeric thresholds. Loadable from YAML/JSON; sensible defaults make
the offline path work with zero configuration.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from pydantic import BaseModel, Field

# Default rubric weights (sum == 1.0). If a dimension is disabled at runtime
# (e.g. prosody when there is no audio), the scorer redistributes its weight.
DEFAULT_WEIGHTS: dict[str, float] = {
    "fillers": 0.18,
    "pace": 0.12,
    "pauses": 0.12,
    "word_choice": 0.18,
    "vocabulary": 0.12,
    "hedging": 0.10,
    "readability": 0.06,
    "prosody": 0.12,
}

DEFAULT_THRESHOLDS: dict[str, Any] = {
    # Pace (words per minute). Configurable band; default ~conversational-presentation.
    "wpm_ideal_low": 130.0,
    "wpm_ideal_high": 160.0,
    "wpm_fair_low": 110.0,
    "wpm_fair_high": 180.0,
    "wpm_window_sec": 10.0,
    "wpm_consistency_full": 15.0,   # windowed-WPM stdev at/below this = no penalty
    "wpm_consistency_dock": 35.0,   # stdev at/above this = full consistency penalty
    # Pauses (seconds). Gaps above pause_long are "long"; classified per-speaker too.
    "pause_micro": 0.2,
    "pause_long": 0.7,
    "filler_pause_gate": 0.3,       # extra gap over speaker median to upgrade a filler
    "long_pause_midclause_weight": 1.5,
    # Filler-rate bands (fillers per 100 words) -> see scorer.
    "filler_excellent": 2.0,
    "filler_good": 4.0,
    "filler_fair": 6.0,
    # Tripped-up fusion weights (event_score = sum of weighted signals).
    "tripped_up_weights": {
        "hedge": 0.20,
        "vague": 0.15,
        "pause": 0.25,
        "low_conf": 0.20,
        "filled_pause": 0.10,
        "repair": 0.10,
    },
    "tripped_up_min_score": 0.45,   # event_score threshold to surface a tripped_up moment
    "low_conf_threshold": 0.5,      # word.confidence below this contributes to "low_conf"
}


class Config(BaseModel):
    """Runtime configuration. Construct directly or via :func:`load_config`."""

    asr_backend: str = "faster-whisper"  # faster-whisper|crisper-whisper|vosk
    allow_noncommercial: bool = False    # gate for CrisperWhisper (CC-BY-NC weights)
    use_llm: bool = False                # word-choice via Claude API; else offline lexicon
    llm_model: str = "claude-opus-4-8"
    llm_effort: str = "high"             # low|medium|high
    max_llm_words: int = 1200            # cap transcript size sent to the API/agent
    # Agent-handoff word choice: path to a WordChoiceFindingList JSON an agent
    # (Claude in the loop) filled in. Takes precedence over the API path; no key.
    wordchoice_json: Optional[str] = None
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: dict[str, Any] = Field(default_factory=lambda: json.loads(json.dumps(DEFAULT_THRESHOLDS)))
    enable_acoustic: bool = False        # prosody track (needs audio + parselmouth/librosa)
    enable_video: bool = False           # visual tier (needs video + mediapipe/l2cs)
    asr_model_size: str = "large-v3"
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"

    def threshold(self, key: str, default: Any = None) -> Any:
        return self.thresholds.get(key, default)


def load_config(path: Optional[str] = None) -> Config:
    """Load a Config from a YAML/JSON file, or return defaults if ``path`` is None.

    YAML is supported only if PyYAML is installed; JSON always works.
    """
    if not path:
        return Config()
    with open(path, "r", encoding="utf-8-sig") as fh:  # tolerate a BOM
        text = fh.read()
    data: dict[str, Any]
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError("PyYAML required to load a YAML config; pip install pyyaml") from exc
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    # Merge nested defaults so a partial config does not blow away weights/thresholds.
    merged = Config().model_dump()
    for k, v in (data or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return Config.model_validate(merged)
