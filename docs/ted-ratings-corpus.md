# TED audience ratings: an outside-labeled validation corpus for orator

Status: corpus built 2026-11-25; development grading in progress; held-out set sealed.
Tool: `tools/ted_ratings_corpus.py`. Manifest: `docs/ted-ratings-manifest.json`.
Content checks: `docs/ted-ratings-content-checks.json`. Analysis plan: `docs/ted-ratings-charter.md`.

## Why

On the hand-curated exemplar corpus (33 acclaimed, 17 panned) orator's overall score does not
separate good from bad speeches (AUC 0.42). A 0.05 AUC difference needs about 370 independent
speakers. This corpus gives 400 single-speaker TED talks, one per speaker, each labeled by the
viewers who rated it on TED.com.

## Label source

`ted_main.csv` from the Kaggle "TED Talks" dataset (rounakbanik; TED.com metadata to 2017-09-21),
read from a key-free GitHub mirror pinned to a commit:

- URL: `https://raw.githubusercontent.com/Duttaay/TED_Talk_Analysis_R-Project/f0c7a888a85566142b88f81274c53271da4aa9e3/ted_main.csv`
- sha256: `801c01b1f88181bce3dc1af7d4416df45d45f5729e6384eccb60368c00fabd6e` (2,550 rows)
- checked: 2026-11-25

The raw CSV stays in `~/.orator/corpus/ted-ratings/source/`; `label` refuses any other bytes.

## Label (fixed before any orator score existed)

`neg_share = (Longwinded + Unconvincing + Obnoxious + Confusing) / all rating-tag counts`.
Higher means viewers more often picked a negative tag. These four are the only negative tags in
TED's set of 14, and Longwinded and Obnoxious lean toward delivery; Unconvincing and Confusing
mix in content. Treat the label as a noisy crowd read of delivery, not a rubric score.

Covariates, for the popularity confound: `log10(views)`, film `year`, and `event_class`
(ted_main, ted_global, tedx, ted_women, tedmed, ted_other, external). Raw tag counts scale with
views, which is why the label is a share and views stay a covariate.

## Eligibility

Single speaker (`num_speaker == 1`); 360 to 1,800 s long; at least 200 ratings; none of the tags
performance, music, live music, dance, magic, poetry, spoken word. 2,019 of 2,550 talks pass,
from 1,753 speakers.

## Sample and split (label-blind except the strata)

1. One talk per speaker, picked by a seeded hash (`ted-ratings-2026-11-25`).
2. Ten strata by `neg_share` decile over the 1,753 one-per-speaker talks.
3. Within each stratum, a seeded order; take the first 40 whose YouTube upload resolves.
4. YouTube match rule: search `"{speaker} {title} TED"`, accept the first hit from the TED,
   TEDx Talks or TED Archive channel whose title contains the speaker's surname and whose
   length is within max(60 s, 15%) of the CSV length. Audio is never taken from TED.com.
5. Within each stratum, alternate development and held-out in seeded order; a surname already
   placed stays on its side, and any (surname, year) of the political corpus goes to development.
   `assert_heldout_disjoint` from `tools/exemplar_corpus.py` runs on the result.

Result: 400 talks, 40 per stratum, 207 development and 193 held-out (surname grouping moves a few
across). 700 searches: 3 network errors were skipped as unresolved; 383 matches are on the TED
channel and 17 on TEDx Talks.

## Audio, ASR, content check, grade

- Excerpt: the 120 s centred on the midpoint of the YouTube upload (label-blind), cut by
  `exemplar_corpus.acquire` to 16 kHz mono.
- ASR: faster-whisper `medium`, language `en`, per `Config`, cached with `asr_provenance`.
- Content check C1 (automated, recorded per item and committed before grading): at least 150
  words; no non-speech stretch over 20 s; mean word confidence at least 0.60 (screens out
  non-English talks and music). A failing item is not graded.
- Grade: `exemplar_corpus.grade`, stage mode, acoustic on, no LLM; grades carry the ASR
  provenance and the scoring-code sha256.

Everything under `~/.orator/corpus/ted-ratings/`; nothing but the manifest and checks in the repo.

## Run

```
python tools/ted_ratings_corpus.py label
python tools/ted_ratings_corpus.py sample
python tools/ted_ratings_corpus.py resolve
python tools/ted_ratings_corpus.py split
.venv/Scripts/python tools/ted_ratings_corpus.py run --split development --stage acquire
.venv/Scripts/python tools/ted_ratings_corpus.py run --split development --stage transcribe
.venv/Scripts/python tools/ted_ratings_corpus.py run --split development --stage check
# commit docs/ted-ratings-content-checks.json, then
.venv/Scripts/python tools/ted_ratings_corpus.py run --split development --stage grade
.venv/Scripts/python tools/ted_ratings_corpus.py analyze
```

Every stage is cached per item, so a rerun resumes.

## Known limits

- Raters are self-selected TED.com visitors; tag choice is shaped by topic, speaker identity
  (race and gender effects are documented) and content as well as delivery.
- All talks are polished TED productions, so the delivery range is narrow.
- A 120 s mid-talk excerpt is not the whole talk the viewers rated.
- The 2017 snapshot ends rating counts at that date; later views are not reflected.
