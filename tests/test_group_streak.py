"""Tests for per-speaker interruption-free floor-turn streaks in group mode."""

from speech_grading.group import interruption_free_streaks


def test_interruption_free_streaks_worked_example():
    turns = [
        ["Alice", 0.0, 10.0],
        ["Bob", 5.0, 6.0],
        ["Alice", 12.0, 20.0],
        ["Alice", 25.0, 30.0],
    ]
    assert interruption_free_streaks(turns, ["Alice", "Bob"], tol=0.2) == {
        "Alice": 2,
        "Bob": 1,
    }


def test_interruption_free_streaks_tolerance_and_silent_speaker():
    turns = [
        ["Alice", 0.0, 5.0],
        ["Bob", 4.85, 6.0],  # 4.85 + 0.2 = 5.05 >= 5.0 -> within tol, not interrupted
        ["Alice", 7.0, 12.0],
        ["Bob", 9.0, 10.0],  # interrupts Alice's second turn
    ]
    assert interruption_free_streaks(turns, ["Alice", "Bob", "Cara"], tol=0.2) == {
        "Alice": 1,
        "Bob": 2,
        "Cara": 0,
    }


def test_interruption_free_streaks_streak_resets_and_recovers():
    turns = [
        ["A", 0.0, 2.0],
        ["A", 3.0, 5.0],
        ["A", 6.0, 10.0],
        ["B", 8.0, 9.0],
        ["A", 11.0, 13.0],
        ["A", 14.0, 16.0],
        ["A", 17.0, 19.0],
    ]
    assert interruption_free_streaks(turns, ["A", "B"]) == {"A": 3, "B": 1}


def test_interruption_free_streak_in_group_metrics_and_reports(tmp_path):
    import json
    import os
    from speech_grading import cli
    from speech_grading.group import group_metrics
    from speech_grading.schema import load_transcript_json, load_transcript_text

    meeting = os.path.join(os.path.dirname(__file__), "fixtures", "meeting_3speakers.json")
    t = load_transcript_json(meeting)
    m = group_metrics(t, overlap=True)
    # Alice's first turn is overlapped by Bob; her second turn is uninterrupted -> streak 1
    assert m["per_speaker"]["Alice"]["interruption_free_streak"] == 1
    assert m["per_speaker"]["Bob"]["interruption_free_streak"] == 1
    assert m["per_speaker"]["Cara"]["interruption_free_streak"] == 1

    out = tmp_path / "out"
    assert cli.main([meeting, "--group", "--out-dir", str(out)]) == 0
    summary = json.loads((out / "group.json").read_text(encoding="utf-8"))
    assert "interruption_free_streak" in summary["definitions"]
    assert summary["per_speaker"]["Alice"]["interruption_free_streak"] == 1
    assert "interruption_free_streak" in (out / "group.html").read_text(encoding="utf-8")

    untimed = load_transcript_text("Ana: hi\nBob: ok\nAna: thanks\nBob: bye\n")
    um = group_metrics(untimed, overlap=False)
    assert um["per_speaker"]["Ana"]["interruption_free_streak"] is None
