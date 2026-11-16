import numpy as np

from speech_grading.cli import main
from speech_grading.diarize import assign, cluster, windows
from speech_grading.schema import Word


def test_windows_cover_regions():
    w = windows([(0.0, 1.0), (2.0, 5.0)])
    assert w[0] == (0.0, 1.0)
    assert w[1] == (2.0, 3.5) and w[-1] == (3.5, 5.0)
    assert all(b - a <= 1.5 + 1e-9 for a, b in w)


def test_assign_by_overlap_and_nearest():
    words = [Word(text="a", start=0.1, end=0.4), Word(text="b", start=1.6, end=1.9),
             Word(text="c", start=9.0, end=9.2)]
    wins, labels = [(0.0, 1.0), (1.5, 2.5)], [0, 1]
    assert assign(words, wins, labels) == [0, 1, 1]  # c overlaps nothing: nearest window


def test_cluster_separates_two_voices():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=256), rng.normal(size=256)
    emb = np.stack([a + 0.05 * rng.normal(size=256) for _ in range(4)]
                   + [b + 0.05 * rng.normal(size=256) for _ in range(4)])
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    for n in (2, None):
        lab = cluster(emb, n)
        assert len(set(lab[:4])) == 1 and len(set(lab[4:])) == 1 and lab[0] != lab[4]


def test_cli_rejects_bad_diarize_use(tmp_path):
    f = tmp_path / "t.json"
    f.write_text("{}")
    assert main([str(f), "--diarize", "--group"]) == 2
    assert main(["x.wav", "--diarize"]) == 2
    assert main(["x.wav", "--speakers", "3", "--group"]) == 2
