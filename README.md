# orator — speech grading

Grade a spoken sample on **delivery** (fillers, pace, pauses, monotone, energy) and
**content** (vocabulary richness, readability, weak/hedging words, repetitions), and
flag the signature thing: **got-tripped-up moments** where you hesitated and reached
for a worse word, with a stronger one suggested.

Built from a survey of the open-source speech-analysis landscape (see
[References](#references)). Runs on Windows/CPU, commercially licensable by default,
and the analysis layer works fully offline with no model download.

## The one insight that makes this work

Standard speech-to-text (Whisper, Google, most APIs) **deletes filler words on
purpose**. If you transcribe normally you literally cannot count "um". Every serious
tool in this space solves that first by using a **verbatim** recognizer. orator
handles it at the ASR-backend layer (verbatim decode prompt + word timestamps), so
the analysis layer stays engine-agnostic.

## Quickstart

```bash
# 1. create a venv and install (uv shown; pip works too)
uv venv .venv
uv pip install -e .                      # core, offline analysis + reporting

# 2a. grade a canonical transcript JSON (no model, no network)
orator tests/fixtures/sample_transcript.json --offline --html report.html

# 2b. grade an audio file (installs faster-whisper on demand)
uv pip install -e ".[asr]"
orator talk.wav --backend faster-whisper --acoustic --html report.html

# 2c. grade a plain-text transcript (no audio, no model)
orator answer.txt --html report.html

# 2d. richer word-choice via Claude API (needs ANTHROPIC_API_KEY)
uv pip install -e ".[llm]"
orator talk.wav --llm --effort high --html report.html
```

## Word choice without an API key: agent handoff

The mechanical metrics and a deterministic offline word-choice pass need nothing.
For the richer "better word / tripped-up" judgments you have two options: the Claude
API (`--llm`), or an **agent handoff** where Claude (in the loop, e.g. Claude Code)
does the pass with no key:

```bash
orator answer.txt --emit-request --html report.html       # writes answer.txt.llm-request.json
# an agent reads the request and writes answer.txt.llm-response.json ({"findings":[...]})
orator answer.txt --wordchoice-json answer.txt.llm-response.json --html report.html
```

The merged report's mode becomes `claude-agent`. The offline lexicon pass is always
the source of record, so the score is valid even if you never enrich it.

## Use it across the workspace

Any transcript of spoken delivery in any project gets graded and circled back to one
ledger via the wrapper (it writes a report next to the source, appends to
`graded-log.md`, and emits the enrichment request):

```powershell
pwsh speech-grading\orate.ps1 path\to\answer.txt
pwsh speech-grading\orate.ps1 path\to\answer.txt -WordChoice path\to\answer.txt.llm-response.json
```

This is the always-on rule [`.agents/rules/grade-spoken-transcripts-with-orator.md`](../.agents/rules/grade-spoken-transcripts-with-orator.md).
Text transcripts (`.txt/.md/.vtt/.srt`) skip the timing-only dimensions (pace,
pauses) automatically and the scorer redistributes their weight.

Open `report.html` for the score, the per-dimension breakdown, and the transcript
with fillers / weak words / repetitions / tripped-up moments highlighted inline
(hover any highlight for the reason and the suggested stronger word). A sample is
checked in at [sample_report.html](sample_report.html).

## What it measures

| Dimension | What it catches | Needs |
|---|---|---|
| Fillers | um, uh, like, you know, basically (pause-gated, context-aware) | text + timestamps |
| Pace | words/min vs an ideal band, plus consistency over time | text + timestamps |
| Pauses / fluency | long mid-clause (awkward) pauses, repetitions, false starts | text + timestamps |
| **Word choice / tripped-up** | hesitation + a worse word, with a stronger suggestion | text + timestamps (+ optional Claude) |
| Vocabulary | length-robust lexical diversity (MATTR / MTLD) | text |
| Hedging | maybe, I think, kind of, very, really (density) | text |
| Readability | spoken grade level (relative tracking) | text |
| Prosody (optional) | monotone (pitch range), energy dynamics, acoustic filled pauses | audio + parselmouth/librosa |

### How "tripped-up" works

A lexical match alone is not enough. orator fuses signals on a shared time axis:

```
event_score = w·hedge + w·vague + w·pause_before + w·(low ASR confidence)
            + w·(filler just before) + w·(repetition / restart just before)
```

A weak word only surfaces as a stumble when it **co-occurs** with a hesitation
signal (a long pause, a low-confidence word, a filler, or a repair). That is what
separates "I deliberately said *maybe*" from "I stalled and grabbed *maybe*".

## Architecture

```
audio ──▶ ASR backend (pluggable)  ──┐
                                     ├─▶ canonical Transcript  (words: text/start/end/confidence)
transcript.json ────────────────────┘            │
                                                  ▼
        analysis (pure, offline, unit-tested on a JSON fixture)
        fillers · pace · pauses · repetitions · vocabulary · readability · weak-words · prosody
                                                  │
                            word-choice: Claude (opt-in) ──or──▶ offline lexicon fusion
                                                  ▼
                          scorer (weighted 0-100, redistributes absent dims)
                                                  ▼
                            report  ──▶  inline-highlighted HTML  +  JSON
```

- **ASR is decoupled.** Default `faster-whisper` (MIT). `crisper-whisper` is opt-in
  behind `--allow-noncommercial` (its weights are CC BY-NC). `vosk` (Apache-2.0) for
  streaming/embedded.
- **The word-choice LLM pass is enrichment only.** The deterministic offline
  analyzer is the source of record, so an API error can never corrupt the score.
- **Everything below the ASR line is pure** and tested from
  `tests/fixtures/sample_transcript.json` with no model and no network.

## Development

```bash
uv pip install -e ".[dev]"
python tests/_build_fixture.py     # regenerate the sample fixture
pytest -q                          # full suite, fully offline
```

## Licensing

Default stack is permissive (MIT/BSD/Apache/ISC: faster-whisper, lexicalrichness,
textstat, proselint, nltk, jinja2, librosa, vosk). Non-permissive engines are gated:
CrisperWhisper (CC BY-NC) needs `--allow-noncommercial`; the optional prosody track
uses Parselmouth (GPL-3.0, fine for internal/SaaS, a consideration for shipped
binaries). Drop the full Brysbaert concreteness and SUBTLEX frequency CSVs into
`speech_grading/data/` to sharpen offline better-word ranking; a small built-in
table keeps it useful without them.

## References

Open-source projects that informed the design:

- [nyrahealth/CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper) — verbatim ASR that emits [UM]/[UH] with disfluency-robust timestamps
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — fast MIT Whisper with per-word probability (the default backend)
- [linto-ai/whisper-timestamped](https://github.com/linto-ai/whisper-timestamped) — word timestamps + `detect_disfluencies`
- [m-bain/whisperX](https://github.com/m-bain/whisperX) — wav2vec2 forced alignment for sharp timestamps
- [SharathKumar787/AI-Transcript-Scoring-Tool](https://github.com/SharathKumar787/AI-Transcript-Scoring-Tool) — the rubric formulas (filler rate, WPM bands, TTR)
- [unruli/Real-Time-Feedback-System-for-Student-Presentations](https://github.com/unruli/Real-Time-Feedback-System-for-Student-Presentations) — full feedback-system architecture
- [Averylamp/SpeakEZ](https://github.com/Averylamp/SpeakEZ) — word complexity / word-choice angle
- proselint, write-good, retext-* — weak/weasel/hedging lexicons and rules
- Parselmouth (Praat), librosa — prosody / acoustic analysis
```
