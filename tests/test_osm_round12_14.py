import sys
from pathlib import Path

from speech_grading.analysis.delivery_extras import mid_clause_pause_share
from speech_grading.eval.ab_pairs import degradation_verdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import paired_markdown  # noqa: E402


def test_midclause_example():
    assert mid_clause_pause_share([0.1, 0.5, 0.3, 0.8], [False, True, False, False]) == 0.667


def test_midclause_none_and_threshold():
    assert mid_clause_pause_share([0.1, 0.2], [False, False]) is None
    assert mid_clause_pause_share([], []) is None
    assert mid_clause_pause_share([0.25, 0.4], [True, True]) == 0.0
    assert mid_clause_pause_share([0.3, 0.6], [False, True], min_pause=0.5) == 0.0


def test_verdict_example():
    b = {"wpm": 150, "pitch": 4.0, "fillers": 2, "name": "x"}
    e = {"wpm": 120, "pitch": 3.0, "fillers": 2, "name": "y"}
    assert degradation_verdict(b, e, "wpm", "down") == {
        "target": "wpm", "baseline": 150, "edited": 120, "moved_as_expected": True, "collateral": ["pitch"]}


def test_verdict_up_zero_bool_missing():
    b = {"pauses": 3, "z": 0, "flag": True, "a": 10.0, "only_b": 1}
    e = {"pauses": 3, "z": 5, "flag": False, "a": 10.5, "only_e": 9}
    v = degradation_verdict(b, e, "pauses", "up", tol=0.04)
    assert v["moved_as_expected"] is False
    assert v["collateral"] == ["a"]


HEAD = "| metric | pairs | good higher | good lower | ties | agreement | sign p |\n|---|---|---|---|---|---|---|\n"


def test_paired_example():
    p = {"wpm": {"n_pairs": 8, "wins": 7, "losses": 1, "ties": 0, "direction_agreement": 0.875, "sign_test_p": 0.0703125},
         "x": {"n_pairs": 0, "wins": 0, "losses": 0, "ties": 0, "direction_agreement": None, "sign_test_p": 1.0}}
    assert paired_markdown(p) == HEAD + "| wpm | 8 | 7 | 1 | 0 | 0.88 | 0.070 |\n"


def test_paired_sort():
    def row(p):
        return {"n_pairs": 2, "wins": 1, "losses": 1, "ties": 0, "direction_agreement": 0.5, "sign_test_p": p}
    out = paired_markdown({"b": row(0.5), "a": row(0.5), "c": row(0.1)}).splitlines()
    assert [line.split(" | ")[0][2:] for line in out[2:]] == ["c", "a", "b"]
    assert paired_markdown({}) == HEAD
