import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import wilcoxon_exact_p  # noqa: E402


def test_worked_example():
    assert wilcoxon_exact_p([1, 2, 3]) == 0.25


def test_mixed_signs():
    assert wilcoxon_exact_p([1, -2, 3, 4, 5]) == 0.1875
    assert wilcoxon_exact_p([-1, -2, -3]) == 0.25


def test_ties_zeros_empty():
    assert wilcoxon_exact_p([1, 1, -2]) == 1.0
    assert wilcoxon_exact_p([0, 0]) == 1.0
    assert wilcoxon_exact_p([]) == 1.0
    assert wilcoxon_exact_p([0, 2.5, 2.5, 2.5]) == 0.25
