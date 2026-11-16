"""Speaker diarization for one shared mic (stage panel, room recording).

Silero VAD (bundled with faster-whisper) finds speech, WeSpeaker ResNet34 (ONNX,
CC BY 4.0, trained on VoxCeleb) embeds 1.5 s windows, spectral clustering
groups windows by voice, and each ASR word takes the speaker of the windows it
overlaps. Overlapped speech gets one label (the dominant voice); words spoken over
each other are not split.

Model: ``~/.orator/models/wespeaker_en_voxceleb_resnet34_LM.onnx`` from the
sherpa-onnx ``speaker-recongition-models`` release.
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Optional

from .schema import Transcript

SR = 16000
WIN, HOP = 1.5, 0.75
MODEL_NAME = "wespeaker_en_voxceleb_resnet34_LM.onnx"
MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
             + MODEL_NAME)
# ponytail: one fixed cosine cut picks the speaker count; tuned on one synthetic mix, retune on a labelled set.
AUTO_THRESHOLD = 0.7


def model_path() -> str:
    p = os.path.join(os.path.expanduser("~"), ".orator", "models", MODEL_NAME)
    if not os.path.exists(p):
        raise RuntimeError(f"--diarize needs the speaker model at {p}; download it from {MODEL_URL}")
    return p


def _fbank(y):
    """Kaldi-style 80-bin log-mel fbank (25 ms / 10 ms, int16 scale), mean-normalized."""
    import librosa
    import numpy as np

    y = y * 32768.0
    frames = librosa.util.frame(np.pad(y, (0, max(0, 400 - len(y)))), frame_length=400, hop_length=160).T
    frames = frames - frames.mean(axis=1, keepdims=True)
    frames = np.concatenate([frames[:, :1], frames[:, 1:] - 0.97 * frames[:, :-1]], axis=1)
    frames = frames * np.power(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(400) / 399), 0.85)  # povey
    power = np.abs(np.fft.rfft(frames, n=512)) ** 2
    mel = librosa.filters.mel(sr=SR, n_fft=512, n_mels=80, fmin=20, fmax=SR / 2, htk=True, norm=None)
    feats = np.log(np.maximum(power @ mel.T, np.finfo(np.float32).eps))
    return (feats - feats.mean(axis=0)).astype(np.float32)


def windows(speech: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """1.5 s windows at a 0.75 s hop inside each speech region; a short region is one window."""
    out = []
    for s, e in speech:
        if e - s <= WIN:
            out.append((s, e))
            continue
        t = s
        while t + WIN < e:
            out.append((t, t + WIN))
            t += HOP
        out.append((max(s, e - WIN), e))
    return out


def cluster(emb, n_speakers: Optional[int]):
    """Spectral clustering on clipped cosine affinity into ``n_speakers`` groups.

    Unknown count: average-linkage cut at AUTO_THRESHOLD, counting only clusters
    holding at least 5% of windows (stray windows form singleton clusters).
    Fixed-count average linkage was dropped: a few stray windows formed their own
    cluster and two real voices merged to fill the count.
    """
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering, SpectralClustering

    if len(emb) < 2:
        return [0] * len(emb)
    n = n_speakers
    if not n:
        cut = AgglomerativeClustering(n_clusters=None, distance_threshold=AUTO_THRESHOLD,
                                      metric="cosine", linkage="average").fit_predict(emb)
        sizes = np.bincount(cut)
        n = max(1, int((sizes >= max(2, 0.05 * len(emb))).sum()))
    if n == 1:
        return [0] * len(emb)
    if len(emb) <= n:
        return list(range(len(emb)))
    aff = np.clip(emb @ emb.T, 0.0, 1.0)
    return list(SpectralClustering(n_clusters=n, affinity="precomputed", random_state=0).fit_predict(aff))


def assign(words, wins: list[tuple[float, float]], labels: list[int]) -> list[Optional[int]]:
    """Each word takes the cluster with the most overlap seconds; nearest window if none overlap."""
    out = []
    j0 = 0
    for w in words:
        while j0 < len(wins) and wins[j0][1] < w.start:
            j0 += 1
        ov: Counter = Counter()
        j = j0
        while j < len(wins) and wins[j][0] <= w.end:
            ov[labels[j]] += max(0.0, min(w.end, wins[j][1]) - max(w.start, wins[j][0]))
            j += 1
        if ov and max(ov.values()) > 0:
            out.append(ov.most_common(1)[0][0])
        elif wins:
            mid = (w.start + w.end) / 2
            out.append(labels[min(range(len(wins)), key=lambda k: abs((wins[k][0] + wins[k][1]) / 2 - mid))])
        else:
            out.append(None)
    return out


def diarize(t: Transcript, audio_path: str, n_speakers: Optional[int] = None,
            names: Optional[list[str]] = None) -> Transcript:
    """Label every word of ``t`` with a speaker found in ``audio_path`` (in place; returns t).

    Labels are ``names`` in order of first appearance, else ``Speaker 1..N``.
    """
    import numpy as np
    import onnxruntime as ort
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    y = decode_audio(audio_path, sampling_rate=SR)
    ts = get_speech_timestamps(y, VadOptions(min_silence_duration_ms=300, speech_pad_ms=100))
    speech = [(d["start"] / SR, d["end"] / SR) for d in ts if d["end"] - d["start"] >= 0.3 * SR]
    wins = windows(speech)
    if not wins:
        return t
    sess = ort.InferenceSession(model_path(), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    emb = np.stack([sess.run(None, {inp: _fbank(y[int(s * SR):int(e * SR)])[None]})[0][0] for s, e in wins])
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    per_word = assign(t.words, wins, cluster(emb, n_speakers))
    order: dict[int, str] = {}
    for c in per_word:
        if c is not None and c not in order:
            k = len(order)
            order[c] = names[k] if names and k < len(names) else f"Speaker {k + 1}"
    for w, c in zip(t.words, per_word):
        w.speaker = order.get(c)
    return t
