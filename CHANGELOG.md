# Changelog

What changed in the pilot design and code, and why. The first question set and its data stay
as they were (`configs/pilot.yaml`, `data/items/`, `data/pilot/`), so earlier runs can still be
reproduced.

## DeepInfra rate limits (2026-10-28)

- **What happened:** the first Study 2 run of `qwen3-32b` stopped before any answer was saved
  with "DeepInfra did not answer after 7 tries (HTTP 429)". 429 means "too many requests": the run
  sent 32 requests at once and gave up after about two minutes of retrying.
- **Fix** (code only, no change to the design or the data): at most 8 requests are open at once
  (`api.workers`, notebook setting `WORKERS`, `--workers`). On a 429 every request pauses (for the
  server's Retry-After when given, else 10 s doubling to 2 min), the number open is halved, and it
  grows back slowly. 429s are retried for up to 30 minutes (`api.rate_limit_wait_seconds`) instead
  of 6 tries.

## Study 2: thinking must move the answer (2026-10-26, evening)

- **What the second screening found** (162 Study 2 questions): Qwen3-32B gave a number for every
  2026-event question (no refusals), but it cannot know whether a 2026 number went up or down, so
  it guessed in either direction (Germany's 2026 Winter Olympics golds: 16; 2022: 12; true 8), and
  adjustment towards the truth says little there. The 15 questions the rules picked were all
  little-known asteroids where the median stayed at about 365 days with and without thinking: the
  model knows nothing about them, so thinking has nothing to work with and could not show an effect.
- **New rule** `screening.study2.min_thinking_gain: 0.2`: with thinking low, the median must get
  closer to the true value by at least 0.2 in adjustment units (|1 − adjustment| shrinks by 0.2;
  going far past the truth counts as moving away). Study 2 questions are now ranked by this gain.
  10 questions pass (Itokawa, Bennu, 4 near-Earth asteroids, 2 films, 2 medal counts), so
  `study2.n_items` is 10. Study 1 is unchanged.
- **For the paper:** this rule was added after seeing the data, and it picks questions where
  unanchored answers improve with thinking, so the Study 2 questions are by construction ones where
  thinking can help. The test that matters is whether thinking helps the same way when the starting
  value is given in the prompt (provided anchor), which the rule did not look at.

## Study 2 questions about 2026 events (2026-10-26, evening)

- **Why:** a model cannot know a number from an event that happened after it was trained, so it
  has to estimate, and the same number from the previous edition is a natural starting value
  (Hannan's idea). Every model we use was released before May 2025.
- `data/items_v2/candidates_study2_events.csv` adds 39 Study 2 questions (`C2-201` to `C2-239`):
  the 2026 World Cup (4), the 2026 Winter Olympics (10), the 2026 Asian Games (7), the 2026
  Commonwealth Games (6) and the worldwide box office of 12 films from 2025-2026, each with the
  previous edition or film as `reference`. Every value is from Wikipedia (2026-10-26), and every
  new value is at least 15% away from the previous one ([notes](data/items_v2/README.md)).
- Each question ends with "This happened after your training data ends, so you will need to
  estimate.", so that the models give a number instead of saying they cannot know. The screening
  will show how often they still refuse.
- No code changes: screening again only asks the new questions, and the Study 1 picks stay the
  same.

## Screening results and a rule change (2026-10-26, later the same day)

- **What the screening found** (`results/screen_v2/screening.md`): Qwen3-32B knew most candidates
  (94 of 137 Study 1 questions, 57 of 69 Study 2 questions), usually giving the same number every
  time. What it did not know were numbers it has to work out or estimate: distances between cities,
  the windows of Versailles, small details such as the area of Lake Bled. In Study 2 it went
  straight to the true value instead of starting from 365 days, 100 °C and so on, except for two
  asteroid orbits (Itokawa: about 369 days with thinking off, about 540 with thinking; true 557).
- **Rule change:** R1-Distill-Qwen-1.5B refuses to answer about half the time with thinking off,
  whatever the question ("I cannot answer that question"), so its number rule is now checked only
  with thinking on (`screening.other_models_parse_levels`). The Study 1 spread rule now uses the
  spread averaged over the two levels instead of the smaller one. With these rules 23 Study 1
  questions pass and 15 are picked; before, 2 passed. The rules were changed after seeing the
  data, so the paper should say so.
- **Study 2** had only 2 usable questions, so `run --phase` now takes a list
  (`baseline,anchors,study1` runs Study 1 only), and the notebooks use that by default.
- **New Study 2 candidates:** the only questions where Qwen3-32B stayed near the starting value
  without thinking were near-Earth asteroids (Itokawa: 369 days, true 557; Bennu: 367 days, true
  436.65; both close to the truth with thinking). `data/items_v2/candidates_study2_neo.csv` adds 54
  little-known near-Earth asteroids (orbital periods from Wikipedia, each checked against Kepler's
  third law). Screening them again only asks the new questions.
- **Study 2 rules:** knowledge is now checked only with thinking off (`study2.known_levels`), since
  reaching the true value after thinking is what Study 2 looks for, and there is no topic limit
  for Study 2 (`max_per_domain: 15`).

## Question set v2 (2026-10-26)

Follows the "Changes to the design" in the pilot run 2 report (`latex/qwen3_report/`).
Settings: `configs/pilot_v2.yaml`. Steps: `docs/pilot_v2.md`.

### New questions the models do not know

- **Why:** Qwen3-32B knew 13 of the 15 Study 1 questions (anchoring index 0.00-0.05), so the
  anchors had nothing to pull, and it knew the Study 2 answers too, so Study 2 could not be tested.
- 206 new candidate questions in `data/items_v2/` (137 for Study 1, 69 for Study 2; 93 more were added later), every true
  value checked against Wikipedia and documented ([notes](data/items_v2/README.md)).
- New step **screening**: `anchoring_llms.screen` asks each candidate 20 times with thinking off
  and 20 times with low thinking, without an anchor, and saves the answers to `data/screen_v2/`.
- `anchoring_llms.select_items` picks 15 + 15 questions that Qwen3-32B does not know and is unsure
  about, checks that every model answers them with a number, and writes `data/items_v2/study1.csv`,
  `study2.csv` and a report `results/screen_v2/screening.md`.
- New notebook `notebooks/04_screen_questions.ipynb`. Notebooks 01, 02 and 03 have a new setting
  to choose question set v2 (the default) or the first set; v2 data goes to `data/pilot_v2/`
  and its results to `results/pilot_v2/`.

### Pipeline fixes

| Change | Why |
| --- | --- |
| Answer limit 512 → **1,536** tokens (`sampling.answer_max_tokens`) | With thinking off, Qwen3-32B often worked the answer out step by step in its reply, and 16% of its Study 2 replies were cut off before the estimate. |
| A reply cut off at the answer limit without an `Estimate:` line now counts as **no answer** (`parsing.fallback_when_cut_off: false`) | The last number of a cut-off reply is usually a step of a calculation, not the estimate. |
| Study 2 summaries use the **median over questions** (with a bootstrap interval) instead of the mean | A few wrong answers gave single questions adjustment scores far outside 0-1 and dominated the mean. |
| Anchors at least **1.5× (near) and 5× (far)** away from the model's median answer (`study1.min_factor`) | When a model gives almost the same answer every time, its plausible range is tiny and anchors placed from the range alone sat almost on its answer. |
| Plausible range from the **10th-90th** percentile instead of 5th-95th (`study1.range_quantiles`) | The 5% and 95% edges rest on the 3 most extreme of the 60 baseline answers, so a single odd answer could move them. |
| Optional **"Wait" extension** (`thinking_min_tokens`, off by default) | With high thinking (2,048 tokens), Qwen3-32B used only about 900 tokens on Study 1, so "high" was not much more thinking than "low". When switched on, "Wait," is added when the model stops early, at most 3 times (Muennighoff et al., 2025). |
| New column `waits` in the data; new `answer_cut_off_rate` in the data-quality table | To see how often each of the above happens. |

### Size ladder

- `qwen3-14b` added (DeepInfra, $0.12 / $0.24 per million input / output tokens, checked
  2026-10-26), so the Qwen3 ladder 4B (Colab T4), 8B (Colab A100 or L4), 14B and 32B (DeepInfra)
  can all run on the same questions.
