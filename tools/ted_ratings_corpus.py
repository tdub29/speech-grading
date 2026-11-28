"""TED audience-ratings validation corpus for orator: labels, sample, split, audio, grades, analysis.

Labels come from the 2017 ted_main.csv snapshot (a key-free GitHub mirror pinned by sha256). The
label is fixed here before any orator score exists (see docs/ted-ratings-corpus.md). Audio,
transcripts and grades live under ~/.orator/corpus/ted-ratings only; the committed manifest holds
ids, YouTube URLs, labels and covariates. Acquire, ASR and grading reuse tools/exemplar_corpus.py.

  python tools/ted_ratings_corpus.py label            # verify source sha256, build the labeled pool
  python tools/ted_ratings_corpus.py sample           # stratified, speaker-disjoint candidates
  python tools/ted_ratings_corpus.py resolve          # YouTube ids by search (needs yt_dlp module)
  python tools/ted_ratings_corpus.py split            # 400 items, dev / sealed held-out, write manifest
  .venv/Scripts/python tools/ted_ratings_corpus.py run --split development   # acquire, ASR, check, grade
  .venv/Scripts/python tools/ted_ratings_corpus.py analyze                    # development only
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO))
import exemplar_corpus as ec  # noqa: E402  (reuse acquire, ASR, grade, provenance, freeze asserts)

ROOT = Path.home() / ".orator" / "corpus" / "ted-ratings"
SOURCE = {
    "url": "https://raw.githubusercontent.com/Duttaay/TED_Talk_Analysis_R-Project/"
           "f0c7a888a85566142b88f81274c53271da4aa9e3/ted_main.csv",
    "sha256": "801c01b1f88181bce3dc1af7d4416df45d45f5729e6384eccb60368c00fabd6e",
    "origin": "Kaggle rounakbanik/ted-talks ted_main.csv (TED.com metadata to 2017-09-21), mirrored on GitHub",
    "checked": "2026-11-25",
}
MANIFEST = REPO / "docs" / "ted-ratings-manifest.json"
CHECKS = REPO / "docs" / "ted-ratings-content-checks.json"
CONFIRM = REPO / "docs" / "ted-ratings-confirm-manifest.json"  # fresh sample for model-change confirmation
CONFIRM_PER_STRATUM = 15
SEED = "ted-ratings-2026-11-25"
NEGATIVE = ("Longwinded", "Unconvincing", "Obnoxious", "Confusing")
EXCLUDED_TAGS = {"performance", "music", "live music", "dance", "magic", "poetry", "spoken word"}
TED_CHANNELS = {"TED", "TEDx Talks", "TED Archive"}
N_STRATA, PER_STRATUM, RESERVE = 10, 40, 30
EXCERPT_SEC = 120.0


def stable_hash(*parts):
    return hashlib.sha256("|".join([SEED, *map(str, parts)]).encode()).hexdigest()


def event_class(event):
    """Covariate: which TED stage the talk came from (an editorial-selection proxy)."""
    if re.fullmatch(r"TED(19|20)\d\d", event):
        return "ted_main"
    for prefix, name in (("TEDGlobal", "ted_global"), ("TEDx", "tedx"), ("TEDWomen", "ted_women"),
                         ("TEDMED", "tedmed")):
        if event.startswith(prefix):
            return name
    return "ted_other" if event.startswith("TED") else "external"


def label_row(row):
    """Label and covariates for one CSV row; None when the talk is ineligible (rule in the charter)."""
    ratings = {r["name"]: int(r["count"]) for r in ast.literal_eval(row["ratings"])}
    total = sum(ratings.values())
    tags = {t.lower() for t in ast.literal_eval(row["tags"])}
    duration = int(row["duration"])
    if (int(row["num_speaker"]) != 1 or not 360 <= duration <= 1800 or total < 200
            or tags & EXCLUDED_TAGS):
        return None
    year = datetime.fromtimestamp(int(row["film_date"]), timezone.utc).year
    return {"speaker": row["main_speaker"].strip(), "title": row["title"].strip(), "event": row["event"],
            "event_class": event_class(row["event"]), "year": year,
            "date": datetime.fromtimestamp(int(row["film_date"]), timezone.utc).date().isoformat(),
            "ted_url": row["url"].strip(), "csv_duration_sec": duration, "views": int(row["views"]),
            "ratings_total": total, "negative_count": sum(ratings.get(k, 0) for k in NEGATIVE),
            "neg_share": round(sum(ratings.get(k, 0) for k in NEGATIVE) / total, 6)}


def cmd_label(_):
    path = ROOT / "source" / "ted_main.csv"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SOURCE["sha256"]:
        raise SystemExit(f"Source sha256 mismatch: {digest}")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    pool = []
    for index, row in enumerate(rows):
        value = label_row(row)
        if value:
            slug = re.sub(r"[^a-z0-9]+", "_", value["ted_url"].rsplit("/", 1)[-1].lower()).strip("_")[:60]
            pool.append({"id": f"ted_{index:04d}_{slug}", **value})
    ec.write_json(ROOT / "pool.json", {"source": SOURCE, "n_rows": len(rows), "eligible": pool})
    print(json.dumps({"rows": len(rows), "eligible": len(pool),
                      "speakers": len({p["speaker"] for p in pool})}))


def cmd_sample(_):
    pool = json.loads((ROOT / "pool.json").read_text(encoding="utf-8"))["eligible"]
    by_speaker = {}
    for item in pool:  # one talk per speaker, chosen by a label-blind hash
        best = by_speaker.get(item["speaker"])
        if best is None or stable_hash(item["id"]) < stable_hash(best["id"]):
            by_speaker[item["speaker"]] = item
    chosen = sorted(by_speaker.values(), key=lambda i: (i["neg_share"], i["id"]))
    n = len(chosen)
    strata = []
    for s in range(N_STRATA):
        members = chosen[s * n // N_STRATA:(s + 1) * n // N_STRATA]
        for item in members:
            item["stratum"] = s
        strata.append(sorted(members, key=lambda i: stable_hash("order", i["id"])))
    ec.write_json(ROOT / "candidates.json", {"strata": strata,
                  "cutpoints": [s[0]["neg_share"] for s in [sorted(x, key=lambda i: i["neg_share"]) for x in strata]]})
    print(json.dumps({"one_per_speaker": n, "per_stratum": [len(s) for s in strata]}))


def _norm(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def accept_hit(item, entry):
    """Label-blind match rule: official TED channel, speaker surname in title, duration within tolerance."""
    if entry.get("channel") not in TED_CHANNELS or not entry.get("duration"):
        return False
    if ec.surname(item["speaker"]) not in _norm(entry.get("title", "")):
        return False
    return abs(entry["duration"] - item["csv_duration_sec"]) <= max(60, 0.15 * item["csv_duration_sec"])


def resolve_one(item):
    cache = ROOT / "resolve" / f"{item['id']}.json"
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    import yt_dlp
    query = f"ytsearch8:{item['speaker']} {item['title']} TED"
    with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True, "no_warnings": True,
                           "socket_timeout": 20}) as ydl:
        entries = ydl.extract_info(query, download=False).get("entries") or []
    hits = [e for e in entries if accept_hit(item, e)]
    result = {"id": item["id"], "query": query, "status": "resolved" if hits else "unresolved",
              "candidates": [{k: e.get(k) for k in ("id", "channel", "duration", "title")} for e in entries]}
    if hits:
        result.update(youtube_id=hits[0]["id"], channel=hits[0]["channel"], yt_duration_sec=hits[0]["duration"],
                      yt_title=hits[0]["title"])
    ec.write_json(cache, result)
    return result


def cmd_resolve(args):
    strata = json.loads((ROOT / "candidates.json").read_text(encoding="utf-8"))["strata"]
    queue = [item for stratum in strata for item in stratum[:PER_STRATUM + RESERVE]]

    def safe(item):
        try:
            return resolve_one(item)
        except Exception as exc:  # network error: no cache written, a rerun retries it
            return {"id": item["id"], "status": "error", "error": str(exc)[:300]}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(safe, queue):
            print(json.dumps({k: result.get(k) for k in ("id", "status", "youtube_id")}), flush=True)


def excerpt(duration):
    """Label-blind position rule: the 120 s centred on the midpoint of the YouTube upload."""
    start = round(max(0.0, duration / 2 - EXCERPT_SEC / 2), 1)
    return start, round(start + EXCERPT_SEC, 1)


def political_urls():
    path = Path.home() / ".orator" / "corpus" / "manifest.json"
    return {v["url"] for v in json.loads(path.read_text(encoding="utf-8")).values()} if path.is_file() else set()


def cmd_split(_):
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists; the split is frozen")
    strata = json.loads((ROOT / "candidates.json").read_text(encoding="utf-8"))["strata"]
    items, seen_urls = [], set()
    for stratum in strata:
        taken = 0
        for item in stratum[:PER_STRATUM + RESERVE]:
            cache = ROOT / "resolve" / f"{item['id']}.json"
            hit = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
            url = f"https://www.youtube.com/watch?v={hit.get('youtube_id')}"
            if hit.get("status") != "resolved" or url in seen_urls:
                continue
            seen_urls.add(url)
            start, end = excerpt(hit["yt_duration_sec"])
            items.append({**item, "source_url": url, "youtube_channel": hit["channel"],
                          "yt_duration_sec": hit["yt_duration_sec"], "start_sec": start, "end_sec": end,
                          "mode": "stage", "genre": "ted_talk"})
            taken += 1
            if taken == PER_STRATUM:
                break
    split_of_surname = {}
    blocked = {e for events in ec.POLITICAL_CORPUS_EVENTS.values() for e in events}
    urls = political_urls()
    for s in range(N_STRATA):
        members = sorted((i for i in items if i["stratum"] == s), key=lambda i: stable_hash("split", i["id"]))
        for k, item in enumerate(members):
            who = ec.surname(item["speaker"])
            split = split_of_surname.get(who) or ("development" if k % 2 == 0 else "heldout")
            if (who, int(item["date"][:4])) in blocked or item["source_url"] in urls:
                split = "development" if who not in split_of_surname else split_of_surname[who]
            split_of_surname.setdefault(who, split)
            item["split"] = split
    dev = [i for i in items if i["split"] == "development"]
    held = [i for i in items if i["split"] == "heldout"]
    ec.assert_heldout_disjoint(dev, held, {}, urls)
    assert len({i["speaker"] for i in items}) == len(items), "one talk per speaker"
    assert not {i["id"] for i in dev} & {i["id"] for i in held}
    pool = json.loads((ROOT / "pool.json").read_text(encoding="utf-8"))
    ec.write_json(MANIFEST, {
        "source": SOURCE, "seed": SEED, "label": "neg_share = (Longwinded + Unconvincing + Obnoxious + Confusing)"
        " / all rating-tag counts; covariates log10(views), year, event_class",
        "eligible_talks": len(pool["eligible"]), "excerpt_rule": "120 s centred on the YouTube upload midpoint",
        "counts": {"development": len(dev), "heldout": len(held)},
        "speeches": [{k: i[k] for k in ("id", "split", "stratum", "speaker", "title", "date", "year", "event",
                                         "event_class", "views", "ratings_total", "negative_count", "neg_share",
                                         "ted_url", "csv_duration_sec", "source_url", "youtube_channel",
                                         "yt_duration_sec", "start_sec", "end_sec", "mode", "genre")}
                     for i in sorted(items, key=lambda i: i["id"])]})
    print(json.dumps({"development": len(dev), "heldout": len(held),
                      "per_stratum": [sum(i["stratum"] == s for i in items) for s in range(N_STRATA)]}))


def cmd_split_confirm(args):
    """Fresh confirmation sample: next unused candidates per stratum, speakers disjoint from the frozen split."""
    if CONFIRM.exists():
        raise SystemExit(f"{CONFIRM} exists; the confirmation sample is frozen")
    import yt_dlp  # noqa: F401  fail fast: resolve_one's errors are skipped below
    used = {i["speaker"] for i in json.loads(MANIFEST.read_text(encoding="utf-8"))["speeches"]}
    used_urls = {i["source_url"] for i in json.loads(MANIFEST.read_text(encoding="utf-8"))["speeches"]} | political_urls()
    strata = json.loads((ROOT / "candidates.json").read_text(encoding="utf-8"))["strata"]
    items = []
    for stratum in strata:
        taken = 0
        for item in stratum[PER_STRATUM + RESERVE:]:
            if item["speaker"] in used:
                continue
            try:
                hit = resolve_one(item)
            except Exception:  # network error: skip; order stays label-blind
                continue
            url = f"https://www.youtube.com/watch?v={hit.get('youtube_id')}"
            if hit.get("status") != "resolved" or url in used_urls:
                continue
            used_urls.add(url)
            start, end = excerpt(hit["yt_duration_sec"])
            items.append({**item, "split": "confirm", "source_url": url, "youtube_channel": hit["channel"],
                          "yt_duration_sec": hit["yt_duration_sec"], "start_sec": start, "end_sec": end,
                          "mode": "stage", "genre": "ted_talk"})
            taken += 1
            if taken == CONFIRM_PER_STRATUM:
                break
    assert len({i["speaker"] for i in items}) == len(items), "one talk per speaker"
    ec.write_json(CONFIRM, {"source": SOURCE, "seed": SEED, "rule": "candidates after index PER_STRATUM + RESERVE in "
                            "each neg_share stratum, label-blind hash order, speakers and URLs disjoint from "
                            "ted-ratings-manifest.json", "count": len(items),
                            "speeches": sorted(items, key=lambda i: i["id"])})
    print(json.dumps({"confirm": len(items), "per_stratum": [sum(i["stratum"] == s for i in items) for s in range(N_STRATA)]}))


# ---------- audio, ASR, content check, grade (exemplar_corpus code, this corpus root) ----------

def load_manifest(split):
    data = json.loads((CONFIRM if split == "confirm" else MANIFEST).read_text(encoding="utf-8"))
    checks = json.loads(CHECKS.read_text(encoding="utf-8")) if CHECKS.is_file() else {}
    items = [dict(i, label=i["neg_share"]) for i in data["speeches"] if i["split"] == split]
    for item in items:
        if item["id"] in checks:
            item["content_check"] = checks[item["id"]]
    return items


def content_check(item):
    """Automated speaker-only rule for one 120 s TED excerpt (charter rule C1), from the cached transcript."""
    transcript, _ = ec.transcribe(item)
    words = transcript.words
    span = EXCERPT_SEC
    covered = sum(w.end - w.start for w in words)
    gaps = [b.start - a.end for a, b in zip(words, words[1:])]
    lead = words[0].start if words else span
    tail = span - words[-1].end if words else span
    mean_conf = sum(w.confidence for w in words) / len(words) if words else 0.0
    reasons = []
    if len(words) < 150:
        reasons.append(f"{len(words)} words < 150")
    if max(gaps + [lead, tail]) > 20:
        reasons.append("non-speech stretch over 20 s")
    if mean_conf < 0.6:
        reasons.append(f"mean word confidence {mean_conf:.2f} < 0.60 (non-English or music)")
    return {"result": "fail" if reasons else "pass", "by": "tools/ted_ratings_corpus.py rule C1 (automated)",
            "date": datetime.now().date().isoformat(), "words": len(words),
            "speech_coverage": round(covered / span, 3), "mean_confidence": round(mean_conf, 3),
            "reasons": reasons}


def cmd_run(args):
    ec.ROOT = ROOT
    ec.assert_committed(CONFIRM if args.split == "confirm" else MANIFEST)
    items = load_manifest(args.split)
    if args.limit:
        items = items[:args.limit]
    stage = args.stage
    log = ROOT / "logs" / f"{args.split}-{stage}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)

    def one(item):
        try:
            if stage == "acquire":
                result = ec.acquire(item)
            elif stage == "transcribe":
                result = {"id": item["id"], "status": "transcribed", "words": len(ec.transcribe(item)[0].words)}
            elif stage == "check":
                result = {"id": item["id"], "status": "checked", "check": content_check(item)}
            else:
                result = ec.grade(item)
        except Exception as exc:
            result = {"id": item["id"], "status": "failed", "error": str(exc)[-600:]}
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(json.dumps(result, ensure_ascii=False)[:300], flush=True)
        return result
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(one, items))
    if stage == "check":  # written for commit; grading reads only the committed copy
        checks = json.loads(CHECKS.read_text(encoding="utf-8")) if CHECKS.is_file() else {}
        checks.update({r["id"]: r["check"] for r in results if r["status"] == "checked"})
        ec.write_json(CHECKS, dict(sorted(checks.items())))
    if stage == "grade":
        ec.assert_committed(CHECKS)


# ---------- analysis (development only until the charter is locked) ----------

def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def residualize(y, covariates):
    import numpy as np
    x = np.column_stack([np.ones(len(y))] + covariates)
    beta, *_ = np.linalg.lstsq(x, np.asarray(y, float), rcond=None)
    return list(np.asarray(y, float) - x @ beta)


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return cov / math.sqrt(va * vb) if va and vb else None


def design(rows):
    classes = sorted({r["event_class"] for r in rows})[1:]
    return [[math.log10(r["views"]) for r in rows], [r["year"] for r in rows]] + \
           [[float(r["event_class"] == c) for r in rows] for c in classes]


def association(rows, metric, n_boot=2000):
    """Spearman, covariate-adjusted partial Spearman (ranks residualized on covariates), extreme-quartile AUC,
    each against neg_share where higher neg_share = worse delivery rating. Bootstrap 95% CI on partial."""
    import random
    use = [r for r in rows if metric in r["metrics"]]
    if len(use) < 20:
        return None
    score = [r["metrics"][metric] for r in use]
    label = [r["neg_share"] for r in use]
    rho = pearson(ranks(score), ranks(label))

    def partial(sub):
        cov = design(sub)
        cov_r = [ranks(c) for c in cov]
        sr = residualize(ranks([r["metrics"][metric] for r in sub]), cov_r)
        lr = residualize(ranks([r["neg_share"] for r in sub]), cov_r)
        return pearson(sr, lr)
    rho_partial = partial(use)
    rng = random.Random(SEED)
    boots = sorted(v for v in (partial([use[rng.randrange(len(use))] for _ in use]) for _ in range(n_boot))
                   if v is not None)
    q = sorted(label)
    lo, hi = q[len(q) // 4], q[3 * len(q) // 4]
    good = [s for s, l in zip(score, label) if l <= lo]
    bad = [s for s, l in zip(score, label) if l >= hi]
    return {"n": len(use), "spearman": round(rho, 3) if rho is not None else None,
            "partial_spearman": round(rho_partial, 3) if rho_partial is not None else None,
            "partial_ci95": [round(boots[int(.025 * len(boots))], 3), round(boots[int(.975 * len(boots)) - 1], 3)]
            if boots else None,
            "auc_low_neg_quartile_higher": round(ec.auc(good, bad), 3) if good and bad else None}


def cmd_analyze(args):
    if args.split != "development":
        lock = REPO / "docs" / "ted-ratings-charter.md"
        if "Status: locked" not in lock.read_text(encoding="utf-8"):
            raise SystemExit("Held-out analysis needs a locked charter")
    ec.ROOT = ROOT
    rows = []
    for item in load_manifest(args.split):
        path = ROOT / "grades" / f"{item['id']}.json"
        if path.is_file():
            report = json.loads(path.read_text(encoding="utf-8"))
            if ec.grade_is_current(item, report):
                rows.append({**item, "metrics": ec.numeric_metrics(report)})
    metrics = sorted({k for r in rows for k in r["metrics"]})
    result = {"split": args.split, "n_graded": len(rows), "label": "neg_share (higher = worse rated)",
              "associations": {m: association(rows, m) for m in metrics},
              "label_vs_covariates": {"views_spearman": round(pearson(ranks([r["views"] for r in rows]),
                                                                      ranks([r["neg_share"] for r in rows])), 3)
                                      if len(rows) > 2 else None}}
    ec.write_json(args.output or ROOT / f"analysis-{args.split}.json", result)
    print(json.dumps({"n_graded": len(rows)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("label").set_defaults(fn=cmd_label)
    sub.add_parser("sample").set_defaults(fn=cmd_sample)
    p = sub.add_parser("resolve")
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_resolve)
    sub.add_parser("split").set_defaults(fn=cmd_split)
    sub.add_parser("split-confirm").set_defaults(fn=cmd_split_confirm)
    p = sub.add_parser("run")
    p.add_argument("--split", choices=["development", "heldout", "confirm"], required=True)
    p.add_argument("--stage", choices=["acquire", "transcribe", "check", "grade"], required=True)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("analyze")
    p.add_argument("--split", choices=["development", "heldout"], default="development")
    p.add_argument("--output", type=Path)
    p.set_defaults(fn=cmd_analyze)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
