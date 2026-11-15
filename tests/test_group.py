"""Group mode: ASR model reuse, conversation metrics, --group CLI, multitrack folders."""

from __future__ import annotations

import json
import math
import os
import sys
import types

import pytest

from speech_grading import cli, pipeline
from speech_grading.config import Config
from speech_grading.group import grade_group, group_metrics, label_from_path, load_multitrack
from speech_grading.pipeline import run_on_transcript
from speech_grading.schema import Transcript, Word, load_transcript_json

MEETING = os.path.join(os.path.dirname(__file__), "fixtures", "meeting_3speakers.json")


# --- Step 1: backend caches the model and passes vad_filter ------------------------------

def test_faster_whisper_model_built_once_and_vad_passed(monkeypatch):
    built, calls = [], []

    class StubModel:
        def __init__(self, *a, **kw):
            built.append(a)

        def transcribe(self, path, **kw):
            calls.append(kw)
            return [], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=StubModel))
    from speech_grading.asr.faster_whisper_backend import FasterWhisperBackend

    b = FasterWhisperBackend(vad_filter=True)
    b.transcribe("a.wav")
    b.transcribe("b.wav")
    assert len(built) == 1
    assert [c["vad_filter"] for c in calls] == [True, True]
    FasterWhisperBackend().transcribe("c.wav")
    assert calls[-1]["vad_filter"] is False  # single-file default unchanged


# --- Step 2: group metrics + per-speaker grading on the hand-built fixture --------------

def test_group_metrics_on_meeting_fixture():
    t = load_transcript_json(MEETING)
    m = group_metrics(t, overlap=True)
    per, g = m["per_speaker"], m["group"]

    # talk_s = summed turn spans from filter_by_speaker; multitrack, so Bob's "yeah" over
    # Alice's 0.9 s breath does not split her turn
    talk = {"Alice": 17.0 + 9.9, "Bob": 0.3 + 25.9, "Cara": 1.9}
    total = sum(talk.values())
    for s, v in talk.items():
        assert per[s]["talk_s"] == pytest.approx(v)
        assert per[s]["share"] == pytest.approx(v / total, abs=1e-4)

    assert g["backchannels"] == 1 and per["Bob"]["backchannels"] == 1
    # Bob's "yeah" does not split Alice's floor turn
    assert [per[s]["floor_turns"] for s in ("Alice", "Bob", "Cara")] == [2, 1, 1]
    assert per["Alice"]["longest_turn_s"] == pytest.approx(17.0)
    assert per["Alice"]["median_turn_s"] == pytest.approx((17.0 + 9.9) / 2)

    assert (per["Bob"]["overlaps_made"], per["Alice"]["overlaps_received"]) == (1, 1)
    assert per["Alice"]["overlaps_made"] == 0 and per["Cara"]["overlaps_made"] == 0
    assert g["overlapping_starts"] == 1

    assert per["Bob"]["response_latency_median_s"] == pytest.approx(-0.4)
    assert per["Cara"]["response_latency_median_s"] == pytest.approx(1.0)
    assert per["Alice"]["response_latency_median_s"] == pytest.approx(0.6)
    assert g["response_latency_median_s"] == pytest.approx(0.6)

    p = [v / total for v in talk.values()]
    assert g["balance"] == pytest.approx(-sum(x * math.log(x) for x in p) / math.log(3), abs=1e-3)

    # single-channel input: overlap is n/a, not 0
    assert group_metrics(t, overlap=False)["per_speaker"]["Bob"]["overlaps_made"] is None


def test_grade_group_matches_direct_speaker_runs():
    t = load_transcript_json(MEETING)
    cfg = Config()
    res = grade_group(t, cfg)
    assert res["not_graded"] == {"Cara": 5}
    assert set(res["reports"]) == {"Alice", "Bob"}
    for s, rep in res["reports"].items():
        direct = run_on_transcript(t.filter_by_speaker(s), cfg)
        assert rep.overall_score == direct.overall_score
        assert rep.transcript.audio_path == t.tracks[s]  # own track, not the merged path

    bob = res["reports"]["Bob"].transcript
    assert bob.turn_starts == [0, 1]
    assert bob.duration_sec == pytest.approx(0.3 + 25.9)  # sum of turn spans, not 8.2 -> 42.5
    assert bob.gap_before(1) == 0.0  # 8.1 s spent listening is not a pause
    assert not any(f.kind == "long_pause" and f.word_index == 1 for f in res["reports"]["Bob"].findings)


# --- Step 3: CLI --group ---------------------------------------------------------------

def test_cli_group_writes_reports(tmp_path, capsys):
    out = tmp_path / "out"
    assert cli.main([MEETING, "--group", "--out-dir", str(out)]) == 0
    for f in ("group.html", "group.json", "Alice.html", "Alice.json", "Bob.html", "Bob.json"):
        assert (out / f).is_file(), f
    assert not (out / "Cara.html").exists()
    page = (out / "group.html").read_text(encoding="utf-8")
    assert "Alice" in page and "Bob" in page and "weakly" in page
    summary = json.loads((out / "group.json").read_text(encoding="utf-8"))
    assert {r["speaker"] for r in summary["leaderboard"]} == {"Alice", "Bob"}
    assert "leaderboard:" in capsys.readouterr().out


def test_cli_group_vtt_untimed(tmp_path):
    a = " ".join(f"word{i} plan" for i in range(35))
    b = " ".join(f"item{i} goal" for i in range(35))
    vtt = tmp_path / "call.vtt"
    vtt.write_text(f"WEBVTT\n\n00:00.000 --> 00:05.000\n<v Ana>{a}</v>\n\n"
                   f"00:05.000 --> 00:09.000\n<v Bob>{b}</v>\n", encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main([str(vtt), "--group", "--out-dir", str(out)]) == 0
    assert (out / "Ana.html").is_file() and (out / "Bob.html").is_file()
    s = json.loads((out / "group.json").read_text(encoding="utf-8"))
    assert s["group"]["share_basis"] == "words" and s["group"]["timing"] is False
    assert s["per_speaker"]["Ana"]["talk_s"] is None
    assert (s["per_speaker"]["Ana"]["words"], s["per_speaker"]["Bob"]["words"]) == (70, 70)
    assert s["per_speaker"]["Ana"]["response_latency_median_s"] is None
    ana, bob = s["per_speaker"]["Ana"], s["per_speaker"]["Bob"]
    assert ana["share"] == pytest.approx(ana["words"] / (ana["words"] + bob["words"]), abs=1e-4)


def test_cli_group_rejects_speaker(tmp_path):
    assert cli.main([MEETING, "--group", "--speaker", "Alice", "--out-dir", str(tmp_path)]) == 2


# --- Step 4: multitrack folder ---------------------------------------------------------

def test_label_from_path():
    assert label_from_path("rec/audioAliceSmith21234.m4a") == "AliceSmith"
    assert label_from_path("bob.wav") == "bob"
    taken: set = set()
    assert [label_from_path(p, taken) for p in ("audioAna11.m4a", "audioAna22.m4a", "audioAna33.m4a")] \
        == ["Ana", "Ana_2", "Ana_3"]


def test_multitrack_folder(tmp_path, monkeypatch):
    (tmp_path / "alice.wav").write_bytes(b"")
    (tmp_path / "bob.wav").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    canned = {
        "alice.wav": [("Hi", 0.0, 0.4), ("there.", 0.5, 0.9), ("Agreed.", 3.0, 3.5)],
        "bob.wav": [("Hello", 1.0, 1.4), ("back.", 1.5, 2.0)],
    }
    built = []

    class Stub:
        def transcribe(self, path):
            ws = [Word(text=x, start=s, end=e) for x, s, e in canned[os.path.basename(path)]]
            return Transcript(words=ws, audio_path=path, engine="stub")

    def make(cfg, vad_filter=False):
        built.append(vad_filter)
        return Stub()

    monkeypatch.setattr(pipeline, "_make_backend", make)
    t = pipeline.load_input(str(tmp_path), Config())
    assert built == [True]
    assert [w.text for w in t.words] == ["Hi", "there.", "Hello", "back.", "Agreed."]
    assert [w.speaker for w in t.words] == ["alice", "alice", "bob", "bob", "alice"]
    assert t.duration_sec == pytest.approx(3.5) and t.engine == "stub multitrack"

    cfg = Config()
    cfg.thresholds["group_min_words"] = 1
    res = grade_group(t, cfg)
    assert res["reports"]["alice"].transcript.audio_path == str(tmp_path / "alice.wav")
    assert res["reports"]["bob"].transcript.audio_path == str(tmp_path / "bob.wav")
    assert res["group"]["overlapping_starts"] == 0  # multitrack: measured, not n/a

    out = tmp_path / "out"
    assert cli.main([str(tmp_path), "--group", "--out-dir", str(out)]) == 0
    regraded = load_transcript_json(str(out / "merged.json"))
    assert regraded.tracks == t.tracks and len(regraded.words) == 5


# --- Review regressions -----------------------------------------------------------------

def _w(spk, n, t0, step=0.4, dur=0.3):
    return [Word(text=f"{spk}{k}", start=t0 + step * k, end=t0 + step * k + dur, speaker=spk) for k in range(n)]


def test_multitrack_interleaved_interruption_is_overlap_not_backchannels():
    from speech_grading.schema import derive_transcript_fields

    ws = sorted(_w("A", 15, 0.0) + _w("B", 5, 2.05), key=lambda w: (w.start, w.end))
    t = derive_transcript_fields(Transcript(words=ws, tracks={"A": "a.wav", "B": "b.wav"}, duration_sec=0.0))
    m = group_metrics(t, overlap=True)
    a, b = m["per_speaker"]["A"], m["per_speaker"]["B"]
    assert (a["backchannels"], b["backchannels"]) == (0, 0)
    assert (a["floor_turns"], b["floor_turns"]) == (1, 1)
    assert b["overlaps_made"] == 1 and a["overlaps_received"] == 1
    assert m["group"]["overlapping_starts"] == 1
    assert a["talk_s"] == pytest.approx(5.9) and b["talk_s"] == pytest.approx(1.9)
    assert t.filter_by_speaker("B").turn_starts == [0]
    # a long pause nobody filled stays a pause in the speaker's own turn
    solo = derive_transcript_fields(Transcript(
        words=_w("A", 3, 0.0) + _w("A", 3, 5.0), tracks={"A": "a.wav"}, duration_sec=0.0))
    assert solo.filter_by_speaker("A").turn_starts == [0]


def test_silent_track_is_reported_not_dropped():
    words = [Word(text=f"w{k}", start=0.4 * k, end=0.4 * k + 0.3, speaker="Alice") for k in range(70)]
    t = Transcript(words=words, tracks={"Alice": "a.wav", "Bob": "b.wav"})
    res = grade_group(t, Config())
    assert set(res["reports"]) == {"Alice"} and res["not_graded"] == {"Bob": 0}
    assert res["group"]["speakers"] == 2 and res["group"]["balance"] == 0
    assert res["per_speaker"]["Bob"]["words"] == 0
    silent = grade_group(Transcript(words=[], tracks={"Ann": "a.wav"}), Config())
    assert silent["not_graded"] == {"Ann": 0}


def test_report_file_names_never_collide(tmp_path):
    from speech_grading.group import report_stems

    assert report_stems(["Ana B", "Ana_B", "Alice", "alice", "group", "merged"]) == {
        "Ana B": "Ana_B", "Ana_B": "Ana_B_2", "Alice": "Alice", "alice": "alice_2",
        "group": "group_2", "merged": "merged_2"}
    words = [Word(text=f"x{k}", start=k, end=k + 0.5, speaker=("group" if k < 70 else "Group B"))
             for k in range(140)]
    src = tmp_path / "m.json"
    src.write_text(Transcript(words=words).model_dump_json(), encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main([str(src), "--group", "--out-dir", str(out)]) == 0
    summary = json.loads((out / "group.json").read_text(encoding="utf-8"))
    assert {r["speaker"]: r["file"] for r in summary["leaderboard"]} == {
        "group": "group_2.html", "Group B": "Group_B.html"}
    assert (out / "group_2.json").is_file() and "leaderboard" in summary


def test_cli_folder_without_group_is_an_error(tmp_path, capsys):
    (tmp_path / "a.wav").write_bytes(b"")
    assert cli.main([str(tmp_path)]) == 2
    assert "--group" in capsys.readouterr().err


def test_vtt_cue_numbers_and_timestamps_are_not_words():
    from speech_grading.schema import load_transcript_text

    vtt = "WEBVTT\n\nNOTE exported\n\n"
    for i in range(1, 21):
        who = "Ana Lee" if i % 2 else "Bob Ray"
        vtt += f"{i}\n00:00:{i:02d}.000 --> 00:00:{i + 1:02d}.000\n{who}: yes we can do that today\n\n"
    t = load_transcript_text(vtt)
    m = group_metrics(t, overlap=False)
    assert {s: p["words"] for s, p in m["per_speaker"].items()} == {"Ana Lee": 60, "Bob Ray": 60}
    assert not any("-->" in w.text or w.text.isdigit() for w in t.words)
