"""Generate the canonical sample Transcript fixture used by the test suite.

Run:  python tests/_build_fixture.py
Writes tests/fixtures/sample_transcript.json with deterministic timings, deliberate
fillers / hedges / a repetition / a long mid-clause pause / a low-confidence
"tripped-up" word so every analysis module has something to detect.
"""

from __future__ import annotations

import json
import os

# (text, gap_before_sec, duration_sec, confidence)
# A ~30s monologue full of teachable issues.
TOKENS = [
    ("So,", 0.00, 0.25, 0.97),
    ("um,", 0.30, 0.45, 0.55),            # filled pause
    ("today", 0.20, 0.35, 0.98),
    ("I", 0.12, 0.12, 0.99),
    ("want", 0.05, 0.22, 0.98),
    ("to", 0.04, 0.12, 0.99),
    ("talk", 0.05, 0.28, 0.98),
    ("about,", 0.05, 0.30, 0.96),
    ("uh,", 0.35, 0.40, 0.50),            # filled pause + gap
    ("our", 0.18, 0.18, 0.97),
    ("quarterly", 0.06, 0.48, 0.95),
    ("results.", 0.05, 0.42, 0.97),
    ("I", 0.45, 0.14, 0.98),
    ("think", 0.04, 0.26, 0.97),          # hedge "I think"
    ("the", 0.05, 0.12, 0.98),
    ("numbers", 0.05, 0.40, 0.96),
    ("are,", 0.05, 0.22, 0.95),
    ("like,", 0.28, 0.30, 0.60),          # discourse filler "like" (not comparison)
    ("pretty", 0.20, 0.28, 0.93),
    ("good.", 0.05, 0.35, 0.94),          # weak adjective "good"
    ("We,", 0.40, 0.20, 0.90),
    ("we", 0.10, 0.16, 0.66),             # immediate repetition "we we"
    ("saw", 0.05, 0.24, 0.97),
    ("a", 0.04, 0.08, 0.98),
    ("really", 0.05, 0.26, 0.92),         # intensifier
    ("big", 0.05, 0.22, 0.95),
    ("increase", 0.05, 0.46, 0.96),
    ("in,", 0.05, 0.18, 0.93),
    ("um,", 0.34, 0.42, 0.52),            # filled pause
    ("revenue.", 0.22, 0.55, 0.96),
    ("The", 0.50, 0.16, 0.88),
    ("the", 0.10, 0.14, 0.58),            # immediate repetition "the the"
    ("team", 0.05, 0.30, 0.97),
    ("did", 0.05, 0.18, 0.98),
    ("a", 0.04, 0.08, 0.98),
    ("great", 0.05, 0.30, 0.95),
    ("job.", 0.05, 0.34, 0.96),
    ("Basically,", 0.45, 0.55, 0.90),     # discourse filler "basically"
    ("the", 0.10, 0.12, 0.95),
    ("thing", 0.05, 0.26, 0.80),          # vague noun "thing"
    ("is", 0.05, 0.16, 0.96),
    ("we", 0.05, 0.16, 0.95),
    ("need", 0.05, 0.24, 0.97),
    ("to,", 0.05, 0.16, 0.92),
    ("uh,", 0.40, 0.45, 0.48),            # filled pause
    ("utilize", 1.35, 0.62, 0.41),        # LONG mid-clause pause + low conf + weak word -> tripped_up
    ("our", 0.18, 0.16, 0.95),
    ("budget", 0.06, 0.40, 0.96),
    ("better.", 0.06, 0.45, 0.95),
    ("You", 0.55, 0.16, 0.93),
    ("know,", 0.05, 0.22, 0.85),          # phrase filler "you know"
    ("I", 0.25, 0.12, 0.96),
    ("guess", 0.04, 0.30, 0.78),          # hedge "I guess"
    ("it", 0.05, 0.12, 0.97),
    ("could", 0.05, 0.22, 0.90),          # hedge
    ("maybe", 0.08, 0.34, 0.72),          # hedge
    ("work.", 0.10, 0.42, 0.95),
]


def build() -> dict:
    words = []
    t = 0.0
    for text, gap, dur, conf in TOKENS:
        t += gap
        start = round(t, 3)
        end = round(t + dur, 3)
        words.append({"text": text, "start": start, "end": end, "confidence": conf})
        t = end
    return {
        "words": words,
        "audio_path": None,
        "sample_rate": None,
        "language": "en",
        "engine": "fixture",
    }


_MEETING_TEXT = (
    "We shipped the new onboarding flow last week and the early numbers look solid. "
    "Signups rose across every channel, and support tickets about setup dropped sharply. "
    "Next we want to test a shorter checklist with the enterprise accounts before the quarter closes. "
    "The design team already has two variants ready, so the experiment can start on Monday. "
)


def _turn(speaker: str, n: int, start: float, offset: int = 0) -> list[dict]:
    """n words, 0.3 s each with 0.1 s gaps (0.4 s step), text cycled from _MEETING_TEXT."""
    pool = _MEETING_TEXT.split()
    return [{"text": pool[(offset + k) % len(pool)], "start": round(start + 0.4 * k, 3),
             "end": round(start + 0.4 * k + 0.3, 3), "confidence": 0.95, "speaker": speaker}
            for k in range(n)]


def build_meeting() -> dict:
    """3-speaker meeting for tests/test_group.py (all numbers hand-checkable):

    Alice 20 words 0.0-7.9 | Bob "yeah" 8.2-8.5 (backchannel) | Alice 20 words 8.8-17.0
    (last word held to 17.0) | Bob 65 words 16.6-42.5 (starts 0.4 s before Alice stops:
    the planted overlap) | Cara 5 words 43.5-45.4 | Alice 25 words 46.0-55.9.
    """
    alice2 = _turn("Alice", 20, 8.8, 20)
    alice2[-1]["end"] = 17.0
    words = (_turn("Alice", 20, 0.0)
             + [{"text": "yeah", "start": 8.2, "end": 8.5, "confidence": 0.9, "speaker": "Bob"}]
             + alice2 + _turn("Bob", 65, 16.6, 7) + _turn("Cara", 5, 43.5, 30)
             + _turn("Alice", 25, 46.0, 40))
    return {"words": words, "audio_path": None, "language": "en", "engine": "fixture multitrack",
            "tracks": {"Alice": "alice.wav", "Bob": "bob.wav", "Cara": "cara.wav"}}


def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sample_transcript.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(build(), fh, indent=2)
    print(f"wrote {out_path} ({len(TOKENS)} tokens)")
    meeting = os.path.join(out_dir, "meeting_3speakers.json")
    with open(meeting, "w", encoding="utf-8") as fh:
        json.dump(build_meeting(), fh, indent=2)
    print(f"wrote {meeting}")


if __name__ == "__main__":
    main()
