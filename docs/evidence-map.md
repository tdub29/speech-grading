# Evidence for orator speech delivery scores and flags

Evidence reviewed 2026-11-17. Code inspected at baseline `f69838b` and in the live
working tree. The 30 political clips are an unlabeled calibration corpus, not a
test of good speaking. Their distribution cannot validate quality cutoffs.

**Decision:** retain existing numeric quality bands as explicitly uncalibrated
heuristics. Do not invent replacements where the literature supplies no compatible
boundary. Keep the six new metrics descriptive. Apply only measurement corrections:
use observed duration for partial WPM windows; suppress interruption-free streaks
when overlap cannot be observed; identify the heuristic rubric in report metadata.

## How to read this map

| Verdict | Meaning |
|---|---|
| supported | Compatible evidence or a mathematical definition supports this specific use, not necessarily an optimal speech-quality cutoff |
| partly | Direction, construct or engineering need has support; the exact number or transfer does not |
| contradicted | Evidence conflicts with the claim made by the rule; this does not automatically identify a better numeric boundary |
| no evidence | No compatible validation of the exact threshold, weight or quality claim found in this review; not proof that the feature never matters |

`Keep heuristic` means preserve the current numeric setting for compatibility,
label it a guess, and do not cite it as an evidence-based optimum. `Descriptive`
means report the measurement without good/bad bands. These recommendations differ
from implementation where a better calibrated value is unavailable.

Evidence keys link to reusable research, with primary citations, study samples,
effects, access depth, moderators and replication limitations:

- **A:** [acoustics](../../skills/speech-delivery-evidence/references/acoustics.md): rate, pauses, fillers, pitch, energy and variation.
- **S:** [structure](../../skills/speech-delivery-evidence/references/structure.md): oral language, questions, signposting, repetition, attention and arrangement.
- **I:** [interaction](../../skills/speech-delivery-evidence/references/interaction.md): turns, gaps, overlap and meeting participation.
- **D:** [datasets](../../skills/speech-delivery-evidence/references/datasets.md): labels, expert rubrics, anxiety, TED and engagement.
- **G:** [grading](../../skills/speech-delivery-evidence/references/grading.md): lexical judgments and calibration design.
- **M:** [existing measurement evidence](../../skills/speech-fluency-measurement/references/sources.md). Its earlier recommendations are superseded where this map or A records a correction.
- **V:** [existing nonverbal evidence](../../skills/nonverbal-confidence-cues/SKILL.md) and its [sources](../../skills/nonverbal-confidence-cues/references/sources.md).
- **C:** [local corpus](political-corpus.md), descriptive and unlabeled.

## Scope and completeness

The inventory covers every first-party runtime module under `speech_grading/`,
including score arithmetic, flag detectors, preprocessing, group mode and optional
visual/acoustic paths. A literal-bearing AST inventory and targeted searches for
constants, comparisons, defaults, thresholds and band mappings were used to expose
hard-coded values outside `Config`. Repeated `.get()` fallback values are covered
by their named setting below. Dependency-internal algorithms are identified as
dependencies, not claimed to be exhaustively audited.

Unit conversions (60 seconds/minute, 100 percent, 12 semitones/octave), array
indices, formatting precision, file extensions, enum names, error-return zeros,
geometry identities and numerical epsilon guards are not empirical quality
thresholds. Their relevant definitions and missing-data behavior are covered below.
UI fonts, colors, licenses, model downloads and process limits do not define speech
quality; limits that censor findings or data are explicitly included.

### Composite score and labels

Source: [config.py](../speech_grading/config.py), [scorer.py](../speech_grading/scorer.py).

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| `DEFAULT_WEIGHTS` | fillers .18; pace .12; pauses .12; word_choice .18; vocabulary .12; hedging .10; readability .06; prosody .12 | A/S/D: no held-out listener-outcome validation of these weights | no evidence | Keep heuristic; report all weights. Do not infer these percentages from perception studies |
| Missing dimensions | Omit dimension and renormalize remaining weights to sum 1 | Arithmetic; M/V support not treating unavailable measurement as a zero | supported | Keep; scores with different available dimensions are not directly equated by evidence |
| `_BAND_POINTS` | excellent 100; good 82; fair 58; poor 28 | No compatible listener calibration | no evidence | Keep heuristic |
| Overall labels | excellent >=90; strong >=78; solid >=65; developing >=50; needs work <50 | No compatible validation | no evidence | Keep heuristic labels, not proficiency certifications |
| Summary focus | Two lowest-point dimensions | Design choice | no evidence | Keep as heuristic prioritization; not proven largest causal improvement |
| Filler bands | rate/100 lexical words: excellent <2; good <4; fair <6; poor >=6 | A: normal disfluency distributions are not listener-quality cutoffs; filled and silent pauses differ | no evidence | Keep 2/4/6 as guesses; contextual description preferred; do not call zero optimal |
| Filler count basis | One lexical or acoustic finding per event; excludes wordchoice source; lexical denominator excludes filled-pause words | A/M; lexicon and acoustic detections can overlap | partly | Keep measurement definition; no evidence acoustic/lexical duplicate counts are independent faults |
| Pause/repair load | Mid-clause long-pause count + .7 times repetition/false-start count, divided by minutes | A/M: repair is less associated with perceived L2 fluency; .7 not estimated from that literature | partly | Keep .7 heuristic; do not use correlation ratios as weights |
| Pause-load bands | excellent <1/min; good <2.5/min; fair <4/min; poor >=4/min | C removed boundary-pause penalties, without listener labels | no evidence | Keep 1/2.5/4 heuristic |
| Pause boundary exclusion | Only rationale starting `Long mid-clause` contributes to load | A/M support location sensitivity; punctuation is an imperfect proxy | partly | Keep; prefer clause annotation if available, not automatic syntactic certainty |
| Hedge-density bands | per100 words: excellent <3; good <6; fair <10; poor >=10 | G01: category/context effects, no density optimum | no evidence | Keep 3/6/10 heuristic; do not reward unjustified certainty |
| Word-choice high severity | finding score >=.6 | No calibrated severity probability | no evidence | Keep .6 heuristic |
| Word-choice bands | No tripped findings: excellent; no high finding and sum<1.5: good; otherwise high count<=2: fair; >2: poor | No length normalization or external quality labels | no evidence | Keep 1.5/2 as guesses; comparisons confounded by talk length |
| Word-choice severity | Sum of tripped finding scores; suggestion count is descriptive | Detector confidence is not validated listener damage | no evidence | Keep heuristic; do not interpret as severity units |
| `rubric_status` | Added `uncalibrated_heuristic`; evidence link `docs/evidence-map.md` | This map | supported | Implemented; no numeric score change from labeling |

### Pace, pauses and drift

Sources: [pace.py](../speech_grading/analysis/pace.py), [pauses.py](../speech_grading/analysis/pauses.py), config.

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| `wpm_ideal_low/high` | 130/160 WPM | A: genre and target outcome vary; descriptive normal rates do not establish optimum | no evidence | Keep 130/160 heuristic; no universal replacement |
| `wpm_fair_low/high` | 110/180 WPM | A; same transfer problem | no evidence | Keep 110/180 heuristic |
| Stage ideal/fair overrides | ideal 110..150; fair 95..170 WPM | C, 20 speeches, no quality labels | no evidence | Keep 110/150/95/170 heuristic; do not call learned quality bands |
| Mode override precedence | Stage band overrides configured pace bounds in pipeline | Engineering behavior, not listener evidence | no evidence | Preserve compatibility; mode is not a validated genre classifier |
| `wpm_window_sec` | 10 s, non-overlapping windows | A: rate variation can be measured, no validated 10-s quality window | no evidence | Keep 10 s as measurement choice |
| Final/short-turn window denominator | Before: full 10 s even for partial windows; after: actual `min(window, remaining span)` | M speech-rate definition: words/time; arithmetic | supported | Implemented observed-duration denominator. Tiny windows remain noisy; no quality cutoff inferred |
| `wpm_gap_cap_sec` | For gaps >2 s remove only excess over2 s from pace clock | C applause robustness, no acoustic applause detector | partly | Keep2 s heuristic; report wall-clock WPM too. A genuine deliberate pause can be removed |
| `wpm_word_cap_sec` | Word durations >1.5 s trimmed to median word duration; excess handled with gap cap | C ASR alignment failure examples | partly | Keep1.5 s heuristic; long words are not automatically applause |
| `wpm_consistency_full/dock` | Window WPM SD<=15 no penalty; >=35 full penalty | A: no compatible SD bands; intentional changes need not be faults | no evidence | Keep15/35 heuristic; use variation descriptively; no validated replacement |
| Pace band logic | Ideal rate + SD<=15 excellent; ideal + greater SD good; fair range fair; outside poor | No joint validation | no evidence | Keep heuristic |
| Pace distance penalty | 50 points at each fair edge, linearly beyond ideal; clamp0..100 | Arbitrary utility mapping | no evidence | Keep50 heuristic |
| Pace consistency penalty | Up to50 points linearly across SD15..35; step50 if span<=0 | No validated causal loss function | no evidence | Keep50 heuristic; do not interpret as measured audience harm |
| `articulation_wpm` | Words/(summed word durations minus held-word overhang) | M distinguishes speech and articulation; ASR word spans are not validated phonation time | partly | Descriptive legacy proxy only; prefer syllables/sec with valid phonation estimate |
| `articulation_sps` | English heuristic syllables/(duration minus gaps>=pause threshold); standalone default .25 s; compute_pace uses configured `pause_micro`=.2 s | M/A define articulation rate; pause floor task/alignment dependent | partly | Keep definition, disclose .2 vs .25 and ASR limits; no quality bands |
| Syllable heuristic | Vowel groups, silent final e exception `le/ee`, minimum1 for letters; no numeric-only syllables | Implementation approximation; claimed ~90% in old comment has no validation supplied | no evidence | Keep as approximate measurement; no score weight or accuracy guarantee |
| SD and drift minimum | SD requires>=2 windows; drift requires>=2, otherwise0; drift=mean(second half)-mean(first half), split floor(n/2) | Arithmetic descriptions, not norm validation | supported | Keep; zero can mean unavailable/too short, not proven steady delivery |
| `pause_micro` | .2 s; gap<.2 ignored | M/A: research pause definitions around200..300ms, task/alignment dependent | partly | Keep .2 measurement convention; no claim of optimal delivery or literal sub-perceptual silence |
| `pause_long` | gap>.7 s flagged, <=.7 not flagged | A/M: location matters; no universal .7-s error threshold | no evidence | Keep .7 heuristic; long boundary pauses may be useful |
| Pause base severity | min(1,.5+gap-.7) | No perceptual calibration | no evidence | Keep .5 offset and linear slope heuristic |
| `long_pause_midclause_weight` | 1.5, severity capped1 | M/A support location distinction, not multiplier | partly | Keep1.5 heuristic |
| Clause proxy | Sentence edge or preceding comma/semicolon/colon; filled-pause punctuation excluded from clause proxy | M/A; ASR punctuation can follow acoustic pause and induce circularity | partly | Keep approximate detector; do not call punctuation verified syntax |

### Fillers, repetition and word-choice flags

Sources: [fillers.py](../speech_grading/analysis/fillers.py), [repetitions.py](../speech_grading/analysis/repetitions.py), [lexicons.py](../speech_grading/lexicons.py), [offline.py](../speech_grading/wordchoice/offline.py).

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| `_FILLED_PAUSE_SCORE` | .95 | A/M: filled pauses have planning/listener functions; not calibrated fault probabilities | no evidence | Keep .95 detector severity heuristic, not95% certainty |
| `_DISCOURSE_SCORE` | .7 for discourse words/phrases | A/I/G: function depends on discourse context | no evidence | Keep .7 heuristic |
| `filler_pause_gate` | Gap>speaker median+.3 s upgrades severity to1 | M/A: delay association, no threshold or harm calibration | partly | Keep .3 heuristic; upgrade does not affect the count-based filler score |
| Filler matching | Phrases longest first, consumed tokens skipped; word `is_filled_pause` or lexicon membership; context rules for ambiguous words | A/M support separating discourse functions; no detector validation | partly | Keep as a candidate detector; function requires context |
| Weak-word selection | Owned tags hedge/weasel/intensifier/weak; that order breaks ties; phrases own hedge/weasel/weak | G01 and code: lexical category membership is not listener harm | no evidence | Keep as heuristic candidate routing, not a semantic verdict |
| Proselint findings | Surface only check names containing `weasel`, `hedg`, `uncomparable` or `redundancy`; map character offset to nearest word; errors return no findings | Dependency rules and local selection, without oral listener validation | no evidence | Keep optional candidate flags; dependency versions can change findings |
| Default finding severity | `Finding.score=1.0` when detector does not supply it, including weak-word/proselint flags | Schema default, not a measured probability or quality effect | no evidence | Preserve compatibility; do not interpret 1 as certainty or maximal listener harm |
| Context `like` gap gates | >median+.25 s OR >.45 s | No labeled precision/recall validation | no evidence | Keep .25/.45 heuristic |
| Other context rules | Initial so/well/okay/ok/anyway/anyways; final right; initial/after-filler like, determiner/comparison exemptions; see never standalone | I/A discourse functions do not establish automatic faults | no evidence | Keep detector heuristic; no uniform coaching penalty justified |
| Immediate repeats | Adjacent equal unigram; equal adjacent bigrams; bigram consumes unigram duplicates | A/S distinguish repairs from rhetorical repetition | partly | Keep detector; repetition is not necessarily accidental |
| Partial-word flags | Trailing hyphen OR prefix length2..4, suffix length1..6, not common-word allowlist | No human-labeled classifier validation | no evidence | Keep2/4/1/6 heuristic; ordinary words can share a prefix |
| Repetition finding severity | Default Finding.score=1 | No measured severity scale | no evidence | Keep1 heuristic |
| Tripped signal weights | hedge .20; vague .15; pause .25; low_conf .20; filled_pause .10; repair .10 | No listener-rated model fitting | no evidence | Keep all six weights heuristic |
| `_pause_norm` |0 at median+.2 s; linear width.8 s;1 at median+1 s | No calibrated word-finding norm | no evidence | Keep .2/.8/1 heuristic |
| `low_conf_threshold` | .5, below threshold contributes (threshold-conf)/threshold; None contributes0 | ASR confidence not calibrated to slurring, comprehension or lexical retrieval | no evidence | Keep .5 heuristic; never diagnose speech ability from recognition confidence |
| `tripped_up_min_score` | .45; offline reads the config value, DEFAULT_THRESHOLDS when unset | No validation; a config override for this key changes the detector | no evidence | Keep .45 heuristic |
| Tripped low-conf config source | Config `low_conf_threshold`, DEFAULT_THRESHOLDS .5 when unset | Code fact | no evidence | Keep .5 default; a config override takes effect |
| Tripped active rationale | Signal>=.5 displayed; output score capped1, rounded3 decimals | Explanation selection, not causal attribution | no evidence | Keep .5 heuristic; a displayed reason is not proven cause |
| Offline suggestion confidence | .6, both single-token and phrase suggestions | Fixed constant, no calibrated confidence | no evidence | Keep .6 heuristic |
| WordNet candidate cap | First6 synsets, single-word alphabetic candidates; keep specificity gain>0; rank by gain then frequency | Norms measure concreteness/frequency, not contextual substitution correctness | no evidence | Keep6 heuristic; require semantic fit before accepting |
| Concreteness/frequency fallback | Built-in table in appendix; no measured provenance for hand-entered values | Nominal scale resembling published norms does not make these observations from those studies | no evidence | Label fallback estimates; do not treat as empirical norms or guaranteed better words |
| External norm table override | Optional CSV overrides fallback; unknown returnsNone; gain0 if either unknown | Engineering definition | supported | Keep missing values; a positive concreteness difference is not general superiority |
| LLM/agent word-choice path | Max1200 input words default; API output cap8000 tokens; valid in-range indices only; failed/empty API falls back offline | Resource/gating choices, no research validation of model judgments | no evidence | Keep limits; results outside cap can be unassessed. No paid calls made in this research |
| Suggestion rendering cap | First25 distinct original strings with suggestions; word-choice kinds only | Display limit, not score threshold | no evidence | Keep25; rendered list is not all findings |
| Lexical tag priority | hedge > weasel > intensifier > weak; lexicon vs wordchoice source separation in scorer | No validated harm ordering | no evidence | Keep as implementation rule; meaning and warranted uncertainty require review |

### Lexical diversity and oral readability

Sources: [vocabulary.py](../speech_grading/analysis/vocabulary.py), [readability.py](../speech_grading/analysis/readability.py).

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| MATTR cutoffs | excellent>=.85; good>=.72; fair>=.60; poor<.60 | S: diversity measurement is not listener-quality calibration | no evidence | Keep .85/.72/.60 heuristic; no reward for needless synonym variation |
| Vocabulary points |100/82/64/45 | No listener-outcome calibration | no evidence | Keep heuristic |
| `_MATTR_WINDOW` |50 tokens; clamp to min(50,total,dependency token count) | S: fixed-window comparison useful; short sample uses different window and is not equivalent | partly | Keep50 measurement setting; no quality norm for samples<50 |
| Short vocabulary cases |0 tokens fair64, metrics0;1 token MATTR/TTR1, MTLD0;>=2 uses dependency | Mathematical degeneracy, not evidence of skill | no evidence | Descriptive/missing preferred; keep existing scoring compatibility, label heuristic |
| Vocabulary token selection | Normalized alphabetic lexical tokens; excludes filled pauses | S/M: preprocessing changes diversity | partly | Keep; compare only compatible tokenization and windows |
| MTLD/TTR | Dependency defaults; error MTLD0, MATTR falls back TTR | S: methods valid for diversity under conditions, not general quality | partly | Keep raw values; error0 is not measured absence of diversity |
| FK grade bands |7..9 excellent100;5..11 outside excellent good92; all else fair80; never poor | S: written readability grade is not oral-comprehension optimum | no evidence | Keep7/9/5/11 and100/92/80 heuristic; use transcript complexity descriptively |
| Readability formulas | textstat Flesch ease, FK grade, SMOG, Fog; exception returns0 | S: formulas have written-text origins; punctuation and short samples distort oral inference | partly | Keep raw text metrics; do not infer listener grade or education requirement |
| Stated versus actual weights | Vocabulary/readability module docstrings say informational/zero; Config actually .12/.06 | Code inspection | contradicted | Treat as scored under defaults. This map and metadata correct the interpretation; no new weights invented |

### Six new metrics: recommended bands

These are measured features, not newly validated scoring dimensions. All six currently
have zero additional score weight. Existing readability/vocabulary scores do not
depend on their new detail fields; anaphora is emitted as a count in scorer metrics.

| Metric | Current detector/value | Evidence | Verdict for a quality band | Recommended bands/action |
|---|---|---|---|---|
| `sentence_length_stats` | Lexical words per punctuation-derived sentence; mean and population SD;>=2 sentences for SD else0; empty0 | S: oral processing depends on syntax, familiarity and prosody, not words alone | no evidence | **No numeric bands.** Show count, mean and SD; compare matched task/person. Sentence-length SD is not rhetorical skill |
| `question_stats` | Sentence-final `?` after stripping quotes/brackets; count/number of sentences; empty0 | S: rhetorical-question effects vary by involvement/argument quality; ASR punctuation does not identify function | no evidence | **No numeric bands.** Show count/share; code rhetorical, information and follow-up functions separately if annotated |
| `detect_anaphora` |>=3 consecutive sentences sharing first normalized non-filler word; one-word opening only | S: rhetorical designs/applause evidence not an ideal count; ordinary pronouns can trigger | no evidence | **No numeric bands.** Keep min_run3 as detector guess, not optimum. Do not confuse repeated first token with tricolon or all anaphora |
| `count_signposts` |10 single tokens +8 phrases, longest matching phrase consumed, rate/100 tokens; exact list below | S: meaningful signaling can aid comprehension; dictionary frequency does not measure appropriate signaling | no evidence | **No numeric bands.** Show count/rate and functional examples; no quota |
| `pace_drift_wpm` | Second-half mean window WPM minus first-half; split floor(n/2);<2 windows0 | A: no compatible optimum or direction; talk sections and partial windows confound | no evidence | **No numeric bands.** Signed WPM difference descriptive; corrected partial windows. Do not reward0 or penalize acceleration automatically |
| `interruption_free_streaks` | Longest run of speaker floor turns without other starts >.2 s before end; count not seconds | I: overlap can cooperate; status/task/opportunity/length confounds | no evidence | **No numeric bands.** Count only with timing+overlap-capable input; otherwise null, implemented. Not a dominance or politeness grade |

### Prosody and acoustic flags

Source: [prosody.py](../speech_grading/analysis/prosody.py).

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| F0 dispersion measure | Population SD of voiced semitones relative to median F0 | A/M; perceived excursion scaling supports semitones | supported | Keep measure; SD is not pitch range or a quality norm |
| `_MONOTONE_EXCELLENT/GOOD/FAIR` |4.0/2.5/1.5 semitones | A: author-assigned liveliness classes and small charisma studies do not validate these boundaries | no evidence | Keep4/2.5/1.5 heuristic; do not call a healthy speaker clinically monotone |
| `_ENERGY_DYNAMIC` | RMS CV .35 | A/M: no compatible listener-rated boundary; linear RMS and silence affect CV | no evidence | Keep .35 heuristic; no evidence for converting a dB study into this cutoff |
| Prosody band logic | excellent if F0SD>=4 and CV>=.35; good if SD>=2.5; fair if SD>=1.5 OR CV>=.35; else poor | No joint model validation | no evidence | Keep heuristic; high variation not universally better |
| Prosody point weighting | Pitch70*min(1,SD/4); energy30*min(1,CV/.35); clamp0..100 | No empirical70/30 contribution estimate | no evidence | Keep70/30 heuristic |
| `_F0_MIN_HZ/MAX_HZ` |50/800Hz pitch tracker and accepted frame range | M Praat supports suitable tracking ranges, not universal healthy-speech bounds | partly | Keep as instrument settings; adapt to speaker/register and inspect errors |
| `_OCTAVE_JUMP_ST` |Discard frames >12 semitones from median | M octave errors exist; this is median-distance gate, not temporal continuity tracker | partly | Keep12 heuristic; genuine wide excursions may be removed |
| F0 minimum material |<2 accepted frames returns(0,0) | No minimum duration validation | no evidence | Preserve scope; missing voicing can currently produce poor prosody rather than abstention, unresolved |
| Energy windowing | All selected audio frames, including silence; RMS CV over span | A/M require compatible voicing/recording normalization | partly | Treat as descriptive proxy; not validated dynamic vocal energy. No replacement cutoff justified |
| Acoustic filler duration | `_FP_MIN_DURATION` .6 s | No measured precision/recall against filler labels | no evidence | Keep .6 heuristic candidate detector |
| Acoustic filler spectral gate | `_FP_MAX_FLUX` .04 after normalization by clip maximum | No compatible validation; depends on signal and clip | no evidence | Keep .04 heuristic; sustained vowels are not necessarily fillers |
| Acoustic voicing gate | RMS>10% of clip peak | Energy is not periodic voicing; no filler classifier calibration | no evidence | Keep .10 heuristic; do not call this a true voicing detector |
| Acoustic filler severity |1, nearest word by midpoint | No calibrated fault probability; potential duplicate lexical finding | no evidence | Keep1 heuristic; explicit acoustic approximation label |
| Librosa framing | RMS/onset hop512 default; spectral flux proxy normalized0..1 | Instrument implementation, no quality cutoff | partly | Preserve reproducibility; normalize consistently before comparisons |
| Onset peak syllable proxy | pre_max3/post_max3/pre_avg3/post_avg5/delta.1/wait3; divide count by summed word spans | M: not the validated intensity+voicing syllable-nuclei algorithm | no evidence | Keep as unvalidated detail only; never substitute for validated articulation measure |
| Prosody availability | Disabled/no audio/video/dependency/pitch read failure: omit dimension | M/V: unavailable is not low quality | supported | Keep abstention. Energy failure currently leaves0 and may lower score, unresolved |

### Group and meeting metrics

Sources: [group.py](../speech_grading/group.py), [schema.py](../speech_grading/schema.py), config.

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| `BACKCHANNEL_MAX_WORDS` |<=2 lexical words | I: backchannel is a sequential function, not a word-count class | no evidence | Keep2 heuristic detector, not gold annotation |
| `BACKCHANNEL_MAX_SEC` |<=1 s | I: no universal boundary | no evidence | Keep1 s heuristic |
| Backchannel context | Bracketed by same other speaker, or contained in another multitrack run; then drop from floor turns | I supports continuers versus turn claims; automatic rule can confuse short answers | partly | Keep contextual candidate detector; manual sequence review for consequential labels |
| `OVERLAP_TOL_SEC` |>.2 s remaining after another speaker's earlier start | I: conversational gap/overlap distributions do not define interruption threshold | no evidence | Keep .2 detector tolerance; no aggression/dominance inference |
| Overlap availability | Timing+multitrack/explicit overlap-capability required for overlap counts | I; single-channel dominant-word diarization loses simultaneous speech | supported | Keep null when unobservable |
| Streak availability | Before timing alone; after timing+overlap capability | Same observation requirement as overlap counts | supported | Implemented null for single-channel/untimed input |
| `TRACK_TURN_GAP_SEC` | Own gap>1 s overlapping another voice starts a new track turn | I: turn completion is sequential, not a fixed silence threshold | no evidence | Keep1 s engineering split; no universal turn boundary |
| `group_min_words` |60 lexical words before grading; shorter speaker listed ungraded | Sample-size noise, no reliability study establishes60 | no evidence | Keep60 heuristic; null/ungraded is not low performance |
| Response latency | Median of adjacent floor-turn change start minus previous end; negative overlap | I: Stivers polar-question transitions are not every meeting turn | partly | Descriptive, no ideal target or universal200ms band |
| Floor share | Sum own turn spans / sum all speakers' spans; untimed fallback lexical word share | Arithmetic definition; I warns opportunity/status/task confounding | supported | Keep descriptive. Overlap means denominator not equal meeting wall time |
| Balance | Shannon entropy divided ln(N), N>=2; otherwiseNone;0..1 | Mathematical normalization only; I/D no universal ideal quality score | supported | Keep as distribution descriptor;1 is even, not necessarily best |
| Longest/median floor turn | Last-word end minus first-word start after backchannel removal | Measurement definition; not quality cutoff | supported | Keep descriptive, no ideal seconds |
| Track synchronization warning | Length difference>1 s | Engineering diagnostic, not a synchrony guarantee | no evidence | Keep1 s warning; synchronized starts still must be true |
| Turn-start pause exclusion | `gap_before`0 at new speaker turns; per-speaker durations sum own turns | M/I: inter-turn gaps differ from within-speaker pauses | supported | Keep; do not score listening time as hesitation |

### Visual cues and quality gates

Sources: [visual_events.py](../speech_grading/analysis/visual_events.py), [visual.py](../speech_grading/analysis/visual.py).
Visual findings are appended after scoring, so these affect flags/descriptors, not
the composite. V is the existing dedicated body of evidence, extended rather than
duplicated here. No geometric threshold below has been externally calibrated.

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| Baseline sample | First30 s, face spans>=10 s | V supports own baseline and camera controls, not30/10 values | partly | Keep30/10 engineering guesses |
| Face quality gate | Face visible>=60% | V: visibility gating needed, exact60 not validated | partly | Keep60 heuristic; skip flags below gate |
| Hands gate `need_hands` |.2 all profiles, i.e.>=20% tracked frames | V: missing hands bias self-touch counts, exact20 not validated | partly | Keep20% engineering guess |
| Face-touch distance | default/zoom/interview .15; phone .20; stage .12, normalized face size | V: no confidence validity; geometry unvalidated | no evidence | Keep .15/.20/.12 as neutral detection guesses |
| Face-touch event persistence | min .4 s, max gap .3 s | V: no validated event classifier | no evidence | Keep .4/.3 heuristic |
| Chin delta threshold |8 degrees except phone10 | V: camera/context confounds, no exact angular fault boundary | no evidence | Keep8/10 neutral detector guesses; camera_level gate required |
| Chin persistence |>=1 s, max gap .3 s | No exact event validation | no evidence | Keep1/.3 heuristic |
| Post-sentence smile | Within .6 s; rise>=.25 except phone .30 | V: no evidence post-sentence smiling signals insecurity | no evidence | Keep .6/.25/.30 as neutral counts, no negative score |
| Mode cue enablement | All modes self-touch/chin; smile disabled on stage | V supports contextual interpretation, not this exact switch | partly | Keep descriptive cue policy |
| Gaze-off thresholds | default .5; zoom .6; phone .5; stage .8; interview .7 | V: camera gaze not direct eye contact or universal confidence | no evidence | Keep .5/.6/.5/.8/.7 engineering guesses |
| `YAW_ON_CAMERA` |abs(yaw)<=25 degrees | V: head angle matters but exact25 not validated | no evidence | Keep25 geometric guess |
| `MIN_RATE_SEC` |60 s before per-minute visual rates; shorter count only | V: denominators/visibility matter; no validated60-s reliability boundary | no evidence | Keep60 heuristic |
| Pose visibility | min landmark visibility .5; pose visible>=30%;>=2 frames | V: occlusion gating needed, exact.5/30/2 not validated | partly | Keep engineering gates |
| Gesture motion |>.5 shoulder widths/sec; frame pair gap<=.5 s | V: meaningful gesture type differs from wrist speed | no evidence | Keep .5/.5 descriptor thresholds, no gesture-quality grade |
| Pose geometry | Shoulder width normalization; signed tilt folded to +/-90 degrees; sway SD | Geometric definitions, not psychosocial inference | supported | Keep neutral measures |
| False hand gate | Wrist and>=75% hand landmarks inside face box removes candidate | Local detector workaround; no external sensitivity study | no evidence | Keep75% heuristic; genuine covered-face touches can be missed |
| Visual extraction |10 FPS; fallback native30 FPS;1 face/2 hands/1 pose | Instrument/resource settings; no validation at this sampling rate | no evidence | Keep10/30/1/2/1 engineering settings |
| Crop recovery |3x face box, min64px; half-size3x3 grid; grid scan each10 sampled frames | Local tracking workaround | no evidence | Keep3/64/3x3/10 engineering settings |
| Feature rows |5-s windows; means per feature | Training export convention, not score norm | no evidence | Keep5 s descriptive |
| Visual event score | Default1; word_index=-1 for unanchored event | Schema convention, not confidence probability | no evidence | Keep flag identity; no score contribution |

### Preprocessing and optional instrument constants

These change who/what reaches the detectors. They are not speech-quality bands.

| Constant or rule | Current value | Evidence | Verdict | Recommended value/action |
|---|---|---|---|---|
| Median gap candidate range |0<gap<3 s | M: ASR/gap uncertainty; no3-s validation | no evidence | Keep3 s baseline heuristic |
| Crowd removal |>=3 repeated interjections, mean available confidence<.5; repeat cleanup to fixed point | C ASR artifacts, no general detector validation | partly | Keep3/.5 heuristic; refrain from interpreting removed words as ground truth |
| Caption removal | Bracketed/parenthetical sound tags; all-caps known tag phrases; optional and/& joins | C preprocessing need; no labeled deletion validation | partly | Keep targeted rule; exact vocabularies below |
| Sentence splitting | Regex sentence-final punctuation; unpunctuated remainder one sentence | S/M: punctuation is ASR-dependent | partly | Keep measurement definition; language structure is not proven by punctuation |
| Text speaker-label parsing | VTT `<v Name>` tags; capitalized `Name:` prefixes of 1 to 3 components count only when that exact name starts at least 2 lines | Local parsing heuristic; no labeled speaker-identification validation | no evidence | Keep 1..3/2 engineering guesses; inspect role labels before interpreting per-speaker metrics |
| Subtitle filtering | Skip `WEBVTT`, lines starting `NOTE`, digit-only lines and any line containing `-->`; remove closing `</v>` tags | Input-format handling rather than speech-quality evidence | partly | Keep; raw speech lines matching these patterns can be lost |
| `has_timing` | any word end>start; duration/speaking sums from cleaned words | Instrument availability rule | partly | Keep; positive span alone does not establish timestamp accuracy |
| Single-mic diarization |16000Hz; WIN1.5 s/HOP.75 s; one dominant speaker label per word | Instrument choice; overlap not resolved | no evidence | Keep as engineering settings, never claim overlap observability |
| `AUTO_THRESHOLD` | Average-link cosine distance .7 estimates speaker count | Code notes one synthetic mix, no held-out DER validation | no evidence | Keep .7 heuristic; external validity unresolved |
| Speaker-count support | Count clusters with>=max(2,.05*windows); at least1 | No labeled reliability calibration | no evidence | Keep2/5%/1 engineering guesses |
| Diarization affinity | Cosine clipped0..1; spectral clustering seed0; known count honored | Algorithm definition, not quality threshold | partly | Preserve reproducibility; no guarantee identities are correct |
| Diarization VAD | min silence300ms; speech pad100ms; discard regions<.3 s | Instrument defaults, no delivery-outcome evidence | no evidence | Keep300/100/.3 engineering settings |
| Embedding frontend |25ms frame/10ms hop (400/160 samples); preemphasis.97; Povey exponent.85; FFT512;80 mel bins;20Hz..Nyquist;int16 scale32768 | Model input convention, not listener-quality norm | partly | Keep exact pretrained-model contract; do not retune as speech quality |
| ASR confidence scale | faster-whisper/vosk clamp0..1; other nonpositive values exponentiated; None retained | Probability-domain conversion is not cross-engine calibration | partly | Keep domain conversion; do not infer comparable .5 accuracy or confidence in speaking |
| Vosk missing confidence | Defaults1; read chunks4000 frames | Backend convention, not observed certainty | no evidence | Keep compatibility; missing confidence is not empirical certainty |
| Default ASR | faster-whisper medium, CPU/int8, language pinned to English; verbatim prompt, word timestamps, previous-text conditioningFalse; VAD off except multitrack | M/A: prompting does not establish verbatim recall or perfect timestamps | partly | Keep instrument settings; treat omitted fillers as unknown, not flawless fluency |
| Input audio extraction |16000Hz mono PCM16 | Instrument standardization, no quality cutoff | partly | Keep; record microphone/compression conditions |
| Optional learned suggestions | Model output confidence unrestricted numeric schema; valid word indices only | D/G: no benchmark here validates this scoring oracle | no evidence | Keep optional; no claim of calibrated confidence |

## Exact lexical constants

Numeric thresholds alone do not cover lexicon-based flags. The following appendix
records the current values of the word/phrase sets, signposts, norms and exemptions.
They are heuristic candidate vocabularies with **no evidence** for treating every
member as a defect. Recommended action: preserve candidates, check function and
meaning, and avoid presenting membership as validated listener harm. A/M/I/G supply
the reasons not to equate a discourse token, hedge or acknowledgment with a fault.

| Constant | Exact current value |
|---|---|
| `speech_grading/lexicons.py:FILLED_PAUSES` | `["ah", "ahh", "er", "erm", "err", "hm", "hmm", "huh", "mhm", "mm", "mmm", "uh", "uh-huh", "uhh", "uhm", "um", "umm"]` |
| `speech_grading/lexicons.py:CONTEXT_FILLERS` | `["anyway", "anyways", "like", "ok", "okay", "right", "see", "so", "well"]` |
| `speech_grading/lexicons.py:is_context_filler.content_prev` | `["feel", "feels", "felt", "look", "looks", "looked", "sound", "sounds", "sounded", "seem", "seems", "seemed", "be", "is", "are", "was", "were", "act", "acts", "acted", "treat", "treats", "'s", "more", "just", "would", "want", "wants", "wanted", "love", "loves", "loved", "like", "likes", "liked", "enjoy", "enjoys", "dislike"]` |
| `speech_grading/lexicons.py:is_context_filler.object_next` | `["a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "our", "their", "him", "them", "it", "us", "you", "me"]` |
| `speech_grading/lexicons.py:DISCOURSE_FILLERS` | `["actually", "basically", "honestly", "literally"]` |
| `speech_grading/lexicons.py:HEDGES` | `["allegedly", "apparently", "arguably", "could", "essentially", "fairly", "kinda", "may", "maybe", "might", "perhaps", "possibly", "presumably", "probably", "quite", "rather", "seemingly", "seems", "somewhat", "sorta", "supposedly"]` |
| `speech_grading/lexicons.py:WEASEL` | `["few", "many", "most", "numerous", "several", "some", "someone", "something", "somewhere", "stuff", "thing", "things", "various"]` |
| `speech_grading/lexicons.py:INTENSIFIERS` | `["absolutely", "completely", "deeply", "definitely", "extremely", "highly", "incredibly", "just", "particularly", "really", "simply", "super", "surprisingly", "totally", "truly", "utterly", "very"]` |
| `speech_grading/lexicons.py:_WEAK_EXTRA` | `["bad", "good", "impactful", "leverage", "nice", "synergy", "utilize"]` |
| `speech_grading/lexicons.py:PHRASE_TAGS` | `{"you know": ["filler"], "i mean": ["filler"], "you see": ["filler"], "let me see": ["filler"], "let's see": ["filler"], "you know what i mean": ["filler"], "sort of": ["filler", "hedge"], "kind of": ["filler", "hedge"], "i think": ["hedge"], "i guess": ["filler", "hedge"], "i suppose": ["hedge"], "i believe": ["hedge"], "i feel like": ["hedge"], "a bit": ["hedge"], "a little": ["hedge"], "more or less": ["hedge"], "to some extent": ["hedge"], "a number of": ["weasel"], "a lot of": ["weasel"], "a couple of": ["weasel"], "in order to": ["weak"], "due to the fact that": ["weak"], "at this point in time": ["weak"], "for all intents and purposes": ["weak"]}` |
| `speech_grading/lexicons.py:REPLACEMENTS` | `{"utilize": "use", "leverage": "use", "in order to": "to", "due to the fact that": "because", "at this point in time": "now", "for all intents and purposes": "effectively", "a lot of": "many", "a number of": "several", "really": "", "very": "", "just": "", "actually": "", "basically": "", "literally": "", "honestly": "", "simply": "", "kind of": "", "sort of": "", "kinda": "", "sorta": "", "maybe": "", "perhaps": "", "i think": "", "i guess": "", "i mean": "", "you know": "", "things": "(name them)", "thing": "(be specific)", "stuff": "(be specific)", "nice": "(use a precise adjective)", "good": "(use a precise adjective)", "bad": "(use a precise adjective)", "impactful": "(say the actual effect)"}` |
| `speech_grading/analysis/repetitions.py:_COMMON_WORDS` | `["a", "all", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for", "from", "go", "have", "he", "her", "him", "his", "how", "i", "if", "in", "is", "it", "its", "let", "me", "my", "no", "of", "on", "or", "our", "out", "see", "she", "so", "than", "that", "the", "them", "then", "they", "this", "to", "too", "up", "us", "use", "want", "was", "way", "we", "well", "were", "who", "why", "win", "with", "yes", "yet", "you", "your"]` |
| `speech_grading/analysis/vocabulary.py:SINGLE` | `["consequently", "finally", "first", "furthermore", "however", "meanwhile", "nevertheless", "second", "therefore", "third"]` |
| `speech_grading/analysis/vocabulary.py:PHRASES` | `[["on", "the", "other", "hand"], ["as", "a", "result"], ["for", "example"], ["for", "instance"], ["in", "conclusion"], ["in", "summary"], ["to", "summarize"], ["in", "addition"]]` |
| `speech_grading/schema.py:_TAG_WORDS` | `["applause", "booing", "chanting", "cheering", "cheers", "crosstalk", "inaudible", "laughs", "laughter", "music", "silence"]` |
| `speech_grading/schema.py:_CROWD_SOUNDS` | `["aah", "ah", "hey", "oh", "ooh", "whoo", "woo", "wooo", "wow", "yay", "yeah"]` |
| `speech_grading/norms.py:_BUILTIN_CONCRETENESS` | `{"thing": 1.4, "things": 1.4, "stuff": 1.6, "something": 1.3, "aspect": 1.6, "factor": 1.7, "issue": 1.8, "area": 2.4, "way": 1.8, "part": 2.3, "nice": 1.6, "good": 1.7, "bad": 1.8, "great": 1.9, "important": 1.6, "data": 2.6, "result": 2.2, "report": 3.6, "document": 4.0, "chart": 4.4, "dashboard": 4.2, "model": 3.2, "budget": 3.3, "deadline": 3.0, "dog": 5.0, "table": 4.9, "car": 4.9, "house": 4.9, "money": 4.4}` |
| `speech_grading/norms.py:_BUILTIN_FREQ` | `{"thing": 4.6, "things": 4.5, "stuff": 4.0, "good": 5.1, "nice": 4.3, "data": 3.4, "report": 3.3, "document": 2.9, "model": 3.1, "budget": 2.9, "use": 4.6, "many": 4.5, "because": 4.9, "now": 5.2, "several": 3.3}` |

`FILLERS` is the union of FILLED_PAUSES, CONTEXT_FILLERS and DISCOURSE_FILLERS.
`WEAK` is the union of HEDGES, WEASEL, INTENSIFIERS and _WEAK_EXTRA.
`MAX_PHRASE_LEN` is 5 tokens, derived from PHRASE_TAGS.
The signpost PHRASES list has 8 entries; SINGLE has 10. These lists detect lexical matches, not discourse function.

## What changed and what remains

Implemented changes have regression tests in `tests/test_evidence_calibration.py`.
All earlier tests retain their original expectations. Numeric quality bands,
weights, pause/filler penalties and visual thresholds were not re-tuned.

The partial-window correction changes consistency and drift, and can change pace
points and the composite. WPM over the whole effective speech clock is unchanged.
Streak gating changes an unavailable measurement to null, with no score effect.
Metadata labels the rubric and adds no score effect. Fixed-input results and suite
status follow below.

### Fixed-input behavior and tests

Compared the baseline pace module at `f69838b` with the corrected implementation,
using the same current pipeline and default Config for both. Only `_window_wpms`
was swapped in memory; no working-tree checkout or real-index operation was used.
These are deterministic implementation comparisons, not listener-quality evidence.

| Input | Pace points before / after | Composite before / after | Window WPM SD before / after | Drift WPM before / after |
|---|---|---|---|---|
| `tests/fixtures/sample_transcript.json` | 50.000 / 97.678 | 53.0 / 59.5 | 36.986 / 15.929 | -63.00 / -20.49 |
| 50 synthetic lexical words, each .5 s, total 25 s | 41.789 / 75.000 | 73.4 / 77.9 | 28.284 / 0.000 | -30.00 / 0.00 |

Only pace points moved. Pace bands remained good and fair, respectively; every
other dimension's points/band stayed unchanged on these inputs. Whole-clock WPM
did not change. Scores can move either way on other inputs because a partial
window now uses its observed duration. No real political-corpus regrade or claim
of improved human-rating accuracy is made.

Requested full suite: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`,
run from speech-grading on 2026-11-17, exit 0. Collection confirmed 154 tests,
including four new measurement/metadata regressions. No prior test expectations
were changed. The streak test covers both unavailable and overlap-capable states.

Unresolved: no validated genre-specific replacement bands; no expert labels for the
political corpus; no causal validation of the composite; clause/punctuation and ASR
errors; acoustic filler precision/duplicates; absent-voicing/failed-energy scoring;
short-window rate uncertainty; shared-channel overlap; and role/culture/gender/status
confounds. These are explicit limitations, not silently passed validation.

## Primary bibliography for standalone copies

The workspace links above hold the full study ledger, including sample units,
effects, access depth and limitations. This compact index keeps the evidence
citations usable in a speech-grading-only clone. A source supports only its stated
construct and population, not every threshold in the corresponding topic. All
links were reviewed on 2026-11-17; instrument documentation is a definition source.

| Key used above | Primary sources and reviews supporting the stated distinction |
|---|---|
| A: rate and genre | [Kim, Allen and Preiss 2019, rate-persuasion meta-analysis](https://doi.org/10.22158/csm.v2n1p1); [Guyer et al. 2025, vocal speed and message processing](https://doi.org/10.1007/s10919-024-00477-6); [Tauroza and Allison 1990, genre rate distributions](https://doi.org/10.1093/applin/11.1.90) |
| A/M: pause, repair and fluency | [Suzuki, Kormos and Uchihara 2021, L2 fluency meta-analysis](https://doi.org/10.1111/modl.12706); [Kahng 2018, pause location](https://doi.org/10.1017/S0142716417000534); [Gao, Sun and Li 2025, criterion-dependent pause floors](https://doi.org/10.1177/02655322251315792) |
| A/M: filled pauses | [Christenfeld 1995, listener judgments after filler editing](https://doi.org/10.1007/BF02175503); [Corley and Hartsuiker 2011, temporal-delay experiment](https://doi.org/10.1371/journal.pone.0019792); [Muhlack et al. 2021, recall replication](https://doi.org/10.21437/Interspeech.2021-1056) |
| A/M: prosody | [Rosenberg and Hirschberg 2009, charisma from speech and text](https://doi.org/10.1016/j.specom.2008.11.001); [Niebuhr et al. 2018, investor-pitch impressions](https://doi.org/10.21437/SpeechProsody.2018-73); [Praat pitch instrument documentation](https://www.fon.hum.uva.nl/praat/manual/Sound__To_Pitch__filtered_ac____.html) |
| A: timing variation | [Kayser et al. 2015, temporal irregularity and recognition](https://doi.org/10.1523/JNEUROSCI.2243-15.2015) |
| S: oral complexity and diversity | [Rubin 2012, listenability](https://doi.org/10.1080/10810730.2012.712622); [Covington and McFall 2010, MATTR](https://doi.org/10.1080/09296171003643098); [McCarthy and Jarvis 2010, lexical-diversity validity](https://doi.org/10.3758/BRM.42.2.381); [Ayasse et al. 2021, syntax and listening](https://doi.org/10.3389/fpsyg.2021.629464) |
| S: questions and signaling | [Petty et al. 1981, rhetorical questions and involvement](https://doi.org/10.1037/0022-3514.40.3.432); [Chaudron and Richards 1986, lecture discourse markers](https://doi.org/10.1093/applin/7.2.113); [Alpizar et al. 2020, multimedia signaling meta-analysis](https://doi.org/10.1007/s11423-020-09748-7) |
| S: repetition, arrangement and attention | [Heritage and Greatbatch 1986, political rhetorical formats](https://doi.org/10.1086/228465); [Aristotle, Rhetoric Book III](https://classics.mit.edu/Aristotle/rhetoric.mb.txt); [Wilson and Korn 2007, attention-limit review](https://doi.org/10.1080/00986280701291291); [Welhaf et al. 2022, retrieval-question conceptual replication](https://doi.org/10.1186/s41235-022-00372-y) |
| I/M: turns, gaps and overlap | [Sacks et al. 1974, turn allocation](https://doi.org/10.2307/412243); [Schegloff 2000, overlap organization](https://doi.org/10.1017/S0047404500001019); [Stivers et al. 2009, polar-question response timing](https://doi.org/10.1073/pnas.0903616106); [Heldner and Edlund 2010, timing distributions](https://doi.org/10.1016/j.wocn.2010.08.002) |
| I: listening and confounds | [Bavelas et al. 2000, listeners as co-narrators](https://doi.org/10.1037/0022-3514.79.6.941); [Anderson and Leaper 1998, interruption meta-analyses](https://doi.org/10.1023/A:1018802521676); [Karpowitz et al. 2012, institutional participation](https://doi.org/10.1017/S0003055412000329); [Seuren et al. 2021, video-call latency](https://doi.org/10.1016/j.pragma.2020.11.005) |
| I: group equality | [Woolley et al. 2010, turn-count association](https://doi.org/10.1126/science.1193147); [Bates and Gupta 2017, divergent task results](https://doi.org/10.1016/j.intell.2016.11.004); [Blanchard et al. 2025, dyadic task evidence](https://doi.org/10.1186/s41235-025-00655-0); [Riedl et al. 2021, group-process synthesis](https://doi.org/10.1073/pnas.2005737118) and [2022 correction](https://doi.org/10.1073/pnas.2204380119) |
| D: labels and engagement | [Schreiber et al. 2012, PSCR](https://doi.org/10.1080/03634523.2012.670709); [Chen et al. 2016, multimodal automated scoring](https://doi.org/10.18608/jla.2016.32.13); [Guo et al. 2014, MOOC viewing engagement](https://doi.org/10.1145/2556325.2566239) |
| G: lexical judgments | [Hosman and Siltanen 2006, powerful/powerless language forms](https://doi.org/10.1177/0261927X05284477) |
| V: perceived versus actual cues | [Hall et al. 2005, nonverbal verticality meta-analysis](https://doi.org/10.1037/0033-2909.131.6.898); [DePaulo et al. 2003, deception-cue meta-analysis](https://doi.org/10.1037/0033-2909.129.1.74) |
