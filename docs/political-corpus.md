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

Known limit: slow oratory (Kennedy 1961, Trump SOTU 2019) still lands at "poor" pace against the
130 to 160 wpm conversational band. That band suits presentations, not ceremonial addresses.
There are no "good speaker" labels here, so this sets reference ranges, not a learned model.

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
