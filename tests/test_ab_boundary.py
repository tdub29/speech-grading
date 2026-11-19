from speech_grading.eval.ab_pairs import pick_midclause_boundary

T = ["Hello.", "we", "went", "to", "the", "store."]
ST = [0.0, 6.0, 6.3, 6.6, 6.8, 7.0]
EN = [0.5, 6.2, 6.5, 6.75, 6.95, 7.4]


def test_worked_example():
    assert pick_midclause_boundary(T, ST, EN, [False] * 6) == 1


def test_skips_punctuation_fillers_and_long_gaps():
    assert pick_midclause_boundary(["a,", "b", "c"], [6, 7, 7.3], [6.9, 7.2, 7.5], [False] * 3) == 1
    assert pick_midclause_boundary(T, ST, EN, [False, False, True, False, False, False]) == 3
    assert pick_midclause_boundary(["a", "b"], [6, 7], [6.5, 7.5], [False, False]) is None


def test_min_time_and_empty():
    assert pick_midclause_boundary(T, ST, EN, [False] * 6, min_time=6.5) == 3
    assert pick_midclause_boundary([], [], [], []) is None
