# Manuscript outline

Working title: *Do LLMs Anchor on Items? Testing Bidirectional Item-Based Anchoring in Large
Language Models*. Target: a short (4-page) or long (8-page) ACL-style paper, decided after the pilot.
Every number in the paper comes from `results/bidirectional/` and is traceable to a table there.

1. **Introduction.** Anchoring in people and in LLMs; nearly all LLM work gives a number. Young et
   al. (2026) showed that comparing two items pulls both estimates together in people. Question:
   does an LLM do the same, in both directions, when it must supply the anchor itself?
   Contributions (as in [literature.md](literature.md), after the novelty search).
2. **Related work.** Numeric anchoring in LLMs (SynAnchors, AnchorBench, Lou & Sun, thinking
   budgets), confidence and anchoring (Owusu & Feldman), entity-comparison biases (Lehmann et al.),
   item-based anchoring in people (Young et al.).
3. **Method.** Datasets A-D with sources and checks (Table 1: entities, pairs, metrics). Conditions
   with literal prompts (Figure 1: one conversation per condition). Screening and freezing.
   Models and settings. Measure and analysis plan.
4. **Results.**
   - 4.1 Main result: comparison − C1 for the low and the high direction (Figure 2: the contrasts
     plot; Table 2: means, intervals, patterns).
   - 4.2 Where the effect comes from: C3 − C1 and comparison − C3 (commitment); C1 − B and
     C2 − B2 (priming and an irrelevant comparison).
   - 4.3 Asymmetry: low vs high (Young et al.'s prediction).
   - 4.4 Datasets: post-cutoff vs obscure vs known items; Young's products vs the human results.
   - 4.5 Prior strength and confidence (Figure 3: spread / certainty vs assimilation).
   - 4.6 Models: size and family.
   - 4.7 Exploratory: numeric anchors (C4), triplets, naming order, turn-1 correctness.
5. **Discussion.** What the pattern says about how LLMs answer comparisons (self-consistency vs
   accessibility); what it means for users who ask a model to compare things before asking for a
   number; limits ([limitations.md](limitations.md)).
6. **Appendix.** All prompts; entity and pair lists with sources; exclusion counts per condition;
   the mixed-model check; the percentile measure; robustness on tournament totals; power.
