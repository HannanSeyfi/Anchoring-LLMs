# Protocol: bidirectional item-based anchoring in LLMs

Design version `bidir-v2` (bidir-v1 written 2026-11-06 before any real data; v2 the same day after
pilot run A: the comparison is now a forced choice, see `CHANGELOG.md`). Changes after this date are
listed in `CHANGELOG.md` with the reason, and the frozen pairs are never edited.

## Question

Young et al. (2026, *Cognitive Psychology* 164, 101796) asked people to compare two **items**
(e.g. a stapler and a moped) and then estimate one of them. Both estimates moved towards the
other item, and low-value items moved more (their pre-registrations are on OSF, project 2a9nz).
We ask the same of LLMs:

> After a model compares entity A with entity B, does its estimate of A move towards B **and** its
> estimate of B move towards A? Or does only one direction move, or neither?

An item anchor differs from the numeric anchors that most LLM work uses: no number is given. If the
estimate moves, the model built the anchor itself from what it believes about the other entity.

## Hypotheses

Each direction is tested on its own (one-sided claims are reported per direction, not pooled).

- **H1 (low direction).** Low entities are estimated higher after the comparison than after a
  co-mention (C1).
- **H2 (high direction).** High entities are estimated lower after the comparison than after C1.
- **H3 (bidirectional).** H1 and H2 both hold. The possible outcomes, decided from the two 95%
  intervals: bidirectional, low only, high only, contrast (a move away), equivalent to no effect
  (both intervals inside ±0.05 log units), or no reliable effect.
- **H4 (asymmetry).** As in people, the low direction is larger than the high direction.
- **H5 (commitment).** Answering the comparison (LT/LA/HT/HA) moves estimates more than seeing it
  without answering (C3), i.e. part of the effect comes from staying consistent with one's own
  earlier answer.
- **H6 (prior strength).** Entities whose baseline answers are more spread out (weaker prior)
  move more. Tested with the spread of the baseline answers and, for open models, the certainty
  from candidate scoring (`08_bidir_confidence`).
- **Exploratory.** Numeric anchors (C4) against item anchors; triplets (does the middle entity
  move up after a low partner and down after a high one); datasets; model size; order of naming;
  whether the turn-1 answer was right.

## Conditions (each trial is a fresh conversation)

The entity whose value is asked is the **target**; the other is the **partner**. System prompt
for every trial: "You are a helpful assistant." Thinking is off for the primary analysis.

| Code | Turns | What the model sees |
| --- | --- | --- |
| B | 1 | The estimate question about the target only |
| B2 | 2 | "Have you heard of *target*? Answer with one word: YES, NO, or UNSURE." then the estimate question |
| C1 | 1 | "*A* and *B* both played in the group stage of the 2026 FIFA World Cup." + estimate question (both orders) |
| C2 | 2 | "Does the name "*A*" contain more or fewer letters than the name "*B*"?" then the estimate |
| C3 | 1 | "Consider the following question, but do not answer it: "*comparison*" Instead, answer this question. *estimate*" |
| LT / LA | 2 | Comparison (low named first / high named first), then estimate the **low** entity |
| HT / HA | 2 | Comparison (high first / low first), then estimate the **high** entity |
| C4 | 2 | "Is the answer to the following question higher or lower than *N*?" where *N* is the partner's true value; then the estimate (numeric phase only) |
| TRI | 2 | Compare the middle entity with the low or the high one, then estimate one of the two |

Example (World Cup 2026, group stage, primary metric):

> **Turn 1.** Did Cape Verde record more, fewer, or the same number of attempts at goal as
> Colombia across their three group-stage matches at the 2026 FIFA World Cup? Answer with one
> word: MORE or FEWER. If you are not sure, give your best guess.
>
> **Turn 2.** How many attempts at goal did Cape Verde record in total across its three
> group-stage matches at the 2026 FIFA World Cup? Give your best estimate as a single whole
> number. Do not look anything up. If you are not sure, still give your best guess instead of
> refusing. End your reply with a final line of the form `Estimate: <number>`

The model's own turn-1 reply stays in the conversation. Turn 1 is a forced choice ("Answer with one word: MORE or FEWER. If you are not sure, give your
best guess."); in v1 it also offered UNSURE. Two comparison wordings (P1 "more /
fewer", P2 "higher / lower") alternate over repetitions, and LT and HA (and LA and HT) share the
same turn 1, so the two entities of a pair see exactly the same comparison.

## Datasets

| Dataset | What | Why | Pairs |
| --- | --- | --- | --- |
| A. World Cup 2026 teams | Attempts at goal, passes, corners, crosses in the three group matches (FIFA match statistics, summed and checked against FIFA's totals) | Ended July 2026, after every tested model's release: the model has no stored answer | 20 per metric; + 20 on tournament totals (robustness) |
| A. World Cup 2026 players | Attempts (forwards), passes (midfielders/defenders), saves (goalkeepers), group stage | Same, with less famous names | 12 per metric |
| A. Winter Olympics 2026 | Total medals per nation (Wikipedia medal table, revision 1376824706) | After cutoff, a different domain | 15 |
| B. World Cup 2022 teams | Attempts and passes, group stage (FIFA) | Before the cutoff but obscure: a weak, possibly stored prior | 6 per metric |
| C. Known facts | Heights of mountains, towers, a waterfall; maximum depths of lakes | The model knows the answers: anchoring should be small | 9 |
| D. Young et al. products | The 8 products and prices of their Experiment 1 (pilot means, GBP) | Direct comparison with the human study | 16 (4 low × 4 high) |

Pairs come from the same competition, metric and scope (and position, for players), with a true
ratio between 1.25 and 3 (rules per dataset in the config), spread over ratio bins and over how
many of the two are famous; one entity is used in at most one or two pairs. 188 pairs and 9
triplets were selected.

## Extension: known-partner pairs (bidir-kp1, exploratory)

Added after runs A and B (see `CHANGELOG.md`). Each pair is one **obscure** item and one
**famous** item of the same kind: 28 mountains (height above sea level) and 28 buildings
(height), values from Wikidata. Example:

> **Turn 1.** Is the height of Long-Bang Trade Plaza (in Taichung, Taiwan) greater or smaller
> than that of the Eiffel Tower? Answer with one word: GREATER or SMALLER. If you are not sure,
> give your best guess.
>
> **Turn 2.** How tall is Long-Bang Trade Plaza (in Taichung, Taiwan)? ...

Same conditions, sampling and rules as above; settings in `configs/bidirectional_kp.yaml`.
Screening also requires the model to know the famous item (baseline median within 10% of the
truth). Predictions: the obscure item moves towards the famous one in both directions; the
famous item hardly moves; C4 with the famous item's value as a number moves the obscure item
about as much as the item does, if the item anchor works through the value the model recalls.

### Two partners per item (bidir-kp2)

Added after the kp1 run, because every control condition moved the estimates by itself (see
`CHANGELOG.md`). Each obscure item is compared once with a taller and once with a shorter famous
item, e.g. Qutani (3,740 m) with Mount Elbrus (5,642 m) and with Mount Vesuvius (1,281 m). The effect is
the estimate after the taller partner minus after the shorter one; anything a condition does by
itself is the same on both sides and cancels. Settings in `configs/bidirectional_kp2.yaml`.

## Rules that keep it honest

1. **No true value in any prompt.** Checked automatically for every trial (`validate.py`);
   only C4 contains a number, the partner's value, by design.
2. **Screening uses baselines only.** Each entity is asked alone 20 times (`05_bidir_screen`).
   A pair is dropped when either entity gives a number in under 80% of replies or refuses in more
   than 20%; post-cutoff pairs are also dropped when the model hits the true value (within 5%) in
   more than half of the replies. No anchoring trial is used to choose pairs.
3. **Frozen before the anchoring runs.** Screening writes `frozen_dataset/` with SHA-256
   checksums; it refuses to overwrite it. Eligible pairs are split there and then into a pilot
   (about 60 pairs, spread over datasets and metrics), the tournament-total robustness set (8)
   and a held-out confirmatory set (the rest). The confirmatory set is run only after the pilot
   analysis is written up.
4. **Fresh conversations, stored in full.** Every reply is saved raw with its parsed number,
   conversation, model, provider, settings and code commit.
5. **No retrieval or tools.** Models answer from what they know.
6. **Simulated data is labelled.** The simulated backend writes only to `*_smoke` folders and its
   report starts with **SIMULATED DATA**.

## Models

Thinking off for all (primary). Qwen3-32B and Qwen3-14B through DeepInfra raw completions
(our own chat template), Llama-3.3-70B and Llama-3.1-8B through DeepInfra's chat endpoint,
Qwen3-8B and Qwen3-4B with vLLM on a Colab GPU. Release dates and stated knowledge cutoffs are in
the config and are saved with every reply. Confidence scoring (Owusu & Feldman's method) runs on
Qwen3-4B (and Qwen3-8B if time allows) with transformers on a Colab GPU, because DeepInfra does
not return the probabilities of a given answer.

## Sampling

Temperature 0.7, top-p 0.95, up to 400 answer tokens. 20 baseline replies per entity (B), 10
repetitions of every other condition per pair (each order for C1-C3). DeepInfra does not take a
seed, so hosted replies cannot be reproduced exactly; the seeds are recorded anyway and are used
by vLLM.
