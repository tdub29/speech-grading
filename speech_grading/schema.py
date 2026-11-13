"""Canonical data schemas for orator.

Every analysis module consumes a :class:`Transcript` (a list of :class:`Word`
objects with timing + confidence) and emits :class:`Finding` / :class:`DimensionScore`
objects. Because the whole analysis layer operates on these in-memory models, it is
fully testable from a JSON fixture with **no ASR model and no network**.

All models are Pydantic v2 so they (de)serialize to JSON cleanly. ``WordChoiceFinding``
is deliberately constrained to satisfy Anthropic structured-output limits
(``additionalProperties: false``, an enum field, no numeric/string constraints).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

_PUNCT_STRIP = re.compile(r"^[^\w']+|[^\w']+$")


def normalize_token(text: str) -> str:
    """Lowercase + strip leading/trailing punctuation, keeping internal ' and -.

    Engine filler tokens like ``[UM]`` normalize to ``um``.
    """
    t = text.strip().lower()
    t = t.strip("[]")
    t = _PUNCT_STRIP.sub("", t)
    return t


class Word(BaseModel):
    """One recognized token with timing and confidence: the atomic analysis unit."""

    text: str
    start: float
    end: float
    confidence: Optional[float] = None
    is_filled_pause: bool = False
    normalized: str = ""
    speaker: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class Transcript(BaseModel):
    """Canonical in-memory representation of one speech sample."""

    words: list[Word] = Field(default_factory=list)
    audio_path: Optional[str] = None
    sample_rate: Optional[int] = None
    duration_sec: float = 0.0
    speaking_sec: float = 0.0
    language: str = "en"
    engine: str = "fixture"
    has_timing: bool = True  # False for text-only transcripts (no word timestamps)
    speaker_median_gap: float = 0.0
    sentences: list[tuple[int, int]] = Field(default_factory=list)
    # Word indices that open a new turn after another speaker talked (set by filter_by_speaker).
    # gap_before() reads 0 there, so the other speaker's turn never scores as a pause.
    turn_starts: list[int] = Field(default_factory=list)

    @property
    def total_words(self) -> int:
        """Count of real lexical tokens (excludes explicit filled-pause tokens)."""
        return sum(1 for w in self.words if not w.is_filled_pause)

    @property
    def minutes(self) -> float:
        return self.duration_sec / 60.0 if self.duration_sec else 0.0

    def gap_before(self, i: int) -> float:
        """Silent gap (seconds) immediately before word ``i`` (0 for the first word)."""
        if i <= 0 or i >= len(self.words) or i in self.turn_starts:
            return 0.0
        return max(0.0, self.words[i].start - self.words[i - 1].end)

    def filter_by_speaker(self, speaker: str) -> Transcript:
        """Return a new Transcript containing only words for the given speaker."""
        available = {w.speaker for w in self.words if w.speaker is not None}
        if not available:
            raise ValueError(f"Speaker {speaker!r} requested, but transcript has no speaker labels.")
        want = speaker if any(w.speaker == speaker for w in self.words) else None
        if want is None:
            want = next((a for a in available if a.lower() == speaker.lower()), None)
        if want is None:
            sorted_avail = ", ".join(sorted(available))
            raise ValueError(f"Speaker {speaker!r} not found in transcript. Available speakers: {sorted_avail}")
        if self.turn_starts and all(w.speaker == want for w in self.words):
            return self  # already filtered: re-filtering would erase turn boundaries
        matching, turns, prev_mine = [], [], False
        for w in self.words:
            mine = w.speaker == want
            if mine:
                if not prev_mine:
                    turns.append(len(matching))
                matching.append(w)
            prev_mine = mine
        filtered = self.model_copy(deep=True)
        filtered.words = [w.model_copy() for w in matching]
        filtered.turn_starts = turns  # includes 0: marks the transcript as speaker-filtered
        # Pace counts only this speaker's turns, not the wall clock spent listening.
        bounds = turns + [len(matching)]
        filtered.duration_sec = round(sum(
            matching[b - 1].end - matching[a].start for a, b in zip(bounds, bounds[1:])), 4) or 0.0
        filtered.sentences = []
        return derive_transcript_fields(filtered)


class Finding(BaseModel):
    """One flagged item from any analysis module. Uniform shape so the report
    renderer and scorer treat every module identically."""

    kind: str  # filler|hedge|weasel|intensifier|repetition|false_start|long_pause|tripped_up|weak_word
    word_index: int
    span: Optional[tuple[int, int]] = None
    start: float = 0.0
    end: float = 0.0
    original: str = ""
    suggestion: Optional[str] = None
    rationale: str = ""
    score: float = 1.0
    source: str = "rule"  # lexicon|rule|acoustic|llm

    def resolved_span(self) -> tuple[int, int]:
        return self.span if self.span is not None else (self.word_index, self.word_index)


class DimensionScore(BaseModel):
    """Score for one rubric dimension with its supporting evidence."""

    dimension: str
    raw: float = 0.0
    band: str = "good"  # excellent|good|fair|poor
    points: float = 0.0  # 0-100 sub-score
    weight: float = 0.0
    findings: list[Finding] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class Report(BaseModel):
    """Top-level graded result; serializes to JSON and drives the HTML renderer."""

    overall_score: float = 0.0
    dimensions: list[DimensionScore] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    transcript: Transcript = Field(default_factory=Transcript)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class WordChoiceFinding(BaseModel):
    """Shared by BOTH the Claude word-choice pass and the offline fallback, so they
    are interchangeable. Used as the structured-output schema for messages.parse."""

    model_config = {"extra": "forbid"}

    word_index: int
    issue_type: Literal["weak", "hedge", "filler", "tripped_up"]
    original: str
    suggestion: Optional[str] = None
    rationale: str
    confidence: float


class WordChoiceFindingList(BaseModel):
    """Wrapper so messages.parse(output_format=...) returns a list of findings."""

    model_config = {"extra": "forbid"}

    findings: list[WordChoiceFinding] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# (De)serialization + derived-field computation
# --------------------------------------------------------------------------- #

_SENT_END = re.compile(r"[.!?]+[\"')\]]*$")


def load_transcript_json(path: str) -> Transcript:
    """Load a canonical Transcript fixture (no ASR, no network) and derive fields."""
    with open(path, "r", encoding="utf-8-sig") as fh:  # tolerate a BOM
        data = json.load(fh)
    t = Transcript.model_validate(data)
    return derive_transcript_fields(t)


def load_transcript_text(source: str) -> Transcript:
    """Build a Transcript from a plain-text transcript (a file path or raw text).

    There are no word timestamps, so ``has_timing`` is False and timing-dependent
    dimensions (pace, pauses, tripped-up timing fusion, prosody) are skipped by the
    pipeline. The lexical analyses (fillers, weak/hedging words, vocabulary,
    readability, word choice) all still run. This is what makes "grade any
    transcript" work across projects, most of which only have text.
    """
    text = source
    if os.path.exists(source):
        with open(source, "r", encoding="utf-8-sig") as fh:  # tolerate a BOM
            text = fh.read()
    words = _text_words(text)
    t = Transcript(words=words, engine="text", has_timing=False)
    return derive_transcript_fields(t)


_VTT_VOICE = re.compile(r"^<v(?:\.[^ >]*)?\s+([^>]+)>\s*")
_NAME_PREFIX = re.compile(r"^([A-Z][\w.'-]*(?: [A-Z0-9][\w.'-]*){0,2}):\s+")


def _text_words(text: str) -> list[Word]:
    """Split text into Words, carrying speaker labels from VTT ``<v Name>`` tags or
    ``Name:`` line prefixes. A ``Name:`` prefix only counts when the same name opens
    at least two lines, so a stray "Note: ..." does not invent a speaker."""
    lines = text.splitlines()
    names = [m.group(1) for ln in lines if (m := _NAME_PREFIX.match(ln.strip()))]
    repeated = {n for n in names if names.count(n) >= 2}
    words: list[Word] = []
    speaker: Optional[str] = None
    for ln in lines:
        ln = ln.strip()
        m = _VTT_VOICE.match(ln)
        if m:
            speaker, ln = m.group(1).strip(), ln[m.end():]
            ln = ln.replace("</v>", "")
        else:
            m = _NAME_PREFIX.match(ln)
            if m and m.group(1) in repeated:
                speaker, ln = m.group(1), ln[m.end():]
        words += [Word(text=tok, start=0.0, end=0.0, speaker=speaker) for tok in ln.split()]
    return words


def dump_report_json(report: Report, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report.model_dump_json(indent=2))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


_TAG_WORDS = {"music", "applause", "laughter", "laughs", "cheering", "cheers", "inaudible",
              "crosstalk", "silence", "booing", "chanting"}


def _is_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) > 1 and all(c.isupper() for c in letters)


def drop_nonspeech_tags(words: list) -> list:
    """Remove ASR sound-event captions ("MUSIC", "CHEERING AND APPLAUSE", "[Applause]").

    A tag is a bracketed token, or an all-caps tag word (plus an "AND" joining two);
    a lowercase "music" said by the speaker, and all-caps chanting ("USA!"), stay.
    """
    keep = [True] * len(words)
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r"^[\[(].*[\])][.,!?]*$", w.text.strip()):
            keep[i] = False
            i += 1
            continue
        if _is_upper(w.text):
            j = i
            while j < len(words) and _is_upper(words[j].text):
                j += 1
            norms = [normalize_token(x.text) for x in words[i:j]]
            for k, n in enumerate(norms):  # tag words, and "AND" joining two tags
                joins = n in ("and", "&") and 0 < k < len(norms) - 1                     and norms[k - 1] in _TAG_WORDS and norms[k + 1] in _TAG_WORDS
                if n in _TAG_WORDS or joins:
                    keep[i + k] = False
            i = j
            continue
        i += 1
    return [w for w, k in zip(words, keep) if k]


_CROWD_SOUNDS = {"oh", "ooh", "ah", "aah", "woo", "whoo", "wooo", "yeah", "hey", "wow", "yay"}


def drop_crowd_runs(words: list, min_run: int = 3, max_conf: float = 0.5) -> list:
    """Remove crowd noise ASR heard as words: 3+ identical interjections in a row
    ("Oh! Oh! Oh!") at low mean confidence. Whisper small wrote these before Michelle
    Obama's 2016 DNC speech; medium heard nothing. A single "oh", a confident run,
    and emphatic repeats of real words ("no, no, no") stay.
    """
    keep = [True] * len(words)
    i = 0
    while i < len(words):
        n = words[i].normalized or normalize_token(words[i].text)
        j = i
        while j < len(words) and (words[j].normalized or normalize_token(words[j].text)) == n:
            j += 1
        confs = [w.confidence for w in words[i:j] if w.confidence is not None]
        if n in _CROWD_SOUNDS and j - i >= min_run and confs and sum(confs) / len(confs) < max_conf:
            keep[i:j] = [False] * (j - i)
        i = j
    return [w for w, k in zip(words, keep) if k]


def derive_transcript_fields(t: Transcript) -> Transcript:
    """Fill normalized forms, speaker_median_gap, sentence spans, speaking_sec,
    and duration_sec when missing. Idempotent."""
    kept = drop_crowd_runs(drop_nonspeech_tags(t.words))
    if len(kept) != len(t.words):
        if t.turn_starts:  # turn starts index words: shift them past the dropped tags
            ids = {id(w): n for n, w in enumerate(kept)}
            new, n = [], 0
            for i, w in enumerate(t.words):
                if i in t.turn_starts:
                    new.append(n)
                n += id(w) in ids
            t.turn_starts = sorted({x for x in new if x < len(kept)})
        t.words = kept
    words = t.words
    for w in words:
        if not w.normalized:
            w.normalized = normalize_token(w.text)

    # speaking_sec = summed phonation time; duration_sec = wall-clock span.
    t.speaking_sec = round(sum(w.duration for w in words), 4)
    if words and not t.duration_sec:
        t.duration_sec = round(max(w.end for w in words) - min(w.start for w in words), 4)

    gaps = [t.gap_before(i) for i in range(1, len(words))]
    # Only count plausible inter-word gaps (ignore overlaps / huge silences) for the median.
    plausible = [g for g in gaps if 0.0 < g < 3.0]
    t.speaker_median_gap = round(_median(plausible), 4)

    # Sentence/clause spans: split on sentence-final punctuation in the surface form.
    sentences: list[tuple[int, int]] = []
    start_idx = 0
    for i, w in enumerate(words):
        if _SENT_END.search(w.text.strip()):
            sentences.append((start_idx, i))
            start_idx = i + 1
    if start_idx < len(words):
        sentences.append((start_idx, len(words) - 1))
    t.sentences = sentences
    return t


def sentence_index_of(t: Transcript, word_index: int) -> int:
    """Return the index into t.sentences containing ``word_index`` (or -1)."""
    for si, (a, b) in enumerate(t.sentences):
        if a <= word_index <= b:
            return si
    return -1


def is_sentence_initial(t: Transcript, word_index: int) -> bool:
    return any(a == word_index for a, _ in t.sentences)


def is_sentence_final(t: Transcript, word_index: int) -> bool:
    return any(b == word_index for _, b in t.sentences)
