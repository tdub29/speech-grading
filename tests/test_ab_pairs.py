"""Real signal checks; all temporary audio stays under the local exemplar root."""

import json
from pathlib import Path
import shutil
import tempfile

import pytest

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
parselmouth = pytest.importorskip("parselmouth")

from speech_grading.eval import ab_pairs


@pytest.fixture
def signal():
    sr = 16000
    t = np.arange(sr * 4) / sr
    phase = 2 * np.pi * (130 * t + 8 * t * t)
    y = .25 * np.sin(phase) + .05 * np.sin(2 * phase)
    return y, sr


@pytest.fixture
def local_dir():
    ab_pairs.CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ab-test-", dir=ab_pairs.CORPUS_ROOT) as directory:
        yield Path(directory)


def _pitch(y, sr):
    hz = parselmouth.Sound(y, sampling_frequency=sr).to_pitch(
        pitch_floor=50, pitch_ceiling=800).selected_array["frequency"]
    hz = hz[hz > 0]
    return np.median(hz), np.std(12 * np.log2(hz / np.median(hz)))


@pytest.mark.parametrize("rate", [.8, 1.25])
def test_pace_duration_changes_with_pitch_preserved(signal, rate):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    y, sr = signal
    edited = ab_pairs.time_stretch(y, sr, rate)
    assert len(edited) / len(y) == pytest.approx(1 / rate, rel=.025)
    assert _pitch(edited, sr)[0] == pytest.approx(_pitch(y, sr)[0], rel=.03)


def test_pitch_flattening_changes_range_preserves_duration(signal):
    y, sr = signal
    edited = ab_pairs.flatten_pitch(y, sr)
    original_median, original_sd = _pitch(y, sr)
    median, sd = _pitch(edited, sr)
    assert len(edited) == len(y)
    assert sd < original_sd * .1
    assert median == pytest.approx(original_median, rel=.03)


def test_compression_reduces_level_variation_without_retiming():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    sr = 16000
    t = np.arange(sr * 4) / sr
    amplitudes = np.repeat([.05, .7, .05, .7], sr)
    y = amplitudes * np.sin(2 * np.pi * 180 * t)
    edited = ab_pairs.compress_dynamic_range(y, sr)
    def level_cv(samples):
        rms = [np.sqrt(np.mean(samples[i * sr + 2000:(i + 1) * sr - 2000] ** 2))
               for i in range(4)]
        return np.std(rms) / np.mean(rms)
    assert len(edited) == len(y)
    assert level_cv(edited) < level_cv(y) * .5
    assert _pitch(edited, sr)[0] == pytest.approx(180, abs=2)


def test_silence_and_same_recording_segment_insert_exactly(signal):
    y, sr = signal
    silence = np.zeros(sr // 2)
    edited = ab_pairs.insert_audio(y, sr, 1, silence)
    np.testing.assert_array_equal(edited[:sr], y[:sr])
    np.testing.assert_array_equal(edited[sr:sr + len(silence)], silence)
    np.testing.assert_array_equal(edited[sr + len(silence):], y[sr:])
    filler = y[:sr // 4]
    edited = ab_pairs.insert_audio(y, sr, 1, filler)
    np.testing.assert_array_equal(edited[sr:sr + len(filler)], filler)
    np.testing.assert_array_equal(edited[sr + len(filler):], y[sr:])


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), 3])
def test_invalid_pace_rejected(signal, rate):
    with pytest.raises(ValueError, match="Rate"):
        ab_pairs.time_stretch(*signal, rate)


def test_guards_reject_escape_bad_samples_and_unvoiced_pitch(signal, local_dir):
    with pytest.raises(ValueError, match="beneath"):
        ab_pairs._within_corpus(local_dir / ".." / ".." / "escape")
    with pytest.raises(ValueError, match="beneath"):
        ab_pairs._within_corpus(ab_pairs.CORPUS_ROOT)
    with pytest.raises(ValueError, match="finite"):
        ab_pairs.insert_audio(np.array([np.nan]), 16000, .1, [0])
    with pytest.raises(ValueError, match="inside"):
        ab_pairs.insert_audio(*signal, 0, [0])
    with pytest.raises(ValueError, match="voiced"):
        ab_pairs.flatten_pitch(np.zeros(16000), 16000)


def test_manifest_records_source_spans_and_all_single_factor_edits(signal, local_dir):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg unavailable")
    y, sr = signal
    source = local_dir / "source.wav"
    sf.write(source, y, sr, subtype="PCM_16")
    options = dict(start=.5, end=3.5, after_word_end=1.2, before_word_start=1.3,
                   speaker="synthetic test", mid_clause=True, filler_source=source,
                   filler_start=0, filler_end=.2, filler_speaker="synthetic test")
    output = local_dir / "pairs"
    manifest = ab_pairs.make_pairs(source, output, **options)
    assert len(manifest["outputs"]) == 7
    assert manifest["source_start_sec"] == .5
    assert manifest["boundary"]["after_word_end_sec"] == 1.2
    assert manifest["skipped"] == []
    assert json.loads((output / "manifest.json").read_text()) == manifest
    for entry in manifest["outputs"]:
        assert Path(entry["path"]).is_relative_to(ab_pairs.CORPUS_ROOT)
        assert len(entry["sha256"]) == 64
    with pytest.raises(FileExistsError):
        ab_pairs.make_pairs(source, output, **options)
    options["filler_speaker"] = "different speaker"
    with pytest.raises(ValueError, match="match"):
        ab_pairs.make_pairs(source, local_dir / "wrong-speaker", **options)
    assert not (local_dir / "wrong-speaker").exists()
