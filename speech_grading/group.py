"""Group grading: one report per speaker plus conversation-level metrics.

Input is a Transcript whose words already carry ``speaker`` labels: a labelled
``.json`` (including a ``merged.json`` from an earlier run), VTT ``<v Name>`` /
``Name:`` text, or a folder of per-speaker audio tracks merged by
:func:`load_multitrack`. Every speaker is graded through
``Transcript.filter_by_speaker`` + ``run_on_transcript``, so a group report for one
speaker matches ``--speaker <label>`` exactly.
"""

from __future__ import annotations

import math
import os
import re
import statistics
import sys
from typing import Optional

from .config import Config
from .pipeline import run_on_transcript
from .schema import Transcript, clean_words, derive_transcript_fields, speaker_turns

BACKCHANNEL_MAX_WORDS = 2
BACKCHANNEL_MAX_SEC = 1.0
OVERLAP_TOL_SEC = 0.2

# Exact definitions, written into group.json and group.html beside the numbers.
DEFINITIONS: dict[str, str] = {
    "run": "A maximal stretch of consecutive words (time order, after caption and crowd-noise "
           "cleanup) with one speaker label. Multitrack: one speaker's words on their own track, broken "
           "only by a gap over 1 s that another speaker's word overlaps, so talking over someone does not "
           "split either turn. This is the turn split filter_by_speaker uses.",
    "backchannel": f"A run of at most {BACKCHANNEL_MAX_WORDS} lexical words (filled pauses not counted) "
                   f"lasting at most {BACKCHANNEL_MAX_SEC:g} s, whose previous and next runs belong to the "
                   "same other speaker (multitrack: or that lies inside another speaker's run). It does not "
                   "take the floor.",
    "floor_turns": "Runs left after dropping backchannels, with adjacent same-speaker runs merged, "
                   "so a backchannel does not end the other speaker's turn.",
    "talk_s": "Seconds holding the floor: the sum over the speaker's own turns of (last word end minus "
              "first word start), from filter_by_speaker, so time spent listening is excluded. "
              "n/a without word timing.",
    "share": "talk_s divided by the sum of every speaker's talk_s. Without word timing: the speaker's "
             "lexical words divided by all lexical words.",
    "longest_turn_s / median_turn_s": "Longest and median floor-turn span (last word end minus first "
                                      "word start), seconds.",
    "overlaps_made / overlaps_received": f"A floor turn that starts while another speaker's floor turn began "
                                         f"earlier and ends more than {OVERLAP_TOL_SEC:g} s after this start "
                                         "counts once as made by the starter and once as received by each "
                                         "speaker talked over. Multitrack input only (one track per voice); "
                                         "n/a otherwise, because one channel cannot hold two voices' words.",
    "response_latency_median_s": "Median over floor-turn changes to this speaker of (their first word "
                                 "start minus the previous floor turn's last word end). Negative means "
                                 "they started before the other speaker finished.",
    "balance": "Normalized Shannon entropy of the shares: -sum(p ln p) / ln(N), N = labelled speakers. "
               "1.0 is perfectly even, 0 is one speaker doing all the talking. n/a when N < 2.",
}

WEAK_NOTE = (
    "Pace and pauses separate speakers weakly. Pauses lean on ASR punctuation: a long pause after a "
    "comma or sentence end is weighted lower than a mid-clause one, and Whisper tends to punctuate "
    "where people pause. Pace cuts any silence over 2 s from its clock. Both stay in the overall "
    "score, so read spreads in these two dimensions with care."
)


def speakers(t: Transcript) -> list[str]:
    """Speaker labels in order of first appearance."""
    return list(dict.fromkeys(w.speaker for w in t.words if w.speaker is not None))


def all_labels(t: Transcript) -> list[str]:
    """Word labels plus any track label with no words (a silent track still gets a row)."""
    labels = speakers(t)
    return labels + [k for k in t.tracks if k not in labels]


def runs(t: Transcript) -> list[tuple[Optional[str], list]]:
    """Speaker runs over the same cleaned words and turn split filter_by_speaker uses."""
    if t.tracks:  # one track per voice: turns from each speaker's own timeline, then time order
        cleaned = clean_words(t.words)
        rs = []
        for s in speakers(t):
            ws, starts = speaker_turns(cleaned, s, multitrack=True)
            rs += [(s, ws[a:b]) for a, b in zip(starts, starts[1:] + [len(ws)])]
        return sorted(rs, key=lambda r: (r[1][0].start, r[1][-1].end))
    out: list[tuple[Optional[str], list]] = []
    for w in clean_words(t.words):
        if out and out[-1][0] == w.speaker:
            out[-1][1].append(w)
        else:
            out.append((w.speaker, [w]))
    return out


def _is_backchannel(rs: list, i: int, multitrack: bool = False) -> bool:
    spk, ws = rs[i]
    if spk is None:
        return False
    lexical = sum(not w.is_filled_pause for w in ws)
    if lexical > BACKCHANNEL_MAX_WORDS or ws[-1].end - ws[0].start > BACKCHANNEL_MAX_SEC:
        return False
    if multitrack and any(o not in (None, spk) and ows[0].start <= ws[0].start and ows[-1].end >= ws[-1].end
                          for o, ows in rs):
        return True
    if not 0 < i < len(rs) - 1:
        return False
    before, after = rs[i - 1][0], rs[i + 1][0]
    return before == after and before not in (None, spk)


def group_metrics(t: Transcript, overlap: bool) -> dict:
    """Per-speaker floor metrics plus group-level balance. See DEFINITIONS."""
    labels = all_labels(t)
    timed = t.has_timing
    rs = runs(t)
    turns: list[list] = []  # [speaker, start, end]
    backchannels = dict.fromkeys(labels, 0)
    for i, (spk, ws) in enumerate(rs):
        if spk is None:
            continue
        if _is_backchannel(rs, i, multitrack=bool(t.tracks)):
            backchannels[spk] += 1
        elif turns and turns[-1][0] == spk:
            turns[-1][2] = max(turns[-1][2], max(w.end for w in ws))
        else:
            turns.append([spk, ws[0].start, max(w.end for w in ws)])

    made = dict.fromkeys(labels, 0)
    received = dict.fromkeys(labels, 0)
    latency: dict[str, list[float]] = {s: [] for s in labels}
    if timed:
        for j, (spk, start, _end) in enumerate(turns):
            over = {o for o, s0, e0 in turns if o != spk and s0 < start and e0 > start + OVERLAP_TOL_SEC}
            made[spk] += bool(over)
            for o in over:
                received[o] += 1
            if j and turns[j - 1][0] != spk:
                latency[spk].append(round(start - turns[j - 1][2], 4))

    per: dict[str, dict] = {}
    for s in labels:
        ts = t.filter_by_speaker(s) if s in speakers(t) else None  # None: silent track
        spans = [e - b for o, b, e in turns if o == s]
        per[s] = {
            "words": ts.total_words if ts else 0,
            "talk_s": (round(ts.duration_sec, 3) if ts else 0.0) if timed else None,
            "floor_turns": len(spans),
            "backchannels": backchannels[s],
            "longest_turn_s": round(max(spans), 3) if timed and spans else None,
            "median_turn_s": round(statistics.median(spans), 3) if timed and spans else None,
            "overlaps_made": made[s] if timed and overlap else None,
            "overlaps_received": received[s] if timed and overlap else None,
            "response_latency_median_s": (round(statistics.median(latency[s]), 3)
                                          if timed and latency[s] else None),
        }
    basis = "talk_s" if timed and sum(p["talk_s"] for p in per.values()) > 0 else "words"
    total = sum(p[basis] for p in per.values()) or 1
    for p in per.values():
        p["share"] = round(p[basis] / total, 4)
    shares = [p["share"] for p in per.values() if p["share"] > 0]
    balance = (round(-sum(p * math.log(p) for p in shares) / math.log(len(labels)), 4)
               if len(labels) >= 2 else None)
    all_lat = [x for s in labels for x in latency[s]]
    return {
        "per_speaker": per,
        "group": {
            "speakers": len(labels),
            "timing": timed,
            "share_basis": basis,
            "balance": balance,
            "floor_turns": len(turns),
            "backchannels": sum(backchannels.values()),
            "overlapping_starts": sum(made.values()) if timed and overlap else None,
            "response_latency_median_s": round(statistics.median(all_lat), 3) if all_lat else None,
        },
    }


def grade_group(t: Transcript, cfg: Config, tracks: Optional[dict[str, str]] = None) -> dict:
    """Grade every labelled speaker; speakers under ``group_min_words`` go to not_graded.

    ``tracks`` (label -> audio file) overrides/extends ``t.tracks``; filter_by_speaker
    then points each speaker's audio_path at their own track for prosody.
    """
    if tracks:
        t = t.model_copy(update={"tracks": {**t.tracks, **tracks}})
    labels = all_labels(t)
    if not labels:
        raise ValueError("--group needs speaker labels (a 'speaker' field per word, VTT <v Name>, "
                         "'Name:' lines, or a folder of per-speaker tracks)")
    sub = cfg.model_copy(deep=True)
    sub.speaker = None
    min_words = cfg.thresholds.get("group_min_words", 60)
    reports, not_graded = {}, {}
    spoke = speakers(t)
    for s in labels:
        ts = t.filter_by_speaker(s) if s in spoke else None
        if ts is None or ts.total_words < min_words:
            not_graded[s] = ts.total_words if ts else 0
        else:
            reports[s] = run_on_transcript(ts, sub)
    return {
        "reports": reports,
        "not_graded": not_graded,
        "files": report_stems(list(reports)),
        "min_words": min_words,
        **group_metrics(t, overlap=bool(t.tracks)),
        "definitions": DEFINITIONS,
        "notes": [WEAK_NOTE],
    }


def safe_name(label: str) -> str:
    """Filesystem-safe file stem for a speaker label."""
    return re.sub(r"[^\w.-]+", "_", label).strip("._") or "speaker"


def report_stems(labels: list[str]) -> dict[str, str]:
    """Label -> unique file stem in --out-dir. Case-insensitive (Windows), and never
    'group' or 'merged', which the group run writes itself."""
    taken, out = {"group", "merged"}, {}
    for label in labels:
        stem = base = safe_name(label)
        n = 2
        while stem.lower() in taken:
            stem, n = f"{base}_{n}", n + 1
        taken.add(stem.lower())
        out[label] = stem
    return out


# --------------------------------------------------------------------------- #
# Multitrack folder input (one audio file per speaker, e.g. Zoom "separate audio")
# --------------------------------------------------------------------------- #

AUDIO_EXTS = {".wav", ".m4a", ".mp3", ".flac", ".ogg", ".opus", ".aac", ".wma",
              ".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def label_from_path(path: str, taken: Optional[set] = None) -> str:
    """'audioAliceSmith21234.m4a' -> 'AliceSmith'; a repeat in ``taken`` gets '_2', '_3'.

    ponytail: Zoom pattern only (leading 'audio', trailing numeric id); a name that
    really ends in digits loses them. Add an explicit --names map if that bites.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    label = re.sub(r"\d+$", "", re.sub(r"^audio", "", stem, flags=re.I)) or stem
    if taken is not None:
        base, n = label, 2
        while label in taken:
            label, n = f"{base}_{n}", n + 1
        taken.add(label)
    return label


def _audio_seconds(path: str) -> Optional[float]:
    # ponytail: best-effort length for the time-zero warning only; None skips the check.
    try:
        if path.lower().endswith(".wav"):
            import wave

            with wave.open(path) as w:
                return w.getnframes() / w.getframerate()
        import av  # ships with faster-whisper

        with av.open(path) as c:
            return c.duration / 1e6 if c.duration else None
    except Exception:
        return None


def load_multitrack(folder: str, cfg: Config) -> Transcript:
    """Transcribe each per-speaker track with one backend (VAD on), tag, and merge.

    Assumes every track starts at meeting time zero (Zoom pads per-participant files;
    unverified). Warns when track lengths differ by more than 1 s.
    """
    from . import pipeline

    files = sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in AUDIO_EXTS)
    if not files:
        raise ValueError(f"no audio tracks found in folder {folder}")
    backend = pipeline._make_backend(cfg, vad_filter=True)
    taken: set = set()
    words, tracks, lengths, engine = [], {}, {}, "asr"
    for f in files:
        path = os.path.abspath(os.path.join(folder, f))
        label = label_from_path(path, taken)
        track = path
        if cfg.enable_acoustic and not path.lower().endswith(".wav"):
            track = pipeline.extract_audio_from_video(path)  # generic ffmpeg -> 16 kHz mono WAV
        tt = backend.transcribe(track)
        engine = tt.engine
        for w in tt.words:
            w.speaker = label
        words += tt.words
        tracks[label] = track
        sec = _audio_seconds(track)
        if sec is not None:
            lengths[label] = sec
    if len(lengths) > 1 and max(lengths.values()) - min(lengths.values()) > 1.0:
        print("orator: warning: track lengths differ by more than 1 s "
              f"({', '.join(f'{k} {v:.1f}s' for k, v in lengths.items())}); if the tracks do not "
              "share time zero, overlap, latency and prosody spans are wrong", file=sys.stderr)
    words.sort(key=lambda w: (w.start, w.end))
    merged = Transcript(words=words, engine=f"{engine} multitrack", tracks=tracks, duration_sec=0.0)
    return derive_transcript_fields(merged)
