# Bidirectional item-based anchoring: how to run it

This study asks whether comparing two items makes **both** estimates move towards each other in an
LLM, as Young et al. (2026) found in people: after "Did Cape Verde record more or fewer attempts at
goal than Colombia?", is Cape Verde's (low) estimate pulled up **and** Colombia's (high) estimate
pulled down? The other documents in this folder:

| File | What is in it |
| --- | --- |
| [protocol.md](protocol.md) | Design, conditions with literal prompts, hypotheses, datasets, the rules that keep it honest |
| [analysis_plan.md](analysis_plan.md) | Measures, contrasts, statistics, exclusions, power |
| [literature.md](literature.md) | What earlier work did and did not do, and what is new here |
| [limitations.md](limitations.md) | Known weaknesses, stated up front |
| [manuscript_outline.md](manuscript_outline.md) | Sections of the paper and which result goes where |

All settings are in [`configs/bidirectional.yaml`](../../configs/bidirectional.yaml).

## What to run (Colab)

Every notebook needs the `GITHUB_TOKEN` Colab secret; the hosted models also need
`DEEPINFRA_API_KEY`. Tick `SMOKE_TEST` first, then untick it for the real run.

| Step | Notebook | Settings | Runtime | Cost |
| --- | --- | --- | --- | --- |
| 1 | [05_bidir_screen](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/05_bidir_screen.ipynb) | `MODEL = qwen3-32b` | CPU | about $0.30 |
| 2 | [06_bidir_run](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/06_bidir_run.ipynb) | `qwen3-32b`, `PHASE = core` | CPU | about $1 |
| 3 | [07_bidir_analyze](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/07_bidir_analyze.ipynb) | `qwen3-32b` | CPU | free |
| 4 | 06_bidir_run | `qwen3-32b`, `PHASE = numeric`, then `triplets`; then 07 again | CPU | about $0.20 |
| 5 | 06 then 07 | `PHASE = core` with `qwen3-14b`, `llama-3.3-70b`, `llama-3.1-8b` | CPU | about $1-2 each |
| 6 | 06 then 07 | `qwen3-8b` (L4/A100) or `qwen3-4b` (T4) | GPU | free |
| 7 | [08_bidir_confidence](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/08_bidir_confidence.ipynb) | `qwen3-4b` | T4 GPU | free |
| 8 | 06 then 07 | `PHASE = confirmatory`, only after the pilot has been looked at | CPU | about $2 per model |
| kp | 05, then 06 (`core`, then `numeric`), then 07 | `CONFIG = configs/bidirectional_kp.yaml`, `qwen3-32b`: the known-partner pairs | CPU | about $0.10 + $0.40 + $0.02 |

Costs are estimates from the token counts of the prompts and DeepInfra's listed prices; each run
stops before passing `MAX_SPEND_USD`. Check the Llama prices on deepinfra.com/pricing before step 5.

## The same steps from a terminal

```bash
pip install -e ".[api,test]"
export DEEPINFRA_API_KEY=...                                   # never written into any file
python -m anchoring_llms.bidirectional.sources                 # entities from raw_sources/ (already done)
python -m anchoring_llms.bidirectional.pairs                   # pairs and triplets (already done)
python -m anchoring_llms.bidirectional.trials --phase screen
python -m anchoring_llms.bidirectional.run --phase screen --model qwen3-32b
python -m anchoring_llms.bidirectional.screen --model qwen3-32b          # freezes the pairs
python -m anchoring_llms.bidirectional.trials --phase core               # also numeric, triplets, confirmatory
python -m anchoring_llms.bidirectional.run --phase core --model qwen3-32b
python -m anchoring_llms.bidirectional.analysis --model qwen3-32b
python -m anchoring_llms.bidirectional.power --from-pilot results/bidirectional_v2/qwen3-32b/off/tables/pair_effects.csv
python -m anchoring_llms.bidirectional.confidence --model qwen3-4b       # on a GPU
python -m anchoring_llms.bidirectional.run --phase core --backend simulated   # test without any model
pytest
```

A simulated run (`--backend simulated`) answers with a made-up model whose pattern you choose
(`--pattern bidirectional | low_only | high_only | none | contrast`). It only checks the code:
its output goes to `runs_smoke/` and `results/bidirectional_smoke/`, and its report says
**SIMULATED DATA** at the top. Simulated numbers are never results.

## Where the files are

| Path | What |
| --- | --- |
| `data/bidirectional/raw_sources/` | Data as downloaded: FIFA match and season statistics (2026, 2022), the 2026 Winter Olympics medal table |
| `data/bidirectional/candidate_entities.csv` | 656 entities with their true value, source and checks |
| `data/bidirectional/candidate_pairs.csv` | Every allowed pair (9,131) before selection |
| `data/bidirectional/verified_pairs.csv` | The 188 selected pairs |
| `data/bidirectional/triplets.csv` | 9 low / middle / high triplets |
| `data/bidirectional/generated_trials/` | Trials per phase (`bank.*` is kept: every condition of every pair once, for reading) |
| `data/bidirectional/frozen_dataset/` | Written once by screening: `pairs_frozen.csv` (with the split), `triplets_frozen.csv`, `FROZEN.json` with checksums |
| `data/bidirectional/screening_results/<model>/off/` | Entity statistics, eligibility of every pair, screening report |
| `data/bidirectional/runs_v2/<phase>/<model>/off/` (`runs/` = pilot run A, design v1) | Every reply, raw, with its parsed number (`part-*.jsonl.gz`) |
| `results/bidirectional_v2/<model>/off/` | Tables, figures (with their numbers as CSV), `report.md` |
| `results/bidirectional/confidence/<model>/` | Candidate scores and shifts |

## Data dictionary

**Entity** (`candidate_entities.csv`): `entity_id`; `dataset` (`wc2026`, `wc2022`, `olympics2026`,
`facts`, `young`); `domain` (teams, players, olympics, mountains, lake depths, towers,
waterfalls, prices); `entity_label` (the name used in prompts); `metric`, `metric_label`,
`metric_definition`; `scope` (`group_stage` = the three group matches, the primary scope;
`tournament` = all matches, robustness; `games`; `fact`); `unit`; `value` (the true value; never
shown to a model); `integer`; `matches_played`, `minutes_played`; `famous` (former World Cup
winner, for teams); `after_cutoff` (the event ended after the tested models' release);
`source_name`, `source_url`, `source_endpoint`, `retrieved_utc`; `verification` (how the value
was checked, e.g. the sum over matches equals FIFA's tournament total).

**Pair** (`verified_pairs.csv`): `pair_id`; `low_entity_id` / `high_entity_id` and their labels
and true values; `gap_ratio` (high / low) and `ratio_bin`; `n_famous`; `same_group`; sources;
`verification_status`; `quality_review`; `ambiguities`. After screening, `pairs_frozen.csv` adds
`eligible`, `exclusion_reason`, `split` (`pilot`, `robustness`, `confirmatory`, `excluded`) and
each side's screening statistics.

**Reply record** (`runs/.../part-*.jsonl.gz`, one line per trial): `trial_id`, `phase`,
`condition`, `pair_id`, `role` (`low` / `high` = which entity is estimated), `order`,
`template_id`, `repetition`, `seed`; `turns` (the user messages) and `history_2` (the full
conversation of the second turn); `reply_1`, `reply_2` and `thinking_*`; `estimate`,
`parse_status` (`ok`, `refusal`, `invalid`, `cut_off`), `flag_*` (range, several numbers,
uncertainty words, ...); `turn1_answer` (more / fewer / unsure), `turn1_correct` and `contaminated` (the turn-1
reply contained numbers other than years); model, provider, release date, cutoff, temperature, token counts, code commit.
