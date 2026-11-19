import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import effects_markdown  # noqa: E402

HEAD = "| metric | n acclaimed | n panned | median acclaimed | median panned | AUC | d |\n|---|---|---|---|---|---|---|\n"


def test_worked_example():
    e = {"wpm": {"n_acclaimed": 3, "n_panned": 2, "median_acclaimed": 140.0, "median_panned": 170.5, "auc_high": 0.2, "cohen_d": -1.234},
         "x": {"n_acclaimed": 3, "n_panned": 0, "median_acclaimed": 1.0, "median_panned": None, "auc_high": None, "cohen_d": None}}
    assert effects_markdown(e) == HEAD + "| wpm | 3 | 2 | 140.00 | 170.50 | 0.20 | -1.23 |\n"


def test_sort_and_none():
    e = {"b": {"n_acclaimed": 1, "n_panned": 1, "median_acclaimed": 1, "median_panned": 2, "auc_high": 0.6, "cohen_d": None},
         "a": {"n_acclaimed": 1, "n_panned": 1, "median_acclaimed": 1, "median_panned": 2, "auc_high": 0.4, "cohen_d": 0.5},
         "c": {"n_acclaimed": 1, "n_panned": 1, "median_acclaimed": None, "median_panned": 2, "auc_high": 0.95, "cohen_d": 2.0}}
    lines = effects_markdown(e).splitlines()
    assert [l.split(" | ")[0][2:] for l in lines[2:]] == ["c", "a", "b"]
    assert lines[2] == "| c | 1 | 1 | n/a | 2.00 | 0.95 | 2.00 |"
    assert lines[4].endswith("| 0.60 | n/a |")
    assert effects_markdown({}) == HEAD
