# Changelog

What changed in the pilot design and code, and why. The first question set and its data stay
as they were (`configs/pilot.yaml`, `data/items/`, `data/pilot/`), so earlier runs can still be
reproduced.

## Question set v2 (2026-10-26)

Follows the "Changes to the design" in the pilot run 2 report (`latex/qwen3_report/`).
Settings: `configs/pilot_v2.yaml`. Steps: `docs/pilot_v2.md`.

### New questions the models do not know

- **Why:** Qwen3-32B knew 13 of the 15 Study 1 questions (anchoring index 0.00-0.05), so the
  anchors had nothing to pull, and it knew the Study 2 answers too, so Study 2 could not be tested.
- 206 new candidate questions in `data/items_v2/` (137 for Study 1, 69 for Study 2), every true
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
