# Statistical analysis plan

Written 2026-11-06, before any real data. Code: `src/anchoring_llms/bidirectional/analysis.py`.

## Measure

For each reply with a number, `z = log(1 + estimate)`. Logs make a move from 20 to 24 count the
same as from 200 to 240, and `1 +` allows 0 (a goalkeeper can make 0 saves). Young et al.'s own
measure, the percentile of an answer among the same entity's baseline (B) answers, is computed
as well and reported as a check.

For every pair, entity and condition, the **cell mean** is the mean `z` over its repetitions
(and both naming orders, where there are two). The **comparison** cell is LT+LA for the low entity
and HT+HA for the high entity.

**Assimilation** of a contrast X − Y = (cell X − cell Y), with the sign flipped for the high
entity, so that a move **towards the other entity is positive** in both directions. 0.10 means
the estimate moved by about 10% towards the partner.

## Contrasts

| Contrast | Question | Role |
| --- | --- | --- |
| comparison − C1 | Does comparing move estimates more than naming both? | **Primary** (H1-H3) |
| comparison − C3 | Does answering the comparison matter beyond seeing it? | Primary for H5 |
| C3 − C1 | Does seeing a comparison, without answering, move estimates? | Secondary |
| comparison − B | The classic contrast with the plain baseline | Secondary |
| comparison − B2 | Against a two-turn baseline of the same length | Secondary |
| C1 − B | Does merely naming the other entity move estimates (priming)? | Secondary |
| C2 − B2 | Does an irrelevant comparison of the names move estimates? | Control |
| first − second named | Order effect within the comparison | Exploratory |
| C4 − B | Numeric anchor (partner's true value) | Exploratory |

## Inference

- **Unit:** the pair. Each pair gives one assimilation value per direction and contrast.
- **Interval:** 95% percentile bootstrap over pairs (2,000 resamples), separately for the low
  and the high direction. Hedges' *g* is reported next to it.
- **Pattern** from the two intervals: *bidirectional* (both above 0), *low only*, *high only*,
  *contrast* (an interval below 0), *equivalent to no effect* (both intervals inside ±0.05, the
  smallest effect of interest), or *no reliable effect*.
- **Converge and common shift:** per pair, `converge` = (low + high) / 2 (the two estimates move
  towards each other) and `common_shift` = (low − high) / 2 (both rise together), bootstrapped
  the same way. A common shift is also what Young et al.'s asymmetry (H4: low moves more) looks
  like, so H4 is read together with C1 − B: if naming alone raises both estimates, the asymmetry
  is a general rise, not stronger anchoring of low items.
- **Check:** a linear mixed model of `z` on condition × role with a random intercept per pair and
  a variance component per entity (statsmodels). It should agree with the bootstrap; if it does
  not, both are reported and the disagreement is discussed.
- **Breakdowns:** by dataset, by domain × metric, by thinking level and by model, each with its
  own intervals. No correction for these, because they are described, not tested.
- **Self-consistency:** comparison effects split by whether the model's turn-1 answer had the
  right order, and by what it said (more / fewer / unsure).
- **Prior strength (H6):** correlation over entities between the spread of the baseline answers
  (and, for open models, candidate-scoring certainty) and the assimilation.
- **Triplets:** for the middle entity, the move after the low partner and after the high partner;
  a two-way pull would show up as up after low **and** down after high.
- **Accuracy:** mean |log error| per condition, to say whether the comparison helps or hurts.

## Exclusions

A reply counts only if it ends with an `Estimate:` line holding one number (the parser reads the
number, and "$4 million" is converted into the question's unit). Refusals, missing lines, cut-off
replies and ranges are excluded and **counted per condition** in the report, because a
condition that makes the model refuse more is itself a finding. As a robustness check, the main
contrasts are repeated **without trials whose turn-1 reply contained numbers** (the model brought
in figures of its own). No other exclusions; no outlier trimming.

## Power

`power.py` simulates the primary test. Each pair's value = effect + pair spread (sd τ) + noise
from sampling (sd σ √(1 / repetitions)). With the placeholder values σ = 0.25 (sd of log answers
within a cell) and τ = 0.10 (spread of the true effect over pairs), about 80 pairs give 80% power
to find **both** directions at an effect of 0.05 with 10 repetitions; bigger effects need far
fewer. These values are guesses: after the pilot, `07_bidir_analyze` reruns the power analysis with
the pilot's σ and τ (`--from-pilot`), and the confirmatory set size is checked against it before
it is run.

## Confirmatory run

The pilot (about 60 pairs) is analysed and written up first. The confirmatory set (about 115
held-out pairs) is then run with the same code and analysed with this plan, without changes. If the
plan has to change, the change and its reason go into `CHANGELOG.md` before the confirmatory data
are looked at.
