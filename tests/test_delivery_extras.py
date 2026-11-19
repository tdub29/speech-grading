from speech_grading.analysis.delivery_extras import (
    count_tricolons,
    mean_length_of_run,
    opening_body_contrast,
)


def test_mlr_worked_example():
    assert mean_length_of_run([0.0, 0.5, 1.0, 2.0, 2.4], [0.4, 0.9, 1.3, 2.3, 2.8]) == 2.5


def test_mlr_empty_and_no_pause():
    assert mean_length_of_run([], []) == 0.0
    assert mean_length_of_run([0.0, 0.3, 0.6], [0.25, 0.55, 0.9]) == 3.0


def test_mlr_threshold_is_inclusive_and_configurable():
    starts, ends = [0.0, 0.5, 1.0], [0.25, 0.75, 1.2]
    assert mean_length_of_run(starts, ends) == 1.0
    assert mean_length_of_run(starts, ends, min_pause=0.3) == 3.0


def test_opening_worked_example():
    out = opening_body_contrast([0, 1, 2, 3, 40, 41, 42, 43], [False, True] + [False] * 6)
    assert out == {"opening_filler_per_100": 33.33, "body_filler_per_100": 0.0, "opening_filler_delta": 33.33}


def test_opening_empty_or_no_body():
    assert opening_body_contrast([], []) == {}
    assert opening_body_contrast([0, 1, 2], [False, False, False]) == {}
    assert opening_body_contrast([0, 31], [False, True]) == {}


def test_opening_offset_and_negative_delta():
    out = opening_body_contrast([100, 101, 105, 106], [False, False, True, False], opening_sec=5)
    assert out == {"opening_filler_per_100": 0.0, "body_filler_per_100": 100.0, "opening_filler_delta": -100.0}


def test_tricolon_worked_example():
    s = ["We came, we saw, we conquered.", "I like apples, pears, and plums.",
         "Well, I think, honestly this is long, okay.", "No list here."]
    assert count_tricolons(s) == 2


def test_tricolon_or_and_item_length():
    assert count_tricolons(["Tea, coffee, or water?"]) == 1
    assert count_tricolons(["Red, green, and blue sky over the big wide sea"]) == 0
    assert count_tricolons(["Red, green, and blue sky over the big wide sea"], max_item_words=10) == 1
    assert count_tricolons(["a, b, and"]) == 0
    assert count_tricolons([]) == 0


def test_metrics_reach_report():
    from speech_grading.config import Config
    from speech_grading.scorer import score
    from speech_grading.schema import Transcript, Word, derive_transcript_fields

    words = [Word(text=x, start=i, end=i + 0.5) for i, x in enumerate("We came, we saw, we conquered.".split())]
    report = score(derive_transcript_fields(Transcript(words=words)), [], [], Config())
    assert report.metrics["tricolon_count"] == 1
    assert report.metrics["mean_length_of_run"] == 1.0
