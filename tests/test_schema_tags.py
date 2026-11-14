from speech_grading.schema import Transcript, Word, derive_transcript_fields


def _t(*texts):
    return Transcript(words=[Word(text=x, start=i, end=i + 0.5) for i, x in enumerate(texts)], has_timing=True)


def test_sound_event_captions_are_not_words():
    t = derive_transcript_fields(_t("MUSIC", "Thank", "you.", "CHEERING", "AND", "APPLAUSE", "[Applause]", "We", "love", "music."))
    assert [w.text for w in t.words] == ["Thank", "you.", "We", "love", "music."]


def test_caps_speech_without_tag_word_is_kept_and_turns_shift():
    t = _t("USA!", "USA!", "MUSIC", "Thank", "you")
    t.turn_starts = [0, 3]
    t = derive_transcript_fields(t)
    assert [w.text for w in t.words] == ["USA!", "USA!", "Thank", "you"]
    assert t.turn_starts == [0, 2]


def test_low_confidence_interjection_run_is_crowd_noise():
    def w(x, i, c):
        return Word(text=x, start=i, end=i + 0.3, confidence=c)
    crowd = [w("Oh!", i, 0.2) for i in range(4)] + [w("Thank", 5, 0.9), w("you.", 6, 0.9)]
    assert [x.text for x in derive_transcript_fields(Transcript(words=crowd, has_timing=True)).words] == ["Thank", "you."]
    speech = [w("Oh,", 0, 0.2), w("no,", 1, 0.3), w("no,", 2, 0.3), w("no.", 3, 0.3), w("Oh!", 4, 0.9), w("Oh!", 5, 0.9), w("Oh!", 6, 0.9)]
    assert len(derive_transcript_fields(Transcript(words=speech, has_timing=True)).words) == 7


def test_bracketed_filler_is_speech_not_a_caption():
    ws = [Word(text="I", start=0, end=0.2), Word(text="[UM]", start=0.3, end=0.6, is_filled_pause=True),
          Word(text="think", start=0.7, end=1.0)]
    assert [w.text for w in derive_transcript_fields(Transcript(words=ws, has_timing=True)).words] == ["I", "[UM]", "think"]


def test_derive_is_idempotent_when_crowd_runs_merge():
    texts = ["Oh!", "Oh!", "yeah", "yeah", "yeah", "Oh!", "Thank"]
    ws = [Word(text=x, start=i, end=i + 0.3, confidence=0.9 if x == "Thank" else 0.2) for i, x in enumerate(texts)]
    once = derive_transcript_fields(Transcript(words=ws, has_timing=True))
    twice = derive_transcript_fields(once.model_copy(deep=True))
    assert [w.text for w in once.words] == [w.text for w in twice.words] == ["Thank"]
