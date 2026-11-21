# Acclaimed vs panned speeches: does orator's grade track acclaim?

Status: research diagnostic, 2026-11-19, independently reviewed. No scoring threshold was changed on the
strength of this corpus (see "What this does not change").

> **Data-quality correction, 2026-11-20.** A later model-pipeline data audit found 6 of
> the 40 stage rows invalid. Four transcripts have Whisper `small` language drift:
> e_rowling_harvard_2008, e_adichie_ted_2009, p_miliband_conf_2014 and
> p_clinton_dnc_1988. Two sources carry the wrong content: a_miliband_conf_2012 is a
> commentator and p_kinnock_sheffield_1992 is a news package. p_dukakis_debate2_1988
> (default mode) is also commentary.
>
> At least 15 further stage rows include introducers, announcers, MCs or music, because
> no speaker filter or excerpt bounds were applied. The pace and pause numbers below are
> therefore contaminated and must be treated as provisional until the corpus is
> re-verified and regraded. That includes the count of fast acclaimed talks behind
> Finding 1. The audit record is in the workspace's private
> `.agents/model-records/speech-grading/orator-pace-pause-2026-11-20/`.

## Question

Rankings of the best speeches, plus press and coach verdicts on the worst ones, give
an outside label of delivery quality that orator has never been checked against. This
corpus asks three things:

1. Do orator's scores separate widely acclaimed speeches from widely panned ones?
2. Within one speaker, does orator rank their praised day above their panned day?
3. When one delivery factor is degraded on purpose, does the targeted metric move,
   and only that metric?

## Sources and selection

**Acclaimed set (`docs/exemplar-positive-candidates.json`, 26 candidates).** Each pick
appears on at least one ranking, and most on two or more:
- the Lucas and Medhurst 1999 survey of 137 rhetoric scholars (8 picks; American Rhetoric hosts the Top 100)
- the Art of Manliness top 35 (8 picks)
- WatchMojo's 2015 list (4)
- TED most-popular and TED's own editorial picks (10)
- NPR's commencement archive (4)
- official Toastmasters World Champions (3)
- single-source press lists for debate moments and individual speeches

Rankings mostly reward content, occasion and historical weight. Only the Toastmasters
results and some TED lists judge delivery directly. Treat "acclaimed" as a noisy label
for delivery.

**Panned and paired set (`docs/exemplar-contrast-candidates.json`).** 19 panned
speeches and 10 within-speaker pairs (one of them relative, see below). Each entry carries cited press, critic or coach
judgements and a `poor_reason`. Delivery failures were preferred over content pans: the
Biden 2024 debate, Obama's first 2012 debate, Reagan's first 1984 debate, Clinton's
1988 DNC length, Michael Bay's CES freeze, Jindal's 2009 response, Eastwood's empty
chair. Six candidates were dropped for unverifiable or content-only failures; the file
lists them.

**Graded:** 50 of 54. Four sources would not download, and the run never retried them:
- Reagan's Challenger address
- Wallace's Kenyon speech
- Perry's "oops" moment
- Jeb Bush's "please clap" moment

That leaves 33 acclaimed speeches (31 stage, 2 debate) and 17 panned (9 stage, 8
debate). The acclaimed group mixes 24 graded ranked speeches with 9 speeches added for the
pairs: 7 praised-day sides that are on no ranking, Beverly's 2019 championship round,
and his 2016 runner-up round. The pairs are 9 praised/panned pairs plus 1 relative pair
(Beverly 2016 vs 2019, both acclaimed). Audio and transcripts stay in
`~/.orator/corpus/exemplars` only.

**Method:** whisper `small` ASR, acoustic features on, no LLM word choice. Audio was
capped at 15 minutes from the start. The mode was `stage` for speeches and `default`
for debates and interviews. Tools: `tools/exemplar_corpus.py` (acquire, grade,
summarize) and `tools/ab_degrade.py`.

## Result 1: the overall score does not separate acclaimed from panned

AUC is the chance that a random acclaimed speech scores higher than a random panned
one. 0.5 means no separation.

| metric | median acclaimed | median panned | AUC all | AUC stage only | acclaimed 10th to 90th pct |
|---|---|---|---|---|---|
| overall_score | 85.4 | 86.6 | 0.42 | 0.37 | 80.4 to 91.2 |
| pace_points | 24.2 | 40.1 | 0.46 | 0.34 | 0 to 50 |
| prosody_points | 94.5 | 100.0 | 0.39 | 0.37 | 83.3 to 100 |
| fillers_points | 100 | 100 | 0.57 | 0.59 | 100 to 100 |
| pauses_points | 100 | 100 | 0.53 | 0.59 | 82 to 100 |
| wpm | 127.6 | 163.3 | 0.34 | 0.39 | 106 to 179 |
| filler_rate_per_100w | 0.50 | 0.76 | 0.30 | 0.27 | 0.07 to 1.52 |
| long_pauses_per_min | 9.1 | 8.5 | 0.59 | 0.53 | 5.2 to 13.2 |
| mean_length_of_run (words) | 10.8 | 11.2 | 0.52 | 0.56 | 8.2 to 14.8 |
| monotone_semitones | 3.69 | 4.05 | 0.40 | 0.42 | 3.0 to 5.2 |
| energy_dynamics | 0.80 | 0.76 | 0.55 | 0.43 | 0.57 to 1.09 |
| mean_sentence_words | 17.1 | 15.4 | 0.66 | 0.71 | 11.3 to 22.4 |
| question_count_per_1000w | 1.3 | 5.3 | 0.30 | 0.32 | 0 to 8.2 |
| anaphora_count_per_1000w | 1.34 | 0.47 | 0.59 | 0.63 | 0 to 3.0 |
| tricolon_count_per_1000w | 0.67 | 0.00 | 0.56 | 0.55 | 0 to 2.7 |

Among stage speeches only, the overall AUC is 0.37: if anything orator leans toward
panned speeches, though that sits inside the noise band given below. The extremes
illustrate it:
- Julian Treasure's TED talk on how to speak scored lowest of all 50 (73.8).
- Palin's widely mocked 2016 endorsement scored 93.7, the third highest.

The full per-metric table, generated by the tool, is `summary.md` beside the corpus
summary. The stage-only AUCs and the percentile ranges are in `summary.json` only.
Rates marked `_per_min` divide by orator's `speaking_sec`, not by wall-clock duration.

## Result 2: within-speaker pairs

Nine speakers, each graded on a praised and a panned day. The relative Beverly pair
is left out here. The summary tool counts only pairs with a panned poor side, so these figures are the
`paired` block of the regenerated `summary.json`.

| metric | good side higher | good side lower | ties | sign p | Wilcoxon p |
|---|---|---|---|---|---|
| overall_score | 4 | 5 | 0 | 1.00 | 1.00 |
| prosody_points | 1 | 7 | 1 | 0.07 | 0.20 |
| filler_rate_per_100w | 2 | 7 | 0 | 0.18 | 0.24 |
| question_count_per_1000w | 2 | 7 | 0 | 0.18 | 0.04 |
| signpost_rate_per_100w | 1 | 6 | 2 | 0.125 | 0.03 |

Orator picks the better day 4 times in 9, no better than a coin. Questions and
signposts run higher on the panned day. Read that as exploratory: about 65 metrics were
tested, with no multiplicity correction, and the sign tests are not significant.
Format plausibly drives it: 5 of the 9 panned sides are debates. In 4 pairs the format
switches from speech to debate, and in Reagan's pair both sides are debates.

## Findings

1. **The stage pace band penalizes acclaimed TED delivery.**
   - Acclaimed TED and commencement talks run 160 to 182 WPM and get 0 to 24 pace points.
   - Jobs is at 166 WPM (9 points); Sinek, Robinson, Urban and Treasure each get 0.
   - The stage band (ideal 110 to 150, fair 95 to 170) is a heuristic.
   - The evidence map already says rate norms depend on genre. About 7 talks, under a
     label this doc calls noisy, suggest the band is too slow for the modern keynote
     register.
2. **Fillers and pauses barely discriminate.**
   - `fillers_points` is 100 for almost every clip, acclaimed or panned.
   - Raw filler rate leans the expected way (panned 0.76 vs 0.50 per 100 words), but
     whisper `small` drops many fillers (see `speech-fluency-measurement`). The input
     is too sparse for the dimension to bite.
3. **Prosody points show no acclaim signal, and may lean the wrong way.**
   - Panned speeches more often get the full 100. In 7 of 8 untied pairs the good side
     scored lower (sign p 0.07, not significant).
   - Pitch range does not separate the sets (AUC 0.40, inside the noise band). That is
     consistent with the evidence map's "no evidence" verdict on the monotone cutoffs.
4. **Long pauses look like a quality signal until speech length is controlled.**
   - Raw `long_pauses` reached AUC 0.73 because the acclaimed clips are longer
     (884 s vs 365 s median).
   - Per minute, the effect is gone (AUC 0.59). Raw counts in reports should be read as
     rates.
5. **Only sentence length clears the noise band among the structure metrics.**
   - Longer sentences lean acclaimed (AUC 0.71 stage only).
   - Anaphora (0.63) and tricolons (0.55; acclaimed median 0.67 per 1000 words,
     panned 0) sit inside the noise band.
   - The acclaimed set is dominated by written, read-aloud oratory, so even the
     sentence-length effect may be register rather than skill.

## Confounds and limits

- n is small (33 vs 17; 9 pairs, plus 1 relative pair). Treat AUCs between about 0.35 and 0.65 as noise.
- **Format:** about half the panned items (8 of 17) are debates or interviews (`default` mode), while
  acclaimed ones are stage speeches. The stage-only column exists for this reason.
- **Era and recording:** the acclaimed set leans on 1930s to 1960s broadcast audio,
  which changes pitch and energy measures.
- **Labels:** acclaim mostly rewards content and occasion. Several "panned" verdicts
  are about a single moment that a 15-minute cap may not contain (Gore's sighs happen
  while Bush is speaking).
- **Sources:** some are excerpts or fan uploads (noted per candidate). Debate audio
  includes moderators and opponents, because diarization was not run.

## Controlled degradations (one factor at a time)

`tools/ab_degrade.py` takes a 120 s clip from 5 graded exemplars. It writes one
degraded copy per transform:
- pace 0.8x and 1.25x
- flattened pitch
- compressed dynamics
- 1.5 s silence inserted mid-clause, at a boundary found by `pick_midclause_boundary`
- a same-speaker "um" spliced in, when the transcript has one

It then regrades every copy and checks the targeted metric with `degradation_verdict`.

Clips: Sinek, Jobs, Brown, Hettiarachchi and Obama 2004, from 60 to 180 s. The
per-clip table is `~/.orator/corpus/exemplars/ab/ab_degrade.md`.

| transform | target metric | moved as expected | overall score change, per clip |
|---|---|---|---|
| pace 0.8x | wpm down | 5 of 5 | +3.9, +6.5, +10.2, -1.6, -1.7 |
| pace 1.25x | wpm up | 5 of 5 | -1.6, -2.1, -2.8, -8.9, -6.4 |
| pitch flattened | monotone_semitones down | 5 of 5 | -7.0, -7.0, -4.5, -7.1, -5.9 |
| dynamics compressed | energy_dynamics down | 5 of 5 | -4.5, +1.0, +0.2, -0.1, +0.4 |
| 1.5 s mid-clause silence | midclause_pauses up | 0 of 5 | +1.2, -1.0, -0.5, +0.2, +2.0 |
| same-speaker "um" | filler_count up | not run | no timed "um" in any of the 5 transcripts |

What it shows:

1. **The measures respond.** Rate, pitch range and energy all moved the right way on
   every clip.
2. **Slowing a fast talk raises its score.** Slowing Sinek, Jobs and Brown to 0.8x
   *raised* their overall scores by 3.9 to 10.2 points. Pace points drove it: Sinek went
   from 17 to 50, Jobs from 13 to 69, and Brown from 0 to 83. This is the stage pace band
   from Finding 1. Time-stretching also moved other metrics, so this is not a pure
   one-factor change.
3. **Compression is not penalized.** Flattening energy dynamics cut `energy_dynamics`
   sharply but left the overall score within 1 point on 4 of 5 clips.
4. **The mid-clause pause detector missed every inserted mid-clause silence.**
   `midclause_pauses` stayed 0 and `pauses_points` stayed 100 on all 5 clips, and the
   overall score moved by 2 points or less. Raw `long_pauses` rose on only 2 of 5.
   Re-transcribing the edited audio also moved filler counts and readability metrics,
   so it reshuffles sentence and pause boundaries. A likely cause, not checked against
   the edited transcripts, is that the ASR punctuates at the new gap, so the pause reads
   as a clause or sentence boundary.
5. **No filler test was possible.** The code searches each clip's whole source
   transcript, and Whisper `small` timed no filled pause anywhere in the 5 transcripts.
   The filler splice therefore had no source; `ab_degrade.md` lists it as skipped. This
   is the same filler-dropping problem as Finding 2.
6. **Time-stretching moves many other metrics.** It shifted 10 to 27 other metrics by
   over 10%, which is expected for rate-dependent measures. Pitch flattening moved 3 to
   17, and compression 1 to 9.

Limits: 5 clips, one 120 s window each, one ASR pass per variant, and no repeat runs
to measure re-ASR noise. All 5 insertion points sit between words with zero gap in
Whisper `small` word times (for example, one word ending at 70.48 s and the next
starting at 70.48 s). Those times are only roughly accurate, so a silence may cut into
a word.

## What this does not change

No band moved. Changing a scoring threshold is a model change under the workspace
predictive-modeling process. This corpus is the evidence for that work, not a
substitute for it. Recommended next steps, in order:

1. Test a genre-aware stage pace band. A keynote register of 150 to 180 WPM is a
   hypothesis from about 7 talks; it needs a pre-fit record and a held-out set.
2. Re-measure fillers with a verbatim ASR before tuning any filler threshold.
3. Test whether prosody points should become descriptive only, against a
   listener-rated set. This corpus alone does not settle it.
4. Report counts as rates throughout.
