# Changelog

What changed in the pilot design and code, and why. The first question set and its data stay
as they were (`configs/pilot.yaml`, `data/items/`, `data/pilot/`), so earlier runs can still be
reproduced.

## Bidirectional study: known-partner pairs (design bidir-kp1, 2026-11-06)

- **Why:** in runs A and B (Qwen3-32B) two World Cup 2026 teams did not anchor each other: the
  model knows neither value, ranked the pairs at chance (55% right) and, from its own baselines,
  had them in the wrong order 59% of the time. A given number did move it (C4: 42% of the way).
  Products did move when compared with products whose price the model knows. The account to
  test: an item works as an anchor only when the model knows roughly what the partner is worth.
- **What:** a new set of 56 pairs, each one obscure item and one famous item of the same kind:
  28 mountains (height above sea level, e.g. Mount Burwell in British Columbia vs the
  Matterhorn) and 28 buildings (height, e.g. a skyscraper in Taichung vs the Eiffel Tower). 26
  famous items, each used at most 4 times; true ratio 1.3-3; the obscure item is the lower one in
  33 pairs and the higher one in 23. Values from Wikidata
  (`data/bidirectional/raw_sources/known_partner/`); built by
  `python -m anchoring_llms.bidirectional.known_partner`. Settings:
  `configs/bidirectional_kp.yaml`, the same design as bidir-v2 (forced choice) with its own
  paths (`data/bidirectional/known_partner/`, `runs_kp/`, `results/bidirectional_kp/`).
- **Screening rule added:** the famous item's baseline median must be within 10% of its true
  value (the model must know it), and the obscure item may be "known" in at most half of the
  replies. Every eligible pair is run (no held-out set: this is an exploratory extension).
- **Predictions, written before any known-partner data:** the obscure item moves towards the
  famous one in both directions (up when the famous one is higher, down when it is lower); the
  famous item hardly moves. C4 gives the same value as a plain number, so item and numeric
  anchors with the same value can be compared directly.
- **Analysis addition:** a "Known partner" table in the report, each contrast split by whether
  the estimated item is the obscure or the famous one.
- **Not changed:** the main pairs, their split, and the main study's runs.

## Bidirectional study: forced-choice comparison (design bidir-v2, 2026-11-06)

- **What happened** (pilot run A, Qwen3-32B, 14,250 answers, `configs/bidirectional_v1.yaml`):
  the turn-1 comparison offered MORE, FEWER or UNSURE. The model answered UNSURE in 66% of the
  World Cup 2026 comparisons and 95% of the Olympics comparisons, so for the main dataset it
  usually never committed to a direction, and there was nothing to anchor on. Young et al.'s
  participants had to choose.
- **Change:** turn 1 offers only the two directions ("Answer with one word: MORE or FEWER. If
  you are not sure, give your best guess."); the same for C4 and the triplets. B, B2, C1, C2 and
  C3 are unchanged. Trial ids change with the design version, and v2 data go to
  `data/bidirectional/runs_v2/` and `results/bidirectional_v2/`.
- **Not changed:** the frozen pairs and their split (screening used only baselines), the
  analysis plan, the rules. Pilot run A stays in `data/bidirectional/runs/` and
  `results/bidirectional/` and is reported as it is.
- **Analysis addition** (both versions): per pair, `converge` = (low + high) / 2, how much the two
  estimates move towards each other, and `common_shift` = (low − high) / 2, how much both rise
  together. In run A, naming a second team raised both teams' estimates by about 0.66 log units
  against the plain baseline; signed towards the partner, such a rise looks like "low towards,
  high away", so it now has its own number.

## New study: bidirectional item-based anchoring (2026-11-06)

- **What:** a separate study (`configs/bidirectional.yaml`, `src/anchoring_llms/bidirectional/`,
  notebooks 05-08, `docs/bidirectional/`). The pilot question sets and their data are unchanged.
- **Why:** the professors asked for an established, citable design. Young et al. (2026) found in
  people that comparing two items pulls both estimates together; no LLM work we found tests that.
- **Data:** World Cup 2026 group-stage team and player statistics (FIFA), Winter Olympics 2026
  medals (Wikipedia), World Cup 2022 team statistics, known facts, and Young et al.'s 8 products.
  188 pairs and 9 triplets, chosen before any model was asked.
- **Code changes shared with the pilot:** `chat_prompt` takes a whole conversation (needed for
  two-turn trials); a new `openai_chat` backend for Llama models on DeepInfra's chat endpoint;
  `scipy`, `statsmodels` and `tabulate` are now dependencies.

## Box-office answers in words, and an index of every question (2026-10-31)

- **What happened:** the 2026 film questions ask for "million US dollars". When a reply wrote
  "Estimate: $400 million", the parser multiplied by a million and saved 400,000,000. This hit
  172 screening answers and 148 Study 2 answers of R1-Distill-Qwen-1.5B (Qwen3-32B wrote plain
  numbers). The reports already corrected it by hand; the code did not.
- **Fix** (code only): `parse_estimate` takes the question's unit; when the unit is already in
  thousands, millions or billions, a scale word on the Estimate line is converted into that unit
  ("$400 million" = 400, "$1.2 billion" = 1,200). Every new record also stores `unit`.
  Saved data is not rewritten.
- **Index:** `scripts/build_index.py` writes `index/`: every question with its set, source and
  the experiments that asked it, and every answer per question with the saved number and the number
  re-read with today's rules (`estimate_checked`).

## Replies without an "Estimate:" line are no answer (2026-10-30, before Study 1 v2)

- **What happened:** in pilot run 1, R1-Distill-Qwen-1.5B with thinking off left out the
  "Estimate:" line in 274 of 300 baseline replies and 877 of 1,200 Study 1 replies. The parser then
  took the last number in the reply, which was often the anchor repeated back ("Liechtenstein has
  about 121,100 people. This is lower than 192,880,557" was read as 192,880,557) or a year from a
  refusal ("as of 2024"). That makes the small model look more anchored than it is, and the
  refusal years also widen the range the anchors are placed from.
- **Fix** (`parsing.fallback: false` in `configs/pilot_v2.yaml`): a reply without an "Estimate:"
  line counts as no answer. Qwen3-32B wrote the line in all 1,800 Study 2 replies, so its data is
  unchanged. Pilot run 1 and its config stay as they were. Expect R1-Distill-1.5B to give few
  answers with thinking off; the analysis reports that as its format rate.

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
