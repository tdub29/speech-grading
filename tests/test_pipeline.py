"""Integration tests for the end-to-end offline pipeline and scorer."""

from __future__ import annotations

from speech_grading.config import Config
from speech_grading.pipeline import run_on_transcript
from speech_grading.report import highlight_transcript_html, render_html, render_json


def test_run_on_transcript_offline(sample_transcript):
    cfg = Config()  # offline word-choice, no acoustic
    report = run_on_transcript(sample_transcript, cfg)

    # Composite is a real 0-100 number.
    assert 0.0 <= report.overall_score <= 100.0

    # Prosody is absent (no audio) so its weight is redistributed: the remaining
    # dimension weights must renormalize to ~1.0.
    dims = {d.dimension for d in report.dimensions}
    assert "prosody" not in dims
    assert {"fillers", "pace", "pauses", "word_choice", "vocabulary", "hedging", "readability"} <= dims
    assert abs(sum(d.weight for d in report.dimensions) - 1.0) < 1e-6

    assert report.metadata["word_choice_mode"] == "offline-lexicon"


def test_pipeline_flags_the_tripped_up_word(sample_transcript):
    report = run_on_transcript(sample_transcript, Config())
    tripped = [f for f in report.findings if f.kind == "tripped_up"]
    assert tripped, "expected at least one tripped-up moment"
    # The 1.35s low-confidence pause before 'utilize' is the planted stumble.
    words = sample_transcript.words
    assert any(words[f.word_index].normalized == "utilize" for f in tripped)
    util = next(f for f in tripped if words[f.word_index].normalized == "utilize")
    assert util.suggestion == "use"  # curated stronger word


def test_render_outputs(sample_transcript, tmp_path):
    report = run_on_transcript(sample_transcript, Config())

    html_str = highlight_transcript_html(report)
    assert "<span" in html_str and "f-tripped" in html_str  # the stumble is highlighted

    html_path = tmp_path / "r.html"
    json_path = tmp_path / "r.json"
    render_html(report, str(html_path))
    render_json(report, str(json_path))
    assert html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert '"overall_score"' in json_path.read_text(encoding="utf-8")


def test_prosody_weight_redistribution_keeps_scale(sample_transcript):
    # With acoustic enabled but no audio, prosody still returns None and the
    # composite stays on a 0-100 scale (no divide-by-zero, no weight leak).
    cfg = Config(enable_acoustic=True)
    report = run_on_transcript(sample_transcript, cfg)
    assert 0.0 <= report.overall_score <= 100.0


def test_pipeline_speaker_filter(sample_transcript):
    # Label half words with A, half with B
    for i, w in enumerate(sample_transcript.words):
        w.speaker = "speaker_a" if i % 2 == 0 else "speaker_b"
    cfg = Config(speaker="speaker_a")
    report = run_on_transcript(sample_transcript, cfg)
    words = report.transcript.words
    assert words and all(w.speaker == "speaker_a" for w in words)
    # every kept word opens a turn, so no gap may score as a pause
    assert not [f for f in report.findings if f.kind == "long_pause"]
    assert report.transcript.duration_sec == round(sum(w.end - w.start for w in words), 4)


def test_video_input_always_transcribes_extracted_wav(monkeypatch, tmp_path):
    from speech_grading import pipeline
    from speech_grading.schema import Transcript, Word

    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"dummy video content")
    wav = str(tmp_path / "extracted.wav")
    calls = []

    class Backend:
        def transcribe(self, path):
            calls.append(path)
            return Transcript(words=[Word(text="hello", start=0.0, end=1.0)])

    monkeypatch.setattr(pipeline, "_make_backend", lambda cfg: Backend())
    monkeypatch.setattr(pipeline, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(pipeline, "extract_audio_from_video", lambda p: wav)
    t = pipeline.load_input(str(vid), Config())
    assert calls == [wav]  # never the .mp4: prosody must get a WAV
    assert t.audio_path == wav


def test_asr_error_is_not_swallowed(monkeypatch, tmp_path):
    import pytest
    from speech_grading import pipeline

    class Boom:
        def transcribe(self, path):
            raise MemoryError("oom")

    monkeypatch.setattr(pipeline, "_make_backend", lambda cfg: Boom())
    monkeypatch.setattr(pipeline, "find_ffmpeg", lambda: None)
    with pytest.raises(MemoryError):
        pipeline.load_input(str(tmp_path / "talk.mp4"), Config())


def test_video_asr_missing_ffmpeg(monkeypatch, tmp_path):
    import pytest
    from speech_grading import pipeline

    vid = tmp_path / "test.mp4"
    vid.write_bytes(b"dummy video")
    monkeypatch.setattr(pipeline, "find_ffmpeg", lambda: None)
    with pytest.raises(RuntimeError) as exc_info:
        pipeline.extract_audio_from_video(str(vid))
    assert "ffmpeg not found" in str(exc_info.value)


def test_add_visual_merges_findings_and_writes_rows(monkeypatch, tmp_path, sample_transcript):
    import json
    from speech_grading import pipeline
    from speech_grading.analysis import visual

    frames = [dict(t=i / 10, face_visible=True, smile=0.1, brow_raise=0.0, brow_furrow=0.0,
                   jaw_open=0.0, gaze_off=0.0, pitch_deg=0.0, hand_face_dist=None,
                   wrist_y_rel=None, hands_visible=False) for i in range(300)]
    monkeypatch.setattr(visual, "extract_frames", lambda p: frames)
    rows = tmp_path / "rows.jsonl"
    cfg = Config(mode="zoom", visual_rows=str(rows))
    rep = pipeline.add_visual(run_on_transcript(sample_transcript, cfg), sample_transcript, "x.mp4", cfg)
    assert rep.metrics["visual"]["mode"] == "zoom"
    assert rows.read_text().strip()
    json.loads(rows.read_text().splitlines()[0])
