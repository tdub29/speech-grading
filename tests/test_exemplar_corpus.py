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
