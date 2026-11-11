# orator: speech grading

Orator is a Python CLI that grades spoken transcripts and audio on delivery (fillers, pace, pauses, monotone, energy) and content (vocabulary richness, readability, hedging words, repetitions). It also flags hesitation stumbles where a speaker pauses or uses a filler and reaches for a weak word, suggesting a stronger replacement.

Core transcript analysis runs offline on CPU with no model download. Optional extras add verbatim speech-to-text, acoustic prosody analysis, and LLM word-choice enrichment. Scores are deterministic heuristics for practice and review, not clinical assessments.

## Sample speech report

![Orator report showing seven scoring dimensions and highlighted synthetic transcript](docs/images/orator-synthetic-report.jpg)

A synthetic timestamped transcript, analyzed with the offline lexicon. The report shows dimension scores and highlights fillers, hedges, repetitions, and hesitation-linked word choices. The rendered report is [examples/sample_report.html](examples/sample_report.html); GitHub shows its source, so download it and open it in a browser.

## From recording to feedback

```mermaid
flowchart LR
    A["Audio recording"] --> B["Optional local speech-to-text"]
    B --> D["Transcript analysis"]
    C["Text or timestamped transcript"] --> D
    A --> E["Optional acoustic analysis"]
    D --> F["Scores and highlighted HTML report"]
    E --> F
    D -.-> G["Optional word-choice enrichment"]
    G -.-> F
```

Text-only grading runs offline. Timestamps unlock pace and pause measures; audio adds optional prosody analysis.

## Why verbatim ASR matters

Standard speech-to-text engines delete filler words by default. If a recognizer strips "um" and "uh" during transcription, downstream code cannot count them. Orator configures its ASR backend with a verbatim decode prompt and word-level timestamps so the analysis layer stays engine-agnostic.

## Installation and Quickstart

Requires Python 3.10 or newer.

```bash
# Create a virtual environment
python -m venv .venv

# Unix / macOS: .venv/bin/python -m pip install -e .
# Windows:      .venv\Scripts\python -m pip install -e .
pip install -e .
```

### 1. Grade a transcript offline (no model weights, no network)

```bash
# Grade a canonical word-timestamp JSON fixture (synthetic fixture included)
orator tests/fixtures/sample_transcript.json --offline --html report.html

# Grade a plain-text transcript (.txt, .md, .vtt, .srt)
orator answer.txt --html report.html
```

Plain-text transcripts skip timing-only dimensions (pace, pauses) automatically and redistribute their weight across the remaining dimensions.

### 2. Grade an audio file (requires `asr` and `acoustic` extras)

```bash
pip install -e ".[asr,acoustic]"
orator talk.wav --backend faster-whisper --acoustic --html report.html
```

### 3. Optional word-choice enrichment (`llm` extra or agent handoff)

Core scoring runs locally without an API key. For deeper word-choice suggestions, use either the Anthropic API (`--llm`, which sends transcript text to Anthropic) or a two-step local JSON handoff:

```bash
# Option A: Anthropic API (requires ANTHROPIC_API_KEY)
pip install -e ".[llm]"
orator talk.wav --llm --effort high --html report.html

# Option B: Key-free JSON handoff
orator answer.txt --emit-request --html report.html
# Fill answer.txt.llm-response.json ({"findings": [...]}), then merge:
orator answer.txt --wordchoice-json answer.txt.llm-response.json --html report.html
```

### 4. Grade a video file (visual cues + audio ASR)

```bash
orator talk.mp4 --mode zoom --html report.html
```

For video, orator pulls a 16 kHz WAV out with ffmpeg (PATH, else `Fantasy Golf App/tools/video/bin`) for ASR and prosody, and tracks smile, gaze, chin pitch and hand-to-face contact.

Open `report.html` to view the overall score, dimension breakdown, and inline-highlighted transcript. A static sample output is checked in at [sample report](examples/sample_report.html).

## Input formats and video analysis

Orator accepts text transcripts, audio recordings, or video files:

- **Text transcripts (`.txt`, `.md`, `.vtt`, `.srt`):** Runs offline text analysis (fillers, weak words, vocabulary, readability). Skips timing dimensions automatically.
- **Timed transcripts (`.json`):** Canonical word-timestamp fixtures that enable pace and pause measures offline without model dependencies.
- **Audio recordings (`.wav`, `.mp3`, any other extension):** Transcribed locally via ASR. Adding `--acoustic` measures pitch dynamics (F0 variation) and energy contour.
- **Video recordings (`.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v`):** Audio extracted with ffmpeg, transcribed via ASR, and analyzed for visual behavior. Without ffmpeg, ASR reads the video directly where the backend can, and prosody is skipped.

### Multi-speaker transcripts

Grade one speaker with `--speaker`. The labels must already be in the input: a `speaker` field per word in `.json`, VTT `<v Name>` tags, or `Name:` line prefixes in text (a name must open at least two lines). No ASR backend diarizes yet. Other speakers' turns never count as pauses, pace time, or prosody.

```bash
orator podcast.json --speaker SPEAKER_00 --html report.html
```

### Video speaking modes (`--mode`)

Different settings require different cue thresholds:

Each mode picks which cues run and how strict they are (see `PROFILES` in `speech_grading/analysis/visual_events.py`):

- `default`: face touch, chin up, smile after sentence, gaze check after sentence.
- `zoom`: drops the gaze check (screen sits below the lens).
- `phone`: all cues; looser face-touch distance (0.20) and chin threshold (10 deg) for a close camera.
- `stage`: face touch and chin up only; tighter face-touch distance (0.12); scanning the audience is normal.
- `interview`: drops the gaze check (speaker looks at the interviewer).

Video cues are reported as counts, plus per-minute rates for clips of 60s or more. They do not change the overall score. Chin up and smile are measured against the speaker's own first 30 seconds, so a habit held from the start is never flagged. The visual tier tracks one face; `--speaker` does not choose which face.

### Visual models location

The visual tier loads MediaPipe models from `~/.orator/models` (or the `$ORATOR_MODELS` environment variable):

- `face_landmarker.task`: 478 face landmarks, blendshapes, and transformation matrix.
- `hand_landmarker.task`: 21 hand landmarks for face-touch detection.

### Feature export for training

To export windowed visual feature records for training or calibration:

```bash
orator talk.mp4 --visual-rows features.jsonl
```

## What it measures

| Dimension | What it catches | Inputs required |
|---|---|---|
| Fillers | um, uh, like, you know, basically (pause-gated, context-aware). Stock Whisper drops many fillers, so the rate is a lower bound | text + timestamps |
| Pace | words per minute against a target band, plus consistency over time | text + timestamps |
| Pauses and fluency | mid-clause pauses, repetitions, false starts | text + timestamps |
| Word choice / tripped-up | hesitation co-occurring with a weak word, plus replacement candidates | text + timestamps (+ optional LLM) |
| Vocabulary | length-robust lexical diversity (MATTR / MTLD) | text |
| Hedging | maybe, I think, kind of, very, really (density) | text |
| Readability | spoken grade level | text |
| Prosody (optional) | pitch range, energy dynamics, acoustic filled pauses | audio + `acoustic` extra |

### How "tripped-up" detection works

A weak word alone is not flagged as a stumble. Orator fuses signals on a shared time axis:

```text
event_score = w*hedge + w*vague + w*pause_before + w*(low ASR confidence)
            + w*(filler just before) + w*(repetition or restart just before)
```

A weak word surfaces as a stumble only when it co-occurs with a hesitation signal (a pause, low ASR confidence, a filler, or a phrase restart).

## Privacy and network boundaries

- **Core transcript mode (`pip install -e .`):** Runs 100% locally and offline.
- **ASR mode (`pip install -e ".[asr]"`):** Downloads `faster-whisper` model weights on first run, then transcribes locally.
- **LLM mode (`--llm`):** Sends transcript text to the Anthropic API.
- **Data hygiene:** `tests/fixtures/sample_transcript.json` and `examples/sample_report.html` are synthetic fixtures. Keep personal audio recordings and private transcripts outside the repository.

## Development

```bash
pip install -e ".[dev]"
python tests/_build_fixture.py     # regenerate the synthetic fixture
pytest -q                          # run the offline test suite
```

## License

This project is released under the [MIT License](LICENSE). Optional dependencies carry their own licenses: `faster-whisper`, `lexicalrichness`, `textstat`, `proselint`, `nltk`, `jinja2`, and `librosa` use permissive licenses (MIT/BSD/Apache/ISC); the optional `acoustic` extra includes `praat-parselmouth` (GPL-3.0); the opt-in `crisper-whisper` backend (`--allow-noncommercial`) uses CC BY-NC weights.

## References

Open-source projects that informed the design:

- [nyrahealth/CrisperWhisper](https://github.com/nyrahealth/CrisperWhisper): verbatim ASR that emits `[UM]`/`[UH]` with disfluency-robust timestamps
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper): CTranslate2 Whisper implementation with word-level probabilities
- [linto-ai/whisper-timestamped](https://github.com/linto-ai/whisper-timestamped): word timestamps and disfluency detection
- [m-bain/whisperX](https://github.com/m-bain/whisperX): wav2vec2 forced alignment for word timestamps
- [SharathKumar787/AI-Transcript-Scoring-Tool](https://github.com/SharathKumar787/AI-Transcript-Scoring-Tool): filler-rate, WPM-band, and lexical diversity rubrics
- [unruli/Real-Time-Feedback-System-for-Student-Presentations](https://github.com/unruli/Real-Time-Feedback-System-for-Student-Presentations): presentation feedback pipeline design
- [Averylamp/SpeakEZ](https://github.com/Averylamp/SpeakEZ): spoken word-choice and complexity scoring

## Repository layout

- `speech_grading/`: transcript schema, analysis, ASR adapters, and report rendering.
- `tests/`: offline tests and synthetic fixtures.
- [examples/](examples/README.md): synthetic transcript, sample reports, and word-choice request/response packets.
- `orate.ps1`: optional PowerShell wrapper for local grading.

Install and test with `pip install -e ".[dev]"` and `python -m pytest`.

## More projects

More of my work and contact details are at [twhite.dev](https://twhite.dev).
