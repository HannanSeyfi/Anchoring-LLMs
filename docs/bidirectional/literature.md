# Literature and what is new here

Only papers we have actually looked at are listed, with how far we read them. Nothing here
claims that this study is the first of its kind: the search was not systematic, and a claim of
novelty in the paper needs a proper search first (Google Scholar, ACL Anthology, arXiv, with
the search terms recorded).

## Papers this design builds on

| Paper | What it did | Read | What we take from it |
| --- | --- | --- | --- |
| Young et al. (2026), *Cognitive Psychology* 164, 101796 | People compared two items (products), then estimated one. Both items' estimates moved towards the other (item-based, bidirectional anchoring); low-value items moved more; selective accessibility fit best. | Abstract and the OSF pre-registrations (project 2a9nz); the paper itself was behind a captcha | The design (LT / LA / HT / HA), the 8 products and prices of Experiment 1, the percentile measure, the low/high asymmetry as a prediction |
| Owusu & Feldman (2026), ACL short, pp. 174-180 | Related anchoring in LLMs to the model's confidence: fixed candidate answers, length-normalised log-likelihood, softmax; certainty = largest probability; shift = total variation distance. Llama-3.1-8B and Qwen2.5-7B, 50 questions. | In full | The confidence method in `confidence.py` (we use 12 candidates instead of 9, spaced on a log scale over all entities of a statistic) |
| Lehmann et al. (2026), EACL long, pp. 4788-4821 | LLM comparisons between entities are biased by the entities' popularity, the order they are named in, and how often they appear together. | Abstract | Balance famous / not famous in every pair bin; both naming orders; a co-mention control (C1) |

## Earlier LLM anchoring work (numeric anchors)

| Paper | Finding | Read |
| --- | --- | --- |
| SynAnchors (arXiv 2505.15392) | Synthetic anchoring dataset; reasoning reduces but does not remove anchoring | In full |
| AnchorBench | Benchmark of numeric anchoring in LLMs | In full |
| Lou & Sun (arXiv 2412.06593) | Chain-of-thought does not remove anchoring | Abstract |
| arXiv 2610.10049 | Larger thinking budgets do not reliably reduce anchoring (5 anchoring items) | Abstract |
| arXiv 2606.12818, arXiv 2511.05766 | Mechanistic analyses of anchoring inside the model | Abstract |

## Novelty matrix

| | Numeric anchor given | Item anchor (model supplies the number) | Both directions tested separately | Post-cutoff items (no stored answer) | Confidence measured | Co-mention / no-commitment controls |
| --- | --- | --- | --- | --- | --- | --- |
| Young et al. (humans) | | ✓ | ✓ | n/a | | |
| Owusu & Feldman | ✓ | | | | ✓ | |
| SynAnchors, AnchorBench, Lou & Sun | ✓ | | | | | |
| Lehmann et al. | (comparisons, no estimates) | | | | | |
| **This study** | ✓ (C4, exploratory) | ✓ | ✓ | ✓ | ✓ (open models) | ✓ |

What this study adds, if the matrix holds after a proper search: item-based anchoring in LLMs;
each direction tested on its own with patterns decided in advance; controls that separate
comparing from merely naming (C1), from seeing without answering (C3) and from an irrelevant
comparison (C2); items the models cannot have memorised (World Cup 2026, Winter Olympics 2026),
contrasted with obscure (World Cup 2022) and known (facts) items; and the human items of Young
et al. for a direct comparison.

## Still to read

- Young et al. (2026) in full (through a library login).
- Lehmann et al. (2026) in full, for how they measure popularity.
- The applied anchoring work suggested by the professors (software engineering), before the
  paper cites it.
