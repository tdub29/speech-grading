# Political speech and debate calibration corpus

30 clips (first 15 minutes each): 20 single-speaker political speeches, 10 debates. Graded with
`asr_model_size: small`, `--acoustic --offline`. Audio stays local in `~/.orator/corpus`; only the
source list lives here.

## What the corpus changed

| Median overall | Before | After |
|---|---|---|
| Speeches | 74.1 | 83.1 |
| Debates | 80.2 | 87.2 |

- **Pace** ignored applause: silences longer than `wpm_gap_cap_sec` (2.0s) are cut from the pace clock.
  Speech median pace went from 113 to 124 wpm; the old wall-clock rate stays as `wall_clock_wpm`.
- **Pauses**: a long pause at a sentence edge is delivery, not disfluency. Only mid-clause pauses and
  repairs count. Speech median load went from 7.3 to 2.7 per minute (every major speech was "poor").
- **Prosody** was silently skipped when parselmouth or librosa was missing; `--acoustic` now says so.
  Corpus pitch variation: speeches median 3.3 semitones, debates 4.1.

Slow oratory sits below the 130 to 160 wpm conversational band, so `--mode stage` uses 110 to 150
(fair 95 to 170). With it, speech pace lands good for 14 of 20 clips, fair for 4, poor for 2
(Sanders 2016 at 80 wpm, Trump SOTU 2019 at 92); speech median overall 84.6.
There are no "good speaker" labels here, so this sets reference ranges, not a learned model.

## ASR-robustness pass (Whisper small vs medium)

Goal: the grade should not depend on which Whisper model transcribed the audio. On the
first 5 minutes of four speeches (Sanders 2016, Trump 2019 SOTU, Obama 2004, Michelle
Obama 2016) each clip was graded from a Whisper small transcript and a Whisper medium
reference. Word-count ratio small/medium was 0.98 to 1.04 (a count ratio, not alignment
recall). Four changes:

- Pause after a comma, semicolon or colon counts as a clause boundary (except after a
  filler's comma, "uh,"). Obama mid-clause pauses went 23 (small) vs 8 (medium) to 0 vs 1.
- ASR sound captions (MUSIC, CHEERING AND APPLAUSE, [Applause]) are not scored as words.
- Applause hung on a word's end time costs the same pace clock as applause in a gap.
  Sanders pace error small vs medium went from 6.6% (baseline 68.8 vs 64.6 wpm) to 2.7%.
- A low-confidence run of 3+ identical interjections ("Oh! Oh! Oh!") is treated as crowd noise.

All four clips then landed in the same band on every dimension under both models.

Full 30-clip regrade: median speech score 84.6 to 89.2 (speeches compared with the
stage-mode run, debates with the default-mode run); debates 87.2 to 87.4. Speech pauses
went from 9 good, 7 fair, 4 poor to 18 excellent, 2 good.

### Known limits (adversarial review)

- **Pauses now mostly read ASR punctuation.** 96% of long pauses in the corpus follow
  punctuation, because Whisper punctuates where people pause. With punctuation stripped
  (as a no-punctuation engine like Vosk outputs), Obama 2004 pauses drop from excellent
  to poor; a synthetic talk with 44 six-second freezes after commas still scores
  excellent. The comma rule removed the mid-clause category under both models rather
  than making small match medium. Settling it needs hand-labelled pauses (hesitation vs
  boundary), including non-oratory speech.
- **Agreement is not correctness.** These goals measure small/medium agreement, not
  accuracy against human judgement, on 4 tuning clips with no held-out set. A Whisper
  medium rerun moved the Sanders reference pace by 5%, the same size as the tolerance.
- **Pace cannot tell applause from a freeze.** Any gap over 2 s is cut, so a speaker who
  freezes for 6 s is not slowed. Cutting only gaps with crowd-level audio energy would fix it.
- **The crowd-run rule was fitted to one intro** and could drop a soft "yeah yeah yeah".
- The higher 30-clip median shows the scores shifted, not that grading got more accurate.

## Sources

| Clip | Source |
|---|---|
| s_kennedy_inaugural_1961 | [President John F. Kennedy's Inaugural Address](https://www.youtube.com/watch?v=PEC1C4p0k3E) |
| s_reagan_inaugural_1981 | [C-SPAN: President Reagan 1981 Inaugural Address](https://www.youtube.com/watch?v=hpPt7xGx4Xo) |
| s_reagan_challenger_1986 | [Challenger: President Reagan's Challenger Disaster Speech - ](https://www.youtube.com/watch?v=Qa7icmqgsow) |
| s_clinton_inaugural_1993 | [Bill Clinton inaugural address: Jan. 20, 1993](https://www.youtube.com/watch?v=Qszv668rN20) |
| s_bush_911_address_2001 | [WATCH: President George W. Bush's address to the nation afte](https://www.youtube.com/watch?v=WA8-KEnfWbQ) |
| s_obama_dnc_2004 | [Obama's 2004 DNC keynote speech](https://www.youtube.com/watch?v=ueMNqdB1QIE) |
| s_obama_inaugural_2009 | [Barack Obama inaugural address: Jan. 20, 2009](https://www.youtube.com/watch?v=JwcR00oGbv0) |
| s_obama_race_2008 | [Barack Obama: 'A More Perfect Union' (Full Speech)](https://www.youtube.com/watch?v=zrp-v2tHaDo) |
| s_trump_inaugural_2017 | [Trump Inauguration Speech (FULL) / ABC News](https://www.youtube.com/watch?v=sRBsJNdK1t0) |
| s_biden_inaugural_2021 | [President Joe Biden 2021 Inaugural Address](https://www.youtube.com/watch?v=UlbyOeMCL0g) |
| s_obama_sotu_2016 | [Watch the full 2016 State of the Union speech](https://www.youtube.com/watch?v=wuI0fP4kc64) |
| s_trump_sotu_2019 | [WATCH: Trump's full 2019 State of the Union address](https://www.youtube.com/watch?v=bYj4cDmilxc) |
| s_biden_sotu_2023 | [Watch President Joe Biden's 2023 State of the Union address](https://www.youtube.com/watch?v=cFxDFq-Cd1Y) |
| s_mlk_dream_1963 | [I Have a Dream speech by Martin Luther King .Jr HD (subtitle](https://www.youtube.com/watch?v=vP4iY1TtS3s) |
| s_thatcher_lady_1980 | [Margaret Thatcher 'the Lady's not for turning'](https://www.youtube.com/watch?v=rQ-M0KEFm9I) |
| s_churchill_finest_hour | [THEIR FINEST HOUR speech by Winston Churchill [BEST SOUND]](https://www.youtube.com/watch?v=6jjhxeHIjvU) |
| s_obama_farewell_2017 | [FULL. Pres. Obama Farewell Speech in Chicago, IL. Jan. 10, 2](https://www.youtube.com/watch?v=CW1HHUCdCDc) |
| s_bernie_dnc_2016 | [Watch Sen. Bernie Sanders’ full speech at the 2016 Democrati](https://www.youtube.com/watch?v=9rtXaPV5SYM) |
| s_michelle_obama_dnc_2016 | [Watch first lady Michelle Obama’s full speech at the 2016 De](https://www.youtube.com/watch?v=4ZNWYqDU948) |
| s_aoc_floor_2020 | [AOC Slams Rep. Yoho In House Floor Speech, Says ‘Having A Da](https://www.youtube.com/watch?v=tSZcdMCHn2o) |
| d_kennedy_nixon_1960 | [Kennedy vs. Nixon: The first 1960 presidential debate](https://www.youtube.com/watch?v=AYP8-oxq8ig) |
| d_reagan_carter_1980 | [Carter vs. Reagan: The second 1980 presidential debate](https://www.youtube.com/watch?v=3HB2sz4bAbU) |
| d_bush_gore_2000 | [Bush vs. Gore: The third 2000 presidential debate](https://www.youtube.com/watch?v=uKDFcOfqGMQ) |
| d_obama_mccain_2008 | [McCain vs. Obama: The first 2008 presidential debate](https://www.youtube.com/watch?v=4b7NfEZWBzw) |
| d_obama_romney_2012 | [Obama vs. Romney: The first 2012 presidential debate](https://www.youtube.com/watch?v=KfaBRyCKRhk) |
| d_trump_clinton_2016 | [Full video: Trump-Clinton first presidential debate](https://www.youtube.com/watch?v=s7gDXtRS0jo) |
| d_trump_biden_2020 | [Trump and Biden face off in chaotic first 2020 presidential ](https://www.youtube.com/watch?v=9HnKFUNlcfY) |
| d_biden_ryan_vp_2012 | [Biden vs. Ryan: The 2012 vice presidential debate](https://www.youtube.com/watch?v=yYcdSwbrErI) |
| d_harris_pence_vp_2020 | [Full Debate: Vice President Mike Pence and Sen. Kamala Harri](https://www.youtube.com/watch?v=Q__CEb3dRqw) |
| d_uk_pmqs | [🔴 PMQs LIVE: Prime Minister's Questions - 11 November 2026](https://www.youtube.com/watch?v=QhPWS-ukOnA) |
