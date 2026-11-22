"""The exported corpus comparisons must preserve direction, ties and missingness."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("exemplar_corpus", Path(__file__).parents[1] / "tools/exemplar_corpus.py")
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def test_auc_direction_and_ties():
    assert corpus.auc([3, 4], [1, 2]) == 1
    assert corpus.auc([1, 2], [3, 4]) == 0
    assert corpus.auc([2], [2]) == .5
    assert corpus.auc([], [2]) is None


def test_effect_and_paired_sign_test():
    assert corpus.cohen_d([2, 4], [0, 2]) == pytest.approx(2 ** .5)
    assert corpus.cohen_d([2, 2], [1, 1]) is None
    result = corpus.paired_stats([1] * 8 + [0])
    assert result["n_pairs"] == 9
    assert result["ties"] == 1
    assert result["sign_test_p"] == pytest.approx(2 / 256)
    assert corpus.paired_stats([0, 0])["direction_agreement"] is None


def test_id_cannot_escape_corpus():
    with pytest.raises(ValueError):
        corpus.item_id({"id": "../outside"})


def _write(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_items_merges_manifests_and_applies_pair_refs(tmp_path):
    pos = _write(tmp_path, "pos.json", {"candidates": [{"id": "a", "label": "acclaimed"}, {"id": "b", "label": "acclaimed"}]})
    con = _write(tmp_path, "con.json", {"candidates": [{"id": "c", "label": "panned", "pair_id": "p1", "pair_side": "poor"}],
                                        "pair_good_refs": {"p1": "a"}})
    items = corpus.load_items([pos, con])
    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert items[0]["pair_id"] == "p1" and items[0]["pair_side"] == "good"
    assert "pair_id" not in items[1]


def test_load_items_accepts_speeches_and_list(tmp_path):
    a = _write(tmp_path, "a.json", {"speeches": [{"id": "x"}]})
    b = _write(tmp_path, "b.json", [{"id": "y"}])
    assert [i["id"] for i in corpus.load_items([a, b])] == ["x", "y"]


def test_load_items_rejects_duplicate_ids_and_dangling_refs(tmp_path):
    a = _write(tmp_path, "a.json", [{"id": "x"}])
    with pytest.raises(ValueError):
        corpus.load_items([a, a])
    d = _write(tmp_path, "d.json", {"candidates": [{"id": "y"}], "pair_good_refs": {"p": "missing"}})
    with pytest.raises(ValueError):
        corpus.load_items([d])


def test_assert_committed_refuses_uncommitted_labels(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    m = repo / "m.json"
    m.write_bytes(b'[{"id": "x"}]\n')
    git("add", "m.json")
    git("commit", "-qm", "labels")
    corpus.assert_committed(m)
    m.write_bytes(b'[{"id": "x"}]\r\n')  # a CRLF checkout of the same labels still passes
    corpus.assert_committed(m)
    m.write_bytes(b'[{"id": "x"}, {"id": "y"}]\n')
    with pytest.raises(RuntimeError):
        corpus.assert_committed(m)
    outside = tmp_path / "o.json"
    outside.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError):
        corpus.assert_committed(outside)


# --- 2026-11-21 model change orator-pace-pause: medium + English ASR, excerpt bounds, R5 asserts ---

class _CountingBackend:
    def __init__(self):
        self.calls = 0

    def transcribe(self, path):
        from speech_grading.schema import Transcript, Word
        self.calls += 1
        words = [Word(text=w, start=i * .5, end=i * .5 + .4, confidence=.9, normalized=w)
                 for i, w in enumerate(["we", "choose", "to", "go"])]
        return Transcript(words=words, audio_path=path, engine="faster-whisper")


def _corpus_root(tmp_path, monkeypatch, audio=b"RIFF-one"):
    monkeypatch.setattr(corpus, "ROOT", tmp_path)
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "x1.wav").write_bytes(audio)
    backend = _CountingBackend()
    monkeypatch.setattr(corpus._THREAD, "backend", backend, raising=False)
    return backend


def test_cached_transcript_reused_only_with_matching_provenance(tmp_path, monkeypatch):
    backend = _corpus_root(tmp_path, monkeypatch)
    item = {"id": "x1"}
    _, provenance = corpus.transcribe(item)
    assert provenance["model"] == "medium" and provenance["language"] == "en"
    corpus.transcribe(item)
    assert backend.calls == 1  # same audio bytes and ASR config: cache hit
    (tmp_path / "audio" / "x1.wav").write_bytes(b"RIFF-two")
    corpus.transcribe(item)
    assert backend.calls == 2  # re-cut excerpt: new sha256, re-transcribed
    stale = json.loads((tmp_path / "transcripts" / "x1.asr.json").read_text(encoding="utf-8"))
    stale["model"] = "small"
    (tmp_path / "transcripts" / "x1.asr.json").write_text(json.dumps(stale), encoding="utf-8")
    corpus.transcribe(item)
    assert backend.calls == 3  # a small-model transcript is never reused under medium
    (tmp_path / "transcripts" / "x1.asr.json").unlink()
    corpus.transcribe(item)
    assert backend.calls == 4  # no provenance, no reuse


def test_grade_refuses_items_without_a_passing_content_check(tmp_path, monkeypatch):
    backend = _corpus_root(tmp_path, monkeypatch)
    for check in (None, {"result": "fail", "reason": "commentator"}, {"result": "pending"}):
        item = {"id": "x1", "mode": "stage"} | ({"content_check": check} if check else {})
        with pytest.raises(ValueError, match="content check"):
            corpus.grade(item)
    assert backend.calls == 0 and not (tmp_path / "grades").exists()


def test_acquire_recuts_excerpt_when_bounds_change(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf
    from speech_grading.pipeline import find_ffmpeg
    if not find_ffmpeg():
        pytest.skip("ffmpeg unavailable")
    source = tmp_path / "src"
    source.mkdir()
    sf.write(source / "x1.wav", np.zeros(16000 * 4, dtype="float32"), 16000)
    monkeypatch.setattr(corpus, "ROOT", tmp_path / "root")
    monkeypatch.setattr(corpus, "FROM_AUDIO", source)
    assert corpus.acquire({"id": "x1", "source_url": "local", "start_sec": 1, "end_sec": 2})["status"] == "acquired"
    assert sf.info(tmp_path / "root/audio/x1.wav").duration == pytest.approx(1, abs=.01)
    assert corpus.acquire({"id": "x1", "source_url": "local", "start_sec": 1, "end_sec": 2})["status"] == "cached"
    assert corpus.acquire({"id": "x1", "source_url": "local", "start_sec": .5, "end_sec": 3})["status"] == "acquired"
    assert sf.info(tmp_path / "root/audio/x1.wav").duration == pytest.approx(2.5, abs=.01)


def _person(key, speaker, date, url):
    return {"id": key, "speaker": speaker, "date": date, "source_url": url}


def test_heldout_must_be_disjoint_from_development_and_political_corpus():
    assert corpus.surname("Martin Luther King Jr.") == "king"
    dev = [_person("e_a", "Ann Lee", "2010-05-01", "u/a")]
    political = {"u/p"}
    clean = _person("h_b", "Bo Diaz", "2015-01-01", "u/b")
    corpus.assert_heldout_disjoint(dev, [clean], {"e_a": "aa", "h_b": "bb"}, political)
    bad = {
        "id": clean | {"id": "e_a"},
        "audio sha256": clean,
        "source url": clean | {"source_url": "u/p"},
        "speaker": clean | {"speaker": "Carl Lee"},
        "event": clean | {"speaker": "Barack Obama", "date": "2004-07-27"},
    }
    for reason, item in bad.items():
        sha = {"e_a": "aa", item["id"]: "aa" if reason == "audio sha256" else "cc"}
        with pytest.raises(ValueError, match=reason):
            corpus.assert_heldout_disjoint(dev, [item], sha, political)


def test_one_insertion_event_per_heldout_source():
    corpus.assert_one_insertion_per_source([{"source_id": "a"}, {"source_id": "b"}])
    with pytest.raises(ValueError):
        corpus.assert_one_insertion_per_source([{"source_id": "a"}, {"source_id": "a"}])


def test_stale_or_unchecked_grades_are_regraded_and_kept_out_of_summary(tmp_path, monkeypatch):
    _corpus_root(tmp_path, monkeypatch)
    (tmp_path / "grades").mkdir()
    stale = {"metadata": {"corpus_asr_provenance": {"model": "small"}}, "metrics": {"wpm": 150}}
    (tmp_path / "grades" / "x1.json").write_text(json.dumps(stale), encoding="utf-8")
    base = {"id": "x1", "speaker": "s", "label": "acclaimed", "genre": "g"}
    with pytest.raises(ValueError, match="content check"):
        corpus.grade(base | {"content_check": {"result": "fail"}})  # cached file no longer bypasses the gate
    passing = base | {"content_check": {"result": "pass"}}
    assert not corpus.grade_is_current(passing, stale)
    assert not corpus.grade_is_current(base, stale)
    current = {"metadata": {"corpus_asr_provenance": corpus.asr_provenance(tmp_path / "audio" / "x1.wav")},
               "overall_score": 70, "metrics": {}, "dimensions": []}
    assert corpus.grade_is_current(passing, current)
    assert not corpus.grade_is_current(base | {"content_check": {"result": "pending"}}, current)
    rows = corpus.summarize([passing])["rows"]
    assert rows == []  # stale small-ASR grade never reaches the effects table
    (tmp_path / "grades" / "x1.json").write_text(json.dumps(current), encoding="utf-8")
    assert len(corpus.summarize([passing])["rows"]) == 1
    assert corpus.summarize([base | {"content_check": {"result": "fail"}}])["rows"] == []
