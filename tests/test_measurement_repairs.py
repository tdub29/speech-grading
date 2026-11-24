"""Failing-first tests for the measurement repairs D1 to D5 (model record orator-pace-pause-2026-11-20,
component D). Drafted by OSM at the Frame stage, two coordinator fixes marked FIX."""
from speech_grading.schema import Word, Transcript, derive_transcript_fields
from speech_grading.analysis.pace import compute_pace
from speech_grading.analysis.pauses import detect_pauses
from speech_grading.analysis.fillers import detect_fillers
from speech_grading.scorer import _pauses_dim
from speech_grading.config import DEFAULT_THRESHOLDS as TH, Config
from speech_grading.wordchoice.offline import OfflineWordChoice
import speech_grading.analysis.delivery_extras as dx

def mk(spec, speakers=None, conf=None):
    ws = []; t = 0.0
    for k, (txt, gap) in enumerate(spec):
        t += gap
        ws.append(Word(text=txt, start=t, end=t+0.3, speaker=(speakers[k] if speakers else None), confidence=conf))
        t += 0.3
    return derive_transcript_fields(Transcript(words=ws))

G = 60/140 - 0.3   # gap that gives steady 140 wpm
def steady(n=140): return [("word.", G) if i%10==9 else ("word", G) for i in range(n)]

def test_applause_gap_does_not_break_consistency():
    s = steady(); s2 = list(s); s2[70] = ("word", 8.0)
    a = compute_pace(mk(s), TH); b = compute_pace(mk(s2), TH)
    assert b.detail["consistency"] < TH["wpm_consistency_full"] and b.points == a.points

def test_one_word_turn_is_not_a_window():
    # FIX (coordinator): OSM draft built 82 speaker labels for 84 words and 2 rounds; restored the spec's 6 rounds.
    spec, speakers = [], []
    for _ in range(6):
        spec += [("word", G)] * 40 + [("other", 0.2), ("Yes.", 0.2), ("other", 0.2)]
        speakers += ["A"] * 40 + ["B", "A", "B"]
    t = mk(spec, speakers).filter_by_speaker("A")
    p = compute_pace(t, TH)
    assert p.detail["consistency"] < TH["wpm_consistency_full"]

def test_gaps_around_filler_not_midclause():
    t = mk([("We", 0), ("cut", G), ("the", G), ("um", 0.9), ("budget", 0.9), ("today.", G)] + [("word", G)] * 120)
    fp = detect_pauses(t, TH); d = _pauses_dim(fp, t).detail
    assert d["midclause_pauses"] == 0 and len(detect_fillers(t, TH)) == 1

def test_plain_midclause_still_flagged():
    t = mk([("We", 0), ("cut", G), ("the", G), ("budget", 0.9), ("today.", G)] + [("word", G)] * 120)
    assert _pauses_dim(detect_pauses(t, TH), t).detail["midclause_pauses"] == 1

def test_offline_reads_cfg_min_score():
    t = mk(steady(30)); th = dict(TH); th["tripped_up_min_score"] = 0.0
    out = OfflineWordChoice(Config(thresholds=th)).analyze(t)
    assert len(out) > 0

def test_offline_reads_cfg_low_conf():
    # FIX (coordinator): spec 6 passed on the buggy code (low_conf 0.16 < default min 0.45); weights isolate low_conf.
    t = mk(steady(30), conf=0.1); th = dict(TH); th["low_conf_threshold"] = 0.05; th["tripped_up_weights"] = {"low_conf": 1.0}
    assert len(OfflineWordChoice(Config(thresholds=th)).analyze(t)) == 0

def test_dead_mid_clause_share_removed():
    assert not hasattr(dx, "mid_clause_pause_share")


# Boundary and edge tests added at the Data stage (coordinator-written, run red before the fix).
from speech_grading.analysis.pace import _window_wpms


def _tx(spec):
    # ASR marks filled pauses (is_filled_pause); the fixture does the same for "um".
    return derive_transcript_fields(Transcript(words=[Word(text=x, start=a, end=b, is_filled_pause=x == "um") for x, a, b in spec]))


def _run(n, t0, step=0.5, dur=0.25, txt="word"):
    return [(txt, t0 + k * step, t0 + k * step + dur) for k in range(n)]


def test_gap_exactly_cap_does_not_split_but_just_over_does():
    a = _run(20, 0.0)                                  # last end 9.75
    at_cap = _window_wpms(_tx(a + _run(20, 11.75)), 10.0)   # gap 2.0 s: one piece
    over = _window_wpms(_tx(a + _run(20, 11.76)), 10.0)     # gap 2.01 s: two pieces
    assert [round(x, 2) for x in at_cap] == [120.0, 104.35]
    assert [round(x, 2) for x in over] == [123.08, 123.08]


def test_short_or_sparse_piece_gives_no_window():
    main = _run(40, 0.0)                               # 0 to 19.75 s: two windows
    assert len(_window_wpms(_tx(main), 10.0)) == 2
    stray = [("word", 30.0, 30.25), ("word", 31.0, 31.25), ("word", 36.0, 36.25)]  # 2-word and 1-word pieces
    assert len(_window_wpms(_tx(main + stray), 10.0)) == 2
    fill = [("word", 30.0, 30.25), ("um", 31.5, 31.75), ("um", 33.0, 33.25), ("word", 34.75, 35.25)]
    assert len(_window_wpms(_tx(main + fill), 10.0)) == 2   # 5.25 s span but 2 lexical words
    lex = [("word", 30.0, 30.25), ("word", 31.5, 31.75), ("word", 33.0, 33.25), ("word", 34.75, 35.25)]
    assert len(_window_wpms(_tx(main + lex), 10.0)) == 3    # 5.25 s span, 4 lexical words: kept


def test_held_word_overhang_counts_as_gap():
    # Applause hung on a word's end (12 s "and"); speech resumes 0.2 s after the raw end. The
    # word-capped end makes that an 11.95 s gap, so no window spans the hold.
    a = _run(29, 0.0) + [("and", 14.5, 26.5)]
    t = _tx(a + _run(30, 26.7))
    assert [round(x, 1) for x in _window_wpms(t, 10.0)] == [122.0, 122.0]   # one 14.75 s window per piece
    assert compute_pace(t, TH).detail["consistency"] < TH["wpm_consistency_full"]


def test_normalized_filler_also_skipped():
    t = mk([("We", 0), ("cut", G), ("the", G), ("uh,", 0.9), ("budget", 0.9), ("today.", G)] + [("word", G)] * 120)
    assert _pauses_dim(detect_pauses(t, TH), t).detail["midclause_pauses"] == 0
