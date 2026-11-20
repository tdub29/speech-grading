import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from exemplar_corpus import auc_within_mode  # noqa: E402


def row(label, mode, **m):
    return {"label": label, "mode": mode, "metrics": m}


ROWS = [row("acclaimed", "stage", wpm=150), row("acclaimed", "stage", wpm=120),
        row("panned", "stage", wpm=130), row("panned", "default", wpm=200)]


def test_worked_example():
    assert auc_within_mode(ROWS, "wpm", "stage") == 0.5


def test_ties_missing_and_empty():
    rows = [row("acclaimed", "stage", x=1), row("acclaimed", "stage", x=3), row("acclaimed", "stage"),
            row("panned", "stage", x=1), row("panned", "stage", x=2), row("panned", "stage", x=2)]
    assert auc_within_mode(rows, "x", "stage") == 0.583
    assert auc_within_mode(ROWS, "wpm", "default") is None
    assert auc_within_mode(ROWS, "nope", "stage") is None
    assert auc_within_mode([], "wpm", "stage") is None
