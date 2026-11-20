import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import add_rate_metrics  # noqa: E402


def test_worked_example():
    m = {"speaking_sec": 120, "total_words": 250, "long_pauses": 6, "tricolon_count": 1, "wpm": 125}
    out = add_rate_metrics(m)
    assert out == {**m, "long_pauses_per_min": 3.0, "tricolon_count_per_1000w": 4.0}
    assert "long_pauses_per_min" not in m


def test_zero_denominators_and_all_names():
    assert add_rate_metrics({"long_pauses": 3, "anaphora_count": 2}) == {"long_pauses": 3, "anaphora_count": 2}
    out = add_rate_metrics({"speaking_sec": 90, "total_words": 3000, "midclause_pauses": 4, "repetitions": 3,
                            "anaphora_count": 3, "question_count": 9})
    assert out["midclause_pauses_per_min"] == 2.667
    assert out["repetitions_per_min"] == 2.0
    assert out["anaphora_count_per_1000w"] == 1.0
    assert out["question_count_per_1000w"] == 3.0
