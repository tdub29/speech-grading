"""A silence the ASR word timestamps hide still counts as a pause (analysis.silence).

faster-whisper held one word 2.56 s across a 1.5 s inserted silence, leaving every word gap 0.00 s.
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")

from speech_grading.config import Config  # noqa: E402
from speech_grading.pipeline import run_on_transcript  # noqa: E402
from speech_grading.schema import Transcript, Word, derive_transcript_fields  # noqa: E402

SR = 16000


def _tone(sec):
    x = np.arange(int(SR * sec)) / SR
    return 0.4 * np.sin(2 * np.pi * 180 * x) * (1 + 0.3 * np.sin(2 * np.pi * 4 * x))


def _clip(tmp_path):
    # speech 0 to 2.0 s, digital silence 2.0 to 3.5 s, speech 3.5 to 5.0 s
    y = np.concatenate([_tone(2.0), np.zeros(int(SR * 1.5)), _tone(1.5)]).astype("float32")
    path = tmp_path / "clip.wav"
    sf.write(path, y, SR)
    return str(path)


def _words(spec):
    return [Word(text=w, start=a, end=b) for w, a, b in spec]


# ASR words that bridge the silence: "the" is held from 1.6 s to 2.9 s, every gap 0.00 s.
BRIDGED = [("we", 0.0, 0.5), ("went", 0.5, 1.0), ("to", 1.0, 1.6), ("the", 1.6, 2.9),
           ("big", 2.9, 3.6), ("store.", 3.6, 5.0)]


def _report(path, spec, acoustic=True):
    t = derive_transcript_fields(Transcript(words=_words(spec), audio_path=path))
    return run_on_transcript(t, Config(enable_acoustic=acoustic, use_llm=False))


def _midclause(report):
    return [f for f in report.findings if f.kind == "long_pause" and "mid-clause" in (f.rationale or "")]


def test_hidden_silence_is_a_midclause_pause(tmp_path):
    found = _midclause(_report(_clip(tmp_path), BRIDGED))
    assert len(found) == 1
    f = found[0]
    assert f.start == pytest.approx(2.0, abs=0.1) and f.end == pytest.approx(3.5, abs=0.1)


def test_acoustics_off_keeps_word_gaps_only(tmp_path):
    assert _midclause(_report(_clip(tmp_path), BRIDGED, acoustic=False)) == []


def test_silence_already_a_word_gap_is_not_counted_twice(tmp_path):
    honest = [("we", 0.0, 0.5), ("went", 0.5, 1.0), ("to", 1.0, 1.6), ("the", 1.6, 2.0),
              ("big", 3.5, 3.9), ("store.", 3.9, 5.0)]
    assert len(_midclause(_report(_clip(tmp_path), honest))) == 1


def test_continuous_speech_gets_no_pause(tmp_path):
    path = tmp_path / "speech.wav"
    sf.write(path, _tone(5.0).astype("float32"), SR)
    spec = [("we", 0.0, 1.0), ("went", 1.0, 2.0), ("to", 2.0, 3.0), ("the", 3.0, 4.0), ("store.", 4.0, 5.0)]
    assert [f for f in _report(str(path), spec).findings if f.kind == "long_pause"] == []


def test_soft_speech_after_a_loud_burst_is_not_silence(tmp_path):
    # a shouted 0.5 s line then 4.5 s of speech at 1/20 the level: speech, not a pause
    y = np.concatenate([_tone(0.5) * 2.4, _tone(4.5) * 0.12]).astype("float32")
    path = tmp_path / "peaky.wav"
    sf.write(path, y, SR)
    spec = [("we", 0.0, 1.0), ("went", 1.0, 2.0), ("to", 2.0, 3.0), ("the", 3.0, 4.0), ("store.", 4.0, 5.0)]
    assert [f for f in _report(str(path), spec).findings if f.kind == "long_pause"] == []


def test_silence_after_a_held_final_word_is_a_sentence_pause(tmp_path):
    # "store." held 1.6 to 3.0 s over the silence: the pause belongs after it, at the sentence edge
    spec = [("we", 0.0, 0.5), ("went", 0.5, 1.0), ("to", 1.0, 1.3), ("the", 1.3, 1.6), ("store.", 1.6, 3.0),
            ("then", 3.5, 4.2), ("home.", 4.2, 5.0)]
    r = _report(_clip(tmp_path), spec)
    pauses = [f for f in r.findings if f.kind == "long_pause"]
    assert len(pauses) == 1 and "sentence boundary" in pauses[0].rationale


def test_speaker_filter_drops_stale_acoustic_gaps():
    t = derive_transcript_fields(Transcript(words=[Word(text="a", start=0, end=1, speaker="A"),
                                                   Word(text="b", start=1, end=2, speaker="B"),
                                                   Word(text="c", start=2, end=3, speaker="A")]))
    t.acoustic_gaps[1] = (0.5, 1.5)
    assert t.filter_by_speaker("A").acoustic_gaps == {}
