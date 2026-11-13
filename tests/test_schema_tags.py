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
