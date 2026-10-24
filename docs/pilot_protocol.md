# Pilot protocol

The pilot checks that the method works before the main study: that answers can be parsed,
that the reasoning budget really changes how much models think, that the questions are hard
enough to show anchoring, and that the traces can be coded. It is not meant to test the
hypotheses with full power. Settings live in [`configs/pilot.yaml`](../configs/pilot.yaml);
the design follows the [proposal](../latex/proposal/main.tex).

## Design (per model)

**Reasoning levels**: off (0 thinking tokens), low (512), high (2048).

**Baseline.** Each of the 15 Study 1 questions is asked without an anchor, 20 times per level
(900 answers). From these we take the model's own *plausible range*: the 5th to 95th percentile
of its answers, pooled over levels, on a log scale.

**Study 1: provided anchors** (3,600 answers). Each question gets eight anchors:
low or high × near or far × round or precise.
- *Near* anchors sit 0.25 range-widths outside the plausible range, *far* anchors 1 range-width
  outside. Anchors are set per model, from that model's own range.
- *Round* anchors have two significant figures; *precise* anchors are 0.4–2% further out and
  look exact (for example 2,300 vs 2,331).
- The prompt is the classic two-step comparative question: "Is it higher or lower than X?
  Then give your best estimate."
- 10 answers per anchor and level.

What each account predicts:

| Signature | Insufficient adjustment | Selective accessibility |
| --- | --- | --- |
| Far vs near anchors | Answers stop at the edge of the plausible range, so far anchors pull no further than the edge | The whole distribution shifts by a similar proportion |
| Precise vs round | Precise anchors pull harder (smaller adjustment steps) | No difference expected |
| Traces | Start at the anchor and move away step by step | Recall facts that fit the anchor |

**Study 2: self-generated vs provided anchors** (2,700 answers). 15 questions whose natural
starting point is a known value that is wrong (water boils at 100 °C, but not on a mountain;
a year is 365 days, but not on Ceres). The starting point is either left for the model to
generate (*self*) or given in the prompt (*provided*). Crossed with three instructions: none,
"accuracy matters", and "consider the opposite". 10 answers per cell.
Prediction from Epley & Gilovich: more reasoning moves self-generated answers further from the
starting point, but does little for provided ones.

Total: 7,200 answers per model; 14,400 for the two pilot models.

## How long it takes

Most of the cost is the "high" level, at up to 2,048 thinking tokens per answer. Our rough
estimate is 1–3 hours per model on an A100, and longer on an L4. This is a guess: the run prints
its own time estimate after the first batch. Runs can be stopped and resumed at any time.

## Go / no-go checks

Look at `results/pilot/summary.md` after the analysis notebook.

1. **Parsing**: at least 95% of answers give a usable number at every level (section 1).
2. **Budget control**: realised thinking tokens clearly differ between low and high
   (section 1 and `thinking_tokens.png`).
3. **Usable questions**: at least 10 of the 15 Study 1 questions are not memorised, meaning the
   model's unanchored answers vary (section 1, "Items to drop or replace").
4. **Anchoring exists**: with thinking off, the anchoring index is clearly above zero
   (section 2). If there is no anchoring, there is nothing to explain.
5. **Study 2 manipulation works**: in the self condition, traces mention the expected starting
   value (section 6, `mentions_start`). If models do not start from it, the questions need
   changing.
6. **Traces can be coded**: two people code the same 50 traces from `hand_coding_sample.csv`
   as adjusting / retrieving / dismissing / none, and agree well (Cohen's kappa ≥ 0.6).

## What the pilot decides

- Which questions to drop or replace, and how many questions the main study needs.
- Sample sizes for the main study, from the variability seen here.
- Whether R1-Distill's "off" level is usable (see [model choice](model_choice.md)).
- The final coding scheme for traces.

## Before using the data in a paper

The true answers in `data/items/` still need checking against primary sources; see
[`data/items/README.md`](../data/items/README.md).
