# TED ratings model check: analysis charter

Status: draft (development analysis only). Written 2026-11-25, before any TED excerpt was graded.
The held-out split may be graded and analyzed exactly once, after this file says `Status: locked`
in a commit that precedes the first held-out grade. `analyze --split heldout` refuses otherwise.

## Question

Do orator's overall score and per-dimension points track TED viewers' negative delivery ratings?

## Label and covariates

As in `docs/ted-ratings-corpus.md`: `neg_share` (higher = worse rated); covariates
`log10(views)`, `year`, `event_class` dummies.

## Scores tested

`overall_score` and every `<dimension>_points` orator emits in stage mode (fillers, pace,
pauses, prosody and the rest present in the report). Raw metrics (wpm, filler rate and so on)
are reported as diagnostics only, never as verdicts.

## Statistics (per score)

1. Spearman rho of score vs `neg_share`.
2. Primary: partial Spearman, the Pearson correlation of score ranks and label ranks after each is
   residualized on the ranked covariates. Bootstrap 95% CI (2,000 resamples, seed fixed).
3. AUC: talks in the best `neg_share` quartile vs the worst; AUC > 0.5 means the better-rated talks
   score higher.

Expected sign: a score that tracks delivery ratings has a negative partial Spearman (more points,
fewer negative tags).

## Verdict rule (development)

- **tracks**: partial Spearman <= -0.10 and its 95% CI excludes 0.
- **runs backward**: partial Spearman >= +0.10 and its 95% CI excludes 0.
- **no detectable tracking**: anything else. With about 200 development talks, |rho| near 0.20 is
  detectable at 80% power; smaller true effects read as no detectable tracking.

Development verdicts are exploratory. Thresholds, dimensions or label are not changed after seeing
development numbers without a new charter version and a new held-out set.

## Held-out (confirmatory, once)

Same statistics on the sealed held-out talks. A score is confirmed as tracking only if its
held-out partial Spearman is negative with a one-sided Holm-corrected p < 0.05 across the scores
that tracked on development. Lock this charter (any amendments recorded below) before grading.

## Amendments

None.
