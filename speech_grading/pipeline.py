"""End-to-end orchestration: (transcribe | load) -> analyze -> word-choice -> score -> report.

Two entry points:
  * :func:`run_pipeline` -- full run from an audio file or a Transcript JSON fixture.
  * :func:`run_on_transcript` -- analysis-only path over an in-memory Transcript
    (no ASR, no network). This is what the tests exercise.
"""

from __future__ import annotations

import os

from .analysis.fillers import detect_fillers
from .analysis.pace import compute_pace
from .analysis.pauses import detect_pauses
from .analysis.readability import compute_readability
from .analysis.repetitions import detect_repetitions
from .analysis.vocabulary import compute_vocabulary
from .analysis.weak_words import detect_weak_words
from .analysis.prosody import compute_prosody
from .config import MODE_THRESHOLDS, Config
from .schema import (
    Finding,
    Report,
    Transcript,
    WordChoiceFinding,
    derive_transcript_fields,
    load_transcript_json,
    load_transcript_text,
)
from .scorer import score
from .wordchoice.base import analyze_word_choice

# WordChoiceFinding.issue_type -> Finding.kind
_ISSUE_KIND = {"tripped_up": "tripped_up", "weak": "weak_word", "hedge": "hedge", "filler": "filler"}


def _wordchoice_to_findings(t: Transcript, wcs: list[WordChoiceFinding]) -> list[Finding]:
    out: list[Finding] = []
    n = len(t.words)
    for wc in wcs:
        if not (0 <= wc.word_index < n):
            continue
        w = t.words[wc.word_index]
        out.append(
            Finding(
                kind=_ISSUE_KIND.get(wc.issue_type, "weak_word"),
                word_index=wc.word_index,
                start=w.start,
                end=w.end,
                original=wc.original or w.text,
                suggestion=wc.suggestion,
                rationale=wc.rationale,
                score=wc.confidence,
                source="wordchoice",
            )
        )
    return out


def run_on_transcript(t: Transcript, cfg: Config) -> Report:
    """Run the full analysis + scoring stack over an already-built Transcript."""
    if cfg.speaker:
        t = t.filter_by_speaker(cfg.speaker)
    findings: list[Finding] = []
    findings += detect_fillers(t, cfg.thresholds)
    findings += detect_repetitions(t)
    findings += detect_weak_words(t)

    dim_scores = [
        compute_vocabulary(t),
        compute_readability(t),
    ]

    # Timing-dependent dimensions only apply when the transcript carries word
    # timestamps (audio or a timed JSON fixture); a text-only transcript skips them
    # and the scorer redistributes their weight.
    if t.has_timing:
        findings += detect_pauses(t, cfg.thresholds)
        dim_scores.append(compute_pace(t, {**cfg.thresholds, **MODE_THRESHOLDS.get(cfg.mode, {})}))

    prosody_ds, prosody_findings = compute_prosody(t, cfg)
    if prosody_ds is not None:
        dim_scores.append(prosody_ds)
        findings += prosody_findings

    # Word choice (LLM with deterministic offline fallback) -> tripped-up + suggestions.
    wcs, wc_mode = analyze_word_choice(t, cfg)
    findings += _wordchoice_to_findings(t, wcs)

    return score(t, findings, dim_scores, cfg, word_choice_mode=wc_mode)


def find_ffmpeg() -> str | None:
    """Locate ffmpeg binary on PATH or known local install paths."""
    import shutil
    from pathlib import Path

    w = shutil.which("ffmpeg")
    if w:
        return w
    fg = Path(__file__).resolve().parents[2] / "Fantasy Golf App" / "tools" / "video" / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if fg.is_file():
        return str(fg)
    return None


def extract_audio_from_video(video_path: str) -> str:
    """Extract 16kHz mono WAV audio from a video container using ffmpeg."""
    import atexit
    import subprocess
    import tempfile

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            f"ffmpeg not found: cannot extract audio from {video_path} "
            "(checked PATH and Fantasy Golf App tools/video/bin)"
        )
    fd, out_path = tempfile.mkstemp(suffix=".wav", prefix="orator_audio_")
    os.close(fd)
    cmd = [
        ffmpeg,
        "-y",
        "-loglevel", "error",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise RuntimeError(f"ffmpeg audio extraction failed (code {res.returncode}): {res.stderr.strip()}")

    def _cleanup():
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass

    atexit.register(_cleanup)
    return out_path


def load_input(input_path: str, cfg: Config) -> Transcript:
    """Resolve an input path to a canonical Transcript.

    ``.json`` -> timed Transcript fixture; ``.txt/.md/.vtt/.srt`` -> text-only
    Transcript (no timestamps); anything else -> transcribe via the ASR backend.
    """
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".json":
        t = load_transcript_json(input_path)
    elif ext in (".txt", ".md", ".vtt", ".srt"):
        t = load_transcript_text(input_path)
    else:
        from .analysis import visual

        backend = _make_backend(cfg)
        audio_path = input_path
        # Video: always hand ASR and prosody a WAV. Backends that read video directly
        # (faster-whisper via PyAV) still leave audio_path on the .mp4, which parselmouth
        # cannot open, and prosody would silently score the speaker as monotone.
        if visual.is_video(input_path) and find_ffmpeg():
            try:
                audio_path = extract_audio_from_video(input_path)
            except RuntimeError as e:
                raise RuntimeError(f"cannot read audio from {input_path} (no audio track?): {e}") from e
        t = backend.transcribe(audio_path)
        if not t.audio_path:
            t.audio_path = audio_path
        t = derive_transcript_fields(t)
    return t


def add_visual(report: Report, t: Transcript, input_path: str, cfg: Config) -> Report:
    """Video input: run the visual tier and attach findings + rates to the report.

    Degrades gracefully: any VisualUnavailable becomes a note in report.metrics.
    """
    from .analysis import visual, visual_events

    if not (cfg.enable_video and visual.is_video(input_path)):
        return report
    try:
        frames = visual.extract_frames(input_path)
    except visual.VisualUnavailable as e:
        report.metrics["visual"] = {"skipped": str(e)}
        return report
    ends = [t.words[e].end + cfg.av_offset_sec for _, e in t.sentences if 0 <= e < len(t.words)]
    res = visual_events.summarize(frames, ends, cfg.mode,
                                  speaking_sec=t.duration_sec if cfg.speaker else None,
                                  camera_level=cfg.camera_level)
    report.findings += res.pop("findings")
    report.metrics["visual"] = res
    if cfg.visual_rows:
        import json

        with open(cfg.visual_rows, "w", encoding="utf-8") as fh:
            for row in visual_events.feature_rows(frames, mode=cfg.mode):
                fh.write(json.dumps(row) + "\n")
    return report


def run_pipeline(input_path: str, cfg: Config) -> Report:
    """Full run. If ``input_path`` is a Transcript JSON/text, skip ASR; else transcribe."""
    t = load_input(input_path, cfg)
    if cfg.speaker:
        t = t.filter_by_speaker(cfg.speaker)
    return add_visual(run_on_transcript(t, cfg), t, input_path, cfg)


def _make_backend(cfg: Config):
    name = cfg.asr_backend
    if name == "faster-whisper":
        from .asr.faster_whisper_backend import FasterWhisperBackend

        return FasterWhisperBackend(
            model_size=cfg.asr_model_size,
            device=cfg.asr_device,
            compute_type=cfg.asr_compute_type,
        )
    if name == "crisper-whisper":
        from .asr.crisper_whisper_backend import CrisperWhisperBackend

        return CrisperWhisperBackend(cfg)
    if name == "vosk":
        from .asr.vosk_backend import VoskBackend

        return VoskBackend()
    raise ValueError(f"Unknown ASR backend: {name!r}")
