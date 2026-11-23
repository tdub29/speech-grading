"""Controlled A/B check: degrade graded exemplar clips one factor at a time and regrade.

Usage (project root, venv): python tools/ab_degrade.py ID [ID ...] [--start 60 --length 120] [--root DIR]
Reads ROOT/{audio,transcripts}/<ID>.* (default ~/.orator/corpus/exemplars-medium-en, the serving ASR);
writes clips, grades and ab_degrade.json/.md under ~/.orator/corpus/exemplars/ab-medium-en/. Nothing goes
in the repo. Exits 1 if any clip failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_grading.eval.ab_pairs import (  # noqa: E402
    CORPUS_ROOT, degradation_verdict, make_pairs, pick_midclause_boundary)
from speech_grading.eval.provenance import scoring_sha256  # noqa: E402

DEFAULT_ROOT = CORPUS_ROOT.parent / "exemplars-medium-en"
AB = CORPUS_ROOT / "ab-medium-en"  # make_pairs only writes beneath CORPUS_ROOT
MIN_REL = 0.05  # a target must move >= 5% of baseline (or 1 count from 0) to count, not ASR jitter
# transform -> (metric expected to move, direction)
TARGETS = {
    "pace_0.8x": ("wpm", "down"),
    "pace_1.25x": ("wpm", "up"),
    "pitch_flat": ("monotone_semitones", "down"),
    "dynamics_compressed": ("energy_dynamics", "down"),
    "silence_inserted": ("midclause_pauses", "up"),
    "filled_pause_inserted": ("filler_count", "up"),
}


def grade_provenance(wav: Path, backend) -> dict:
    """What a cached grade must match: ASR model and language, exact clip bytes, scoring code."""
    return {"model": backend.model_size, "language": backend.language,
            "audio_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(), "scoring_sha256": scoring_sha256()}


def _grade(wav: Path, backend, cfg_mode: str) -> dict:
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.schema import derive_transcript_fields

    t = backend.transcribe(str(wav))
    t.audio_path = str(wav)
    t = derive_transcript_fields(t)
    report = run_on_transcript(t, Config(enable_acoustic=True, use_llm=False, mode=cfg_mode))
    m = {k: v for k, v in report.metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    m["overall_score"] = report.overall_score
    for d in report.dimensions:
        m[f"{d.dimension}_points"] = d.points
    return m


def check_manifest_window(manifest: dict, start: float, end: float) -> None:
    """A cached clip set cut at another window must not be graded as this one."""
    if (manifest.get("source_start_sec"), manifest.get("source_end_sec")) != (start, end):
        raise ValueError(f"cached clips cut at {manifest.get('source_start_sec')}-{manifest.get('source_end_sec')}s, "
                         f"asked {start}-{end}s: delete the clip dir to re-cut")


def run_clip(key: str, start: float, length: float, backend, root: Path) -> list[dict]:
    from speech_grading.schema import Transcript

    audio = root / "audio" / f"{key}.wav"
    tpath = root / "transcripts" / f"{key}.json"
    prov = json.loads((root / "transcripts" / f"{key}.asr.json").read_text(encoding="utf-8"))
    if (prov.get("model"), prov.get("language")) != (backend.model_size, backend.language):
        raise ValueError(f"{key}: transcript ASR {prov.get('model')}/{prov.get('language')} is not the serving ASR")
    t = Transcript.model_validate_json(tpath.read_text(encoding="utf-8"))
    w = t.words
    end = start + length
    i = pick_midclause_boundary([x.text for x in w], [x.start for x in w], [x.end for x in w],
                                [x.is_filled_pause for x in w], min_time=start + 10)
    if i is None or w[i + 1].start >= end:
        raise ValueError(f"{key}: no tight mid-clause boundary inside the clip")
    filler = next((x for x in w if x.is_filled_pause and x.end - x.start >= 0.15), None)
    out = AB / key
    if not (out / "manifest.json").is_file():
        kw = dict(start=start, end=end, after_word_end=w[i].end, before_word_start=w[i + 1].start,
                  speaker=key, mid_clause=True)
        if filler:
            kw.update(filler_source=audio, filler_start=filler.start, filler_end=filler.end, filler_speaker=key)
        make_pairs(audio, out, **kw)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    check_manifest_window(manifest, start, end)
    grades = {}
    for o in manifest["outputs"]:
        cache, wav = out / f"{o['transform']}.grade.json", Path(o["path"])
        p = grade_provenance(wav, backend)
        cached = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
        if cached.get("provenance") != p:  # older ASR, clip or scoring code: regrade
            cached = {"provenance": p, "metrics": _grade(wav, backend, "stage")}
            cache.write_text(json.dumps(cached), encoding="utf-8")
        grades[o["transform"]] = cached["metrics"]
    rows = [{"clip": key, "transform": s["transform"], "skipped": s["reason"]} for s in manifest["skipped"]]
    for name, (metric, expect) in TARGETS.items():
        if name in grades and metric in grades["baseline"] and metric in grades[name]:
            v = degradation_verdict(grades["baseline"], grades[name], metric, expect, min_rel=MIN_REL)
            v.update(clip=key, transform=name, window=[start, end],
                     overall_delta=round(grades[name]["overall_score"] - grades["baseline"]["overall_score"], 1))
            rows.append(v)
    return rows


def merge_rows(old: list[dict], new: list[dict], clips: list[str]) -> list[dict]:
    """A partial rerun replaces only its own clips' rows."""
    return [r for r in old if r["clip"] not in clips] + new


def aggregate(rows: list[dict]) -> list[dict]:
    """Per transform: how many clips moved as expected, and the median relative change of the target."""
    out = []
    for name in TARGETS:
        rs = [r for r in rows if r.get("transform") == name and "moved_as_expected" in r]
        if rs:
            rel = [(r["edited"] - r["baseline"]) / abs(r["baseline"]) for r in rs if r["baseline"]]
            out.append({"transform": name, "moved": sum(r["moved_as_expected"] for r in rs), "n": len(rs),
                        "median_rel_change": round(median(rel), 3) if rel else None})
    return out


def markdown(rows: list[dict]) -> str:
    lines = ["| clip | transform | target | baseline | edited | moved as expected | overall delta | other metrics moved >10% |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['clip']} | | | | | ERROR: {r['error']} | | |")
        elif "skipped" in r:
            lines.append(f"| {r['clip']} | {r['transform']} | n/a | | | skipped: {r['skipped']} | | |")
        else:
            lines.append(f"| {r['clip']} | {r['transform']} | {r['target']} | {r['baseline']:.2f} | {r['edited']:.2f} | "
                         f"{'yes' if r['moved_as_expected'] else 'NO'} | {r['overall_delta']:+.1f} | {len(r['collateral'])} |")
    lines += ["", "| transform | clips moved as expected | median relative change |", "|---|---|---|"]
    for a in aggregate(rows):
        lines.append(f"| {a['transform']} | {a['moved']}/{a['n']} | {a['median_rel_change']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    from speech_grading.asr.faster_whisper_backend import FasterWhisperBackend
    from speech_grading.config import Config

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--start", type=float, default=60.0)
    ap.add_argument("--length", type=float, default=120.0)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    a = ap.parse_args()
    cfg = Config()
    backend = FasterWhisperBackend(model_size=cfg.asr_model_size, language=cfg.asr_language)
    rows = []
    for key in a.ids:
        try:
            rows += run_clip(key, a.start, a.length, backend, a.root)
        except Exception as exc:  # one bad clip must not sink the batch, but it is recorded and fails the exit code
            rows.append({"clip": key, "error": str(exc)})
    AB.mkdir(parents=True, exist_ok=True)
    path = AB / "ab_degrade.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    rows = merge_rows(old, rows, a.ids)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (AB / "ab_degrade.md").write_text(markdown(rows), encoding="utf-8")
    print(markdown(rows))
    if any("error" in r for r in rows if r["clip"] in a.ids):
        sys.exit(1)


if __name__ == "__main__":
    main()
