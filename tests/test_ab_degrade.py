import importlib.util
from pathlib import Path

import pytest

from speech_grading.eval.ab_pairs import degradation_verdict

_spec = importlib.util.spec_from_file_location("ab_degrade", Path(__file__).resolve().parents[1] / "tools" / "ab_degrade.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)


def test_jitter_below_min_rel_does_not_count_as_moved():
    assert degradation_verdict({"wpm": 150}, {"wpm": 149}, "wpm", "down")["moved_as_expected"]  # old default kept
    assert not degradation_verdict({"wpm": 150}, {"wpm": 149}, "wpm", "down", min_rel=0.05)["moved_as_expected"]
    assert degradation_verdict({"wpm": 150}, {"wpm": 120}, "wpm", "down", min_rel=0.05)["moved_as_expected"]
    assert degradation_verdict({"midclause_pauses": 0}, {"midclause_pauses": 1}, "midclause_pauses", "up",
                               min_rel=0.05)["moved_as_expected"]  # count from zero: one is enough


def test_cached_clips_at_another_window_are_refused():
    ab.check_manifest_window({"source_start_sec": 60.0, "source_end_sec": 180.0}, 60.0, 180.0)
    with pytest.raises(ValueError, match="delete the clip dir"):
        ab.check_manifest_window({"source_start_sec": 30.0, "source_end_sec": 150.0}, 60.0, 180.0)


def test_partial_rerun_keeps_other_clips_and_aggregates():
    row = {"transform": "pace_0.8x", "target": "wpm", "overall_delta": 0.0, "collateral": []}
    old = [row | {"clip": "a", "moved_as_expected": True, "baseline": 100, "edited": 80},
           row | {"clip": "b", "moved_as_expected": False, "baseline": 100, "edited": 101}]
    new = [{"clip": "b", "error": "boom"}]
    merged = ab.merge_rows(old, new, ["b"])
    assert merged == [old[0], new[0]]
    assert ab.aggregate(old) == [{"transform": "pace_0.8x", "moved": 1, "n": 2, "median_rel_change": -0.095}]
    assert "ERROR: boom" in ab.markdown(merged) and "1/1" in ab.markdown(merged)
