"""Acquire local-only corpus audio, grade with fixed orator, export numeric diagnostics.

Run from the project root with its venv. Source manifests contain URLs and labels,
never audio or full transcripts. All private intermediates live in the corpus root.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path.home() / ".orator" / "corpus" / "exemplars"
_THREAD = threading.local()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def item_id(item):
    value = item["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"Unsafe corpus id: {value!r}")
    return value


def acquire(item):
    from speech_grading.pipeline import find_ffmpeg
    key = item_id(item)
    destination = ROOT / "audio" / f"{key}.wav"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        return {"id": key, "status": "cached", "audio": str(destination)}
    start = float(item.get("start_sec", 0))
    duration = min(900.0, float(item.get("end_sec", start + 900)) - start)
    if not math.isfinite(start) or not math.isfinite(duration) or start < 0 or duration <= 0:
        raise ValueError(f"Invalid clip bounds for {key}")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg unavailable")
    source = None
    if item.get("existing_id"):
        source = ROOT.parent / f"{item['existing_id']}.mp3"
        if not source.is_file():
            source = None
    if source is None:
        downloader = os.environ.get("ORATOR_YTDLP") or shutil.which("yt-dlp")
        if not downloader:
            raise RuntimeError("yt-dlp unavailable; no account or key fallback")
        folder = ROOT / "downloads" / key
        folder.mkdir(parents=True, exist_ok=True)
        command = [downloader, "--no-playlist", "--no-progress", "--no-warnings",
                   "--no-cache-dir", "--retries", "1", "--fragment-retries", "1",
                   "--socket-timeout", "20", "--ffmpeg-location", str(Path(ffmpeg).parent),
                   "-f", "bestaudio/best", "-o", str(folder / "source.%(ext)s"), item["source_url"]]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        (folder / "download.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(result.stderr.strip()[-1400:])
        sources = [p for p in folder.glob("source.*") if p.suffix not in (".part", ".ytdl")]
        if len(sources) != 1:
            raise RuntimeError(f"Expected one audio source for {key}, found {len(sources)}")
        source = sources[0]
        # Full download then ffmpeg trim: --download-sections hands googlevideo URLs to ffmpeg, which YouTube 403s.
    command = [ffmpeg, "-y", "-loglevel", "error", "-ss", str(start), "-i", str(source),
               "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode or not destination.is_file():
        destination.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip()[-1000:])
    return {"id": key, "status": "acquired", "audio": str(destination),
            "source_url": item["source_url"], "start_sec": item.get("start_sec", 0), "cap_sec": duration}


def grade(item):
    from speech_grading.asr.faster_whisper_backend import FasterWhisperBackend
    from speech_grading.config import Config
    from speech_grading.pipeline import run_on_transcript
    from speech_grading.schema import Transcript, derive_transcript_fields
    key = item_id(item)
    output = ROOT / "grades" / f"{key}.json"
    if output.is_file():
        return {"id": key, "status": "cached"}
    audio = Path(item.get("audio_path", ROOT / "audio" / f"{key}.wav")).resolve()
    if not audio.is_relative_to(ROOT.resolve()) or not audio.is_file():
        raise ValueError(f"Missing or nonlocal corpus audio: {key}")
    transcript_path = ROOT / "transcripts" / f"{key}.json"
    provenance = "new small ASR"
    if transcript_path.is_file():
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        provenance = "cached small ASR"
    else:
        existing = ROOT.parent / "tx" / f"{item.get('existing_id', '__none__')}.json"
        if existing.is_file() and float(item.get("start_sec", 0)) == 0 and not item.get("end_sec"):
            transcript = Transcript.model_validate_json(existing.read_text(encoding="utf-8"))
            provenance = "prior political corpus small ASR, exact source"
        else:
            if not hasattr(_THREAD, "backend"):
                _THREAD.backend = FasterWhisperBackend(model_size="small")
            transcript = _THREAD.backend.transcribe(str(audio))
        transcript.audio_path = str(audio)
        transcript = derive_transcript_fields(transcript)
        write_json(transcript_path, transcript.model_dump())
    transcript.audio_path = str(audio)
    transcript = derive_transcript_fields(transcript)
    if not transcript.words:
        raise ValueError(f"No recognized speech: {key}")
    cfg = Config(asr_model_size="small", enable_acoustic=True, use_llm=False,
                 mode=item.get("mode", "stage"))
    report = run_on_transcript(transcript, cfg)
    if not any(d.dimension == "prosody" for d in report.dimensions):
        raise RuntimeError(f"Requested acoustic measurements missing: {key}")
    value = report.model_dump()
    value["metadata"]["corpus_asr_provenance"] = provenance
    write_json(output, value)
    return {"id": key, "status": "graded", "words": transcript.total_words}


def numeric_metrics(report):
    values = {"overall_score": report["overall_score"]}
    for key, value in report["metrics"].items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values[key] = value
    for dimension in report["dimensions"]:
        values[f"{dimension['dimension']}_points"] = dimension["points"]
    return add_rate_metrics(values)


def auc(positive, negative):
    if not positive or not negative:
        return None
    return sum((a > b) + .5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))


def cohen_d(positive, negative):
    if min(len(positive), len(negative)) < 2:
        return None
    variance = ((len(positive) - 1) * statistics.variance(positive) +
                (len(negative) - 1) * statistics.variance(negative)) / (len(positive) + len(negative) - 2)
    return (statistics.mean(positive) - statistics.mean(negative)) / math.sqrt(variance) if variance else None


def paired_stats(differences):
    nonzero = [d for d in differences if d != 0]
    wins = sum(d > 0 for d in nonzero)
    n = len(nonzero)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(wins, n - wins) + 1)) / 2**n) if n else 1.0
    return {"n_pairs": len(differences), "wins": wins, "losses": n - wins,
            "ties": len(differences) - n, "direction_agreement": wins / n if n else None,
            "sign_test_p": p, "wilcoxon_p": wilcoxon_exact_p(differences), "median_difference": statistics.median(differences) if differences else None}


def effects_markdown(effects: dict) -> str:
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"
    metrics = [
        (name, data) for name, data in effects.items() if data["auc_high"] is not None
    ]
    metrics.sort(key=lambda x: (-abs(x[1]["auc_high"] - 0.5), x[0]))

    lines = [
        "| metric | n acclaimed | n panned | median acclaimed | median panned | AUC | d |",
        "|---|---|---|---|---|---|---|"
    ]
    for name, data in metrics:
        lines.append(f"| {name} | {data['n_acclaimed']} | {data['n_panned']} | {fmt(data['median_acclaimed'])} | {fmt(data['median_panned'])} | {fmt(data['auc_high'])} | {fmt(data['cohen_d'])} |")

    return "\n".join(lines) + "\n"


def paired_markdown(paired: dict) -> str:
    rows = sorted(((name, d) for name, d in paired.items()
                   if d["n_pairs"] > 0 and d["direction_agreement"] is not None),
                  key=lambda x: (x[1]["sign_test_p"], x[0]))
    lines = ["| metric | pairs | good higher | good lower | ties | agreement | sign p |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {n} | {d['n_pairs']} | {d['wins']} | {d['losses']} | {d['ties']} | "
              f"{d['direction_agreement']:.2f} | {d['sign_test_p']:.3f} |" for n, d in rows]
    return "\n".join(lines) + "\n"


def add_rate_metrics(metrics: dict) -> dict:
    result = dict(metrics)
    minutes = metrics.get("speaking_sec", 0) / 60
    kwords = metrics.get("total_words", 0) / 1000

    for name in ["long_pauses", "midclause_pauses", "repetitions"]:
        if name in metrics and minutes > 0:
            result[f"{name}_per_min"] = round(metrics[name] / minutes, 3)

    for name in ["anaphora_count", "tricolon_count", "question_count"]:
        if name in metrics and kwords > 0:
            result[f"{name}_per_1000w"] = round(metrics[name] / kwords, 3)

    return result


def wilcoxon_exact_p(differences: list[float]) -> float:
    """Exact two-sided Wilcoxon signed-rank p; zeros dropped, tied |d| get average ranks."""
    d = [x for x in differences if x != 0]
    n = len(d)
    if n == 0:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    sums = [sum(ranks[i] for i in range(n) if mask >> i & 1) for mask in range(2 ** n)]
    hi = sum(w >= w_plus - 1e-9 for w in sums)
    lo = sum(w <= w_plus + 1e-9 for w in sums)
    return round(min(1.0, 2 * min(lo, hi) / 2 ** n), 6)


def auc_within_mode(rows: list[dict], metric: str, mode: str) -> float | None:
    pos = []
    neg = []

    for row in rows:
        if row["mode"] == mode and metric in row["metrics"]:
            if row["label"] == "acclaimed":
                pos.append(row["metrics"][metric])
            elif row["label"] == "panned":
                neg.append(row["metrics"][metric])

    if not pos or not neg:
        return None

    total_score = 0
    for a in pos:
        for b in neg:
            if a > b:
                total_score += 1
            elif a == b:
                total_score += 0.5

    return round(total_score / (len(pos) * len(neg)), 3)


def summarize(items):
    rows = []
    for item in items:
        path = ROOT / "grades" / f"{item_id(item)}.json"
        if path.is_file():
            report = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"id": item["id"], "speaker": item["speaker"], "label": item["label"],
                         "genre": item["genre"], "pair_id": item.get("pair_id"),
                         "pair_side": item.get("pair_side"), "mode": item.get("mode", "stage"),
                         "metrics": numeric_metrics(report)})
    effects = {}
    metrics = sorted({key for row in rows for key in row["metrics"]})
    for metric in metrics:
        positive = [r["metrics"][metric] for r in rows if r["label"] == "acclaimed" and metric in r["metrics"]]
        negative = [r["metrics"][metric] for r in rows if r["label"] == "panned" and metric in r["metrics"]]
        effects[metric] = {"n_acclaimed": len(positive), "n_panned": len(negative),
                           "median_acclaimed": statistics.median(positive) if positive else None,
                           "median_panned": statistics.median(negative) if negative else None,
                           "auc_high": auc(positive, negative), "cohen_d": cohen_d(positive, negative),
                           "auc_stage_only": auc_within_mode(rows, metric, "stage")}
    pairs = {}
    for row in rows:
        if row["pair_id"]:
            pairs.setdefault(row["pair_id"], {})[row["pair_side"]] = row
    paired = {}
    for metric in metrics:
        differences = [pair["good"]["metrics"][metric] - pair["poor"]["metrics"][metric]
                       for pair in pairs.values() if "good" in pair and "poor" in pair
                       and metric in pair["good"]["metrics"] and metric in pair["poor"]["metrics"]]
        paired[metric] = paired_stats(differences)
    return {"rows": rows, "effects": effects, "paired": paired,
            "missing": [i["id"] for i in items if i["id"] not in {r["id"] for r in rows}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("action", choices=["acquire", "grade", "summarize"])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    items = json.loads(args.manifest.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items["speeches"]
    if args.ids:
        items = [item for item in items if item["id"] in args.ids]
    ROOT.mkdir(parents=True, exist_ok=True)
    if args.action == "summarize":
        result = summarize(items)
        out = args.output or ROOT / "summary.json"
        write_json(out, result)
        Path(out).with_suffix(".md").write_text(
            effects_markdown(result["effects"]) + "\n" + paired_markdown(result["paired"]), encoding="utf-8")
        print(json.dumps({"graded": len(result["rows"]), "missing": result["missing"]}), flush=True)
        return
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    def run(item):
        try:
            result = (acquire if args.action == "acquire" else grade)(item)
        except Exception as exc:
            result = {"id": item["id"], "status": "failed", "error": str(exc)}
        write_json(ROOT / "status" / f"{args.action}-{item_id(item)}.json", result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, items))
    if any(r["status"] == "failed" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
