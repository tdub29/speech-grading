"""Make one-factor audio comparisons, with provenance, outside the repository.

Run ``python -m speech_grading.eval.ab_pairs --help`` for the CLI. These edits are
perturbations, not guaranteed quality degradations. Grade the resulting files to
test that hypothesis. The insertion boundary must be checked within a clause;
word alignment alone cannot establish clause structure or speaker identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


CORPUS_ROOT = Path.home() / ".orator" / "corpus" / "exemplars"


def _within_corpus(path: Path) -> Path:
    path = path.expanduser().resolve()
    if not path.is_relative_to(CORPUS_ROOT.resolve()) or path == CORPUS_ROOT.resolve():
        raise ValueError(f"Output must be beneath {CORPUS_ROOT}")
    return path


def _audio(y, sample_rate: int):
    import numpy as np

    y = np.asarray(y, dtype=float)
    if y.ndim != 1 or y.size == 0 or not np.isfinite(y).all():
        raise ValueError("Audio must be nonempty, finite, mono samples")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("Sample rate must be a positive integer")
    if np.max(np.abs(y)) > 1:
        raise ValueError("Audio samples must be within [-1, 1]")
    return y


def _filtered(y, sample_rate: int, expression: str):
    import numpy as np

    y = _audio(y, sample_rate)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required on PATH")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-f", "f32le", "-ar", str(sample_rate),
         "-ac", "1", "-i", "pipe:0", "-af", expression, "-f", "f32le", "pipe:1"],
        input=y.astype("<f4").tobytes(), capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode(errors='replace').strip()}")
    return _audio(np.frombuffer(result.stdout, dtype="<f4").copy(), sample_rate)


def time_stretch(y, sample_rate: int, rate: float):
    """Pitch-preserving atempo; rate .8 means slower, 1.25 means faster."""
    if not math.isfinite(rate) or not 0.5 <= rate <= 2:
        raise ValueError("Rate must be finite and within [0.5, 2]")
    return _filtered(y, sample_rate, f"atempo={rate}")


def flatten_pitch(y, sample_rate: int):
    """Praat PSOLA with a constant pitch tier at the voiced median F0."""
    import numpy as np
    import parselmouth
    from parselmouth.praat import call

    y = _audio(y, sample_rate)
    sound = parselmouth.Sound(y, sampling_frequency=sample_rate)
    frequencies = sound.to_pitch(pitch_floor=50, pitch_ceiling=800).selected_array["frequency"]
    voiced = frequencies[frequencies > 0]
    if voiced.size < 2:
        raise ValueError("Pitch flattening requires at least two voiced frames")
    manipulation = call(sound, "To Manipulation", 0.01, 50, 800)
    tier = call(manipulation, "Extract pitch tier")
    call(tier, "Remove points between", 0, sound.duration)
    call(tier, "Add point", sound.duration / 2, float(np.median(voiced)))
    call([tier, manipulation], "Replace pitch tier")
    edited = call(manipulation, "Get resynthesis (overlap-add)").values[0]
    # PSOLA can overshoot the input peak; do not silently add a gain edit.
    if np.max(np.abs(edited)) > 1:
        raise ValueError("Pitch resynthesis exceeds PCM range; lower source level first")
    return _audio(edited, sample_rate)


def compress_dynamic_range(y, sample_rate: int):
    """RMS compressor, no makeup gain; threshold .03, ratio 12, 1/30 ms."""
    return _filtered(y, sample_rate,
                     "acompressor=threshold=0.03:ratio=12:attack=1:release=30:makeup=1:detection=rms")


def insert_audio(y, sample_rate: int, at_sec: float, inserted):
    """Insert samples at an explicitly supplied aligned word boundary."""
    import numpy as np

    y = _audio(y, sample_rate)
    inserted = _audio(inserted, sample_rate)
    if not math.isfinite(at_sec) or not 0 < at_sec < len(y) / sample_rate:
        raise ValueError("Insertion must be strictly inside the clip")
    at = round(at_sec * sample_rate)
    return np.concatenate((y[:at], inserted, y[at:]))


def pick_midclause_boundary(texts: list[str], starts: list[float], ends: list[float], fillers: list[bool], min_time: float = 5.0) -> int | None:
    """First word index ending a tight, unpunctuated, filler-free boundary after min_time."""
    for i in range(len(texts) - 1):
        if starts[i] >= min_time and \
           not texts[i].rstrip().endswith((".", ",", ";", ":", "!", "?")) and \
           not fillers[i] and not fillers[i + 1] and \
           0 <= starts[i + 1] - ends[i] < 0.15:
            return i
    return None


def degradation_verdict(baseline: dict, edited: dict, target: str, expect: str, tol: float = 0.1) -> dict:
    """Did ``target`` move in the ``expect`` direction, and which other numeric metrics moved over ``tol``?"""
    b = baseline[target]
    e = edited[target]
    moved = e > b if expect == "up" else e < b

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    collateral = sorted(k for k in baseline if k != target and k in edited
                        and num(baseline[k]) and num(edited[k]) and baseline[k] != 0
                        and abs(edited[k] - baseline[k]) / abs(baseline[k]) > tol)
    return {"target": target, "baseline": b, "edited": e, "moved_as_expected": moved, "collateral": collateral}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_pairs(source: Path, output_dir: Path, *, start: float, end: float,
               after_word_end: float, before_word_start: float, speaker: str,
               mid_clause: bool, silence_sec: float = 1.5, source_url: str = "",
               filler_source: Path | None = None, filler_start: float | None = None,
               filler_end: float | None = None, filler_speaker: str | None = None) -> dict:
    """Write baseline, six edits when filler exists, and deterministic manifest.

    All times refer to the original source, except filler_start/filler_end which
    refer to filler_source. Identity and mid-clause placement are caller labels.
    No word text, transcript or audio is written outside CORPUS_ROOT.
    """
    import numpy as np
    import soundfile as sf

    output_dir = _within_corpus(Path(output_dir))
    source = Path(source).expanduser().resolve(strict=True)
    if not speaker.strip() or not mid_clause:
        raise ValueError("Supply speaker and explicitly confirm a mid-clause boundary")
    times = (start, end, after_word_end, before_word_start, silence_sec)
    if not all(math.isfinite(value) for value in times):
        raise ValueError("Times must be finite")
    if not 0 <= start < after_word_end <= before_word_start < end or silence_sec <= 0:
        raise ValueError("Require 0 <= start < word end <= next word start < end and positive silence")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    info = sf.info(source)
    sample_rate = info.samplerate
    if end > info.frames / sample_rate:
        raise ValueError("Clip end exceeds source duration")
    y, _ = sf.read(source, start=round(start * sample_rate), stop=round(end * sample_rate),
                   always_2d=True)
    y = _audio(y.mean(axis=1), sample_rate)
    at_sec = after_word_end - start
    edits = {
        "baseline": (y, {}),
        "pace_0.8x": (time_stretch(y, sample_rate, .8), {"rate": .8, "method": "ffmpeg atempo"}),
        "pace_1.25x": (time_stretch(y, sample_rate, 1.25), {"rate": 1.25, "method": "ffmpeg atempo"}),
        "pitch_flat": (flatten_pitch(y, sample_rate), {"method": "Praat constant median pitch tier PSOLA"}),
        "dynamics_compressed": (compress_dynamic_range(y, sample_rate),
                                {"method": "ffmpeg acompressor RMS", "threshold": .03,
                                 "ratio": 12, "attack_ms": 1, "release_ms": 30, "makeup": 1}),
        "silence_inserted": (insert_audio(y, sample_rate, at_sec, np.zeros(round(silence_sec * sample_rate))),
                             {"at_clip_sec": at_sec, "duration_sec": silence_sec}),
    }
    filler_fields = (filler_source, filler_start, filler_end, filler_speaker)
    if any(value is not None for value in filler_fields):
        if any(value is None for value in filler_fields):
            raise ValueError("Filler requires source, start, end and speaker")
        if filler_speaker.strip() != speaker.strip():
            raise ValueError("Filler speaker must match the source speaker label")
        if not all(math.isfinite(value) for value in (filler_start, filler_end)) or not 0 <= filler_start < filler_end:
            raise ValueError("Require finite 0 <= filler start < filler end")
        filler_source = Path(filler_source).expanduser().resolve(strict=True)
        filler_info = sf.info(filler_source)
        if filler_info.samplerate != sample_rate:
            raise ValueError("Filler and source sample rates must match")
        if filler_end > filler_info.frames / sample_rate:
            raise ValueError("Filler end exceeds source duration")
        filler, _ = sf.read(filler_source, start=round(filler_start * sample_rate),
                            stop=round(filler_end * sample_rate), always_2d=True)
        edits["filled_pause_inserted"] = (
            insert_audio(y, sample_rate, at_sec, filler.mean(axis=1)),
            {"at_clip_sec": at_sec, "source": str(filler_source), "source_sha256": _sha256(filler_source),
             "source_start_sec": filler_start, "source_end_sec": filler_end,
             "speaker_label": filler_speaker, "label_basis": "caller identified a same-speaker filled pause"},
        )
    manifest = {
        "schema_version": 1, "source": str(source), "source_sha256": _sha256(source),
        "source_url": source_url, "source_start_sec": start, "source_end_sec": end,
        "speaker_label": speaker, "sample_rate": sample_rate, "encoding": "mono PCM_16 WAV",
        "boundary": {"after_word_end_sec": after_word_end, "before_word_start_sec": before_word_start,
                     "label_basis": "caller identified a mid-clause word boundary"},
        "caveat": "One-factor perturbations; score direction and collateral effects require measurement",
        "outputs": [],
        "skipped": [] if filler_source else [{"transform": "filled_pause_inserted", "reason": "No identified same-speaker filler supplied"}],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, (samples, parameters) in edits.items():
        path = _within_corpus(output_dir / f"{name}.wav")
        with path.open("xb") as handle:
            sf.write(handle, samples, sample_rate, format="WAV", subtype="PCM_16")
        manifest["outputs"].append({"transform": name, "path": str(path), "sha256": _sha256(path),
                                    "duration_sec": len(samples) / sample_rate, "parameters": parameters})
    with _within_corpus(output_dir / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="Local recording; never downloaded by this tool")
    parser.add_argument("output_dir", type=Path, help=f"Empty directory beneath {CORPUS_ROOT}")
    for name in ("start", "end", "after-word-end", "before-word-start"):
        parser.add_argument(f"--{name}", type=float, required=True, help="Absolute seconds in source recording")
    parser.add_argument("--speaker", required=True, help="Caller supplied speaker identity")
    parser.add_argument("--mid-clause", action="store_true", required=True, help="Confirm the boundary is inside a clause, checked against audio")
    parser.add_argument("--silence-sec", type=float, default=1.5)
    parser.add_argument("--source-url", default="", help="Public source provenance only")
    parser.add_argument("--filler-source", type=Path, help="Optional recording containing an identified same-speaker um/uh")
    parser.add_argument("--filler-start", type=float)
    parser.add_argument("--filler-end", type=float)
    parser.add_argument("--filler-speaker", help="Must match --speaker; caller must identify the filler by listening")
    args = vars(parser.parse_args(argv))
    try:
        manifest = make_pairs(**args)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"ab_pairs: {error}\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
