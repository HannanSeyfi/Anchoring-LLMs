# Pilot questions (first question set)

Used by `configs/pilot.yaml` in pilot runs 1 and 2. Question set v2, with questions the
models do not know, is in [`data/items_v2/`](../items_v2/README.md).

Two files, 15 questions each. Every question asks for a single number.

| File | Used in | Columns |
| --- | --- | --- |
| `study1_provided.csv` | Baseline and Study 1 (anchors given in the prompt) | `item_id, question, unit, truth, integer, domain, truth_note` |
| `study2_self_anchor.csv` | Study 2 (self-generated vs provided anchors) | as above, plus `reference`: the familiar value a solver naturally starts from |

`integer` marks counts (stations, steps, people), so anchors for them are whole numbers.

**Study 1** questions are factual quantities that models are unlikely to know exactly, spread
from tens to hundreds of thousands so that anchors cover several orders of magnitude.
Questions that a model turns out to know exactly are flagged by the analysis and dropped.

**Study 2** questions each have a well-known but wrong starting point (`reference`): 100 °C for
boiling water at altitude, 365 days for an orbit, 37 °C for an animal's body temperature, and
so on. The physics answers are computed by `scripts/compute_physics_answers.py`
(standard atmosphere and the Antoine equation).

## Status of the true answers

The `truth` values come from commonly cited figures and have **not yet been checked against
primary sources**; `truth_note` says where to check each one. They matter only for Study 2's
adjustment measure and for reporting accuracy; anchors in Study 1 are placed from each model's
own answers, not from the truth. Check them before the main study.
