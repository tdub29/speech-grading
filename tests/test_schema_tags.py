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
