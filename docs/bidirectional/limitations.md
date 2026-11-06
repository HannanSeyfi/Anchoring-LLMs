# Known limitations

Stated before the data come in, so that none of them is discovered conveniently later.

1. **Young et al. read only partly.** The design follows their abstract and OSF pre-registrations.
   Details in the paper (e.g. exact wording, exclusions) may differ from ours.
2. **Olympics data from a secondary source.** The 2026 Winter Olympics medal totals come from
   Wikipedia's medal table (revision 1376824706), not the IOC. Medal totals are rarely revised,
   but the revision is recorded so it can be checked.
3. **FIFA statistics are FIFA's definitions.** "Attempts at goal", "passes", "crosses" and
   "corners" are FIFA's counts; another provider (e.g. Opta) may count differently. The model may
   have a different definition in mind, which adds noise but should not create a direction.
4. **No popularity measure for players or Olympic nations.** For teams, `famous` = former World Cup
   winner. Players and nations have no such flag, so Lehmann et al.'s popularity bias is only
   partly balanced.
5. **No reproducible sampling on DeepInfra.** The API takes no seed. Every reply is stored, so the
   analysis can be reproduced exactly, but the replies cannot be regenerated exactly.
6. **Model cutoffs are inferred.** Qwen3 does not publish a knowledge cutoff; we use its release date
   (April 2025). The World Cup and Olympics 2026 ended after it. Screening also checks that the
   model does not hit the true value.
7. **Known-fact pairs share a domain.** The 9 fact pairs are mountains, towers, lakes and a
   waterfall, a small and uneven set; it is a contrast, not a test on its own.
8. **Young items are prices in pounds from a UK human pilot.** The model's idea of a price may be
   from another year or shop; the prompt asks for the UK price "in British pounds".
9. **Thinking off only, in the primary analysis.** Reasoning may change the effect; the code supports
   thinking levels but the primary analysis (planned in advance) is thinking off.
10. **Turn-1 answers can carry numbers.** If a model writes "Colombia had about 60 attempts" in turn
    1, the anchor is partly numeric. These trials are flagged (`contaminated`) and the main
    contrasts are repeated without them.
11. **One screening model.** Pairs are screened with Qwen3-32B and used for every model. A smaller
    model may refuse or know different items; each model's exclusion counts are reported.
12. **Known-partner values come from Wikidata, often from one statement.** The obscure mountains
    and buildings (2-3 Wikipedia editions each) have a single Wikidata height, which is not
    checked against a second source. The famous items' Wikidata statements were reviewed by hand
    (where there were several, the `note` column of `famous.tsv` says which one was used and why). A wrong value adds noise to accuracy but cannot create a pull towards
    the partner, because the measure is the change from the item's own C1 and baseline answers.
    Building heights can mean roof or tip; Wikidata gives one number and we use it.
13. **Known-partner pairs are built after seeing runs A and B.** The extension was designed to
    explain the null result on World Cup 2026, so it is exploratory. Its pairs were chosen from
    Wikidata values only, and screened on baselines only, as for the main set.
