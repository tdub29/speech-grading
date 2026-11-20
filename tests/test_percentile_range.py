import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import percentile_range  # noqa: E402


def test_worked_example():
    assert percentile_range([5, 1, 4, 2, 3]) == (1.4, 4.6)


def test_edges():
    assert percentile_range([]) is None
    assert percentile_range([7.0]) == (7.0, 7.0)
    assert percentile_range([10, 20], lo=0, hi=100) == (10, 20)
    assert percentile_range([0, 10, 20, 30], lo=25, hi=75) == (7.5, 22.5)
