"""Controlled A/B check: degrade graded exemplar clips one factor at a time and regrade.

Usage (project root, venv): python tools/ab_degrade.py ID [ID ...] [--start 60 --length 120]
Needs ~/.orator/corpus/exemplars/{audio,transcripts}/<ID>.*; writes clips, grades and
ab_degrade.json/.md under ~/.orator/corpus/exemplars/ab/. Nothing goes in the repo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_grading.eval.ab_pairs import (  # noqa: E402
    CORPUS_ROOT, degradation_verdict, make_pairs, pick_midclause_boundary)

AB = CORPUS_ROOT / "ab"
# transform -> (metric expected to move, direction)
TARGETS = {
    "pace_0.8x": ("wpm", "down"),
    "pace_1.25x": ("wpm", "up"),
    "pitch_flat": ("monotone_semitones", "down"),
    "dynamics_compressed": ("energy_dynamics", "down"),
    "silence_inserted": ("midclause_pauses", "up"),
    "filled_pause_inserted": ("filler_count", "up"),
}


def _grade(wav: Path, backend, cfg_mode: str) -> dict:
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.schema import derive_transcript_fields

    t = backend.transcribe(str(wav))
    t.audio_path = str(wav)
    t = derive_transcript_fields(t)
    report = run_on_transcript(t, Config(asr_model_size="small", enable_acoustic=True,
                                         use_llm=False, mode=cfg_mode))
    m = {k: v for k, v in report.metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    m["overall_score"] = report.overall_score
    for d in report.dimensions:
        m[f"{d.dimension}_points"] = d.points
    return m


def run_clip(key: str, start: float, length: float, backend) -> list[dict]:
    from speech_grading.schema import Transcript

    audio = CORPUS_ROOT / "audio" / f"{key}.wav"
    t = Transcript.model_validate_json((CORPUS_ROOT / "transcripts" / f"{key}.json").read_text(encoding="utf-8"))
    w = t.words
    i = pick_midclause_boundary([x.text for x in w], [x.start for x in w], [x.end for x in w],
                                [x.is_filled_pause for x in w], min_time=start + 10)
    if i is None or w[i].end >= start + length:
        raise ValueError(f"{key}: no tight mid-clause boundary inside the clip")
    filler = next((x for x in w if x.is_filled_pause and x.end - x.start >= 0.15), None)
    out = AB / key
    if not (out / "manifest.json").is_file():
        kw = dict(start=start, end=start + length, after_word_end=w[i].end, before_word_start=w[i + 1].start,
                  speaker=key, mid_clause=True)
        if filler:
            kw.update(filler_source=audio, filler_start=filler.start, filler_end=filler.end, filler_speaker=key)
        make_pairs(audio, out, **kw)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    grades = {}
    for o in manifest["outputs"]:
        cache = out / f"{o['transform']}.grade.json"
        if not cache.is_file():
            cache.write_text(json.dumps(_grade(Path(o["path"]), backend, "stage")), encoding="utf-8")
        grades[o["transform"]] = json.loads(cache.read_text(encoding="utf-8"))
    rows = [{"clip": key, "transform": s["transform"], "skipped": s["reason"]} for s in manifest["skipped"]]
    for name, (metric, expect) in TARGETS.items():
        if name in grades and metric in grades["baseline"] and metric in grades[name]:
            v = degradation_verdict(grades["baseline"], grades[name], metric, expect)
            v.update(clip=key, transform=name,
                     overall_delta=round(grades[name]["overall_score"] - grades["baseline"]["overall_score"], 1))
            rows.append(v)
    return rows


def markdown(rows: list[dict]) -> str:
    lines = ["| clip | transform | target | baseline | edited | moved as expected | overall delta | other metrics moved >10% |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "skipped" in r:
            lines.append(f"| {r['clip']} | {r['transform']} | n/a | | | skipped: {r['skipped']} | | |")
            continue
        lines.append(f"| {r['clip']} | {r['transform']} | {r['target']} | {r['baseline']:.2f} | {r['edited']:.2f} | "
                     f"{'yes' if r['moved_as_expected'] else 'NO'} | {r['overall_delta']:+.1f} | {len(r['collateral'])} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    from speech_grading.asr.faster_whisper_backend import FasterWhisperBackend

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--start", type=float, default=60.0)
    ap.add_argument("--length", type=float, default=120.0)
    a = ap.parse_args()
    backend = FasterWhisperBackend(model_size="small")
    rows = []
    for key in a.ids:
        try:
            rows += run_clip(key, a.start, a.length, backend)
        except Exception as exc:  # one bad clip must not sink the batch
            print(json.dumps({"clip": key, "error": str(exc)}), flush=True)
    AB.mkdir(parents=True, exist_ok=True)
    (AB / "ab_degrade.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (AB / "ab_degrade.md").write_text(markdown(rows), encoding="utf-8")
    print(markdown(rows))


if __name__ == "__main__":
    main()
