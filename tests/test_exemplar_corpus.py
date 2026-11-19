"""The exported corpus comparisons must preserve direction, ties and missingness."""
import importlib.util
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
