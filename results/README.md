# Results

Written by `notebooks/02_analyze_pilot.ipynb` (through `python -m anchoring_llms.analysis`).
`results/pilot/` is the first question set; `results/pilot_v2/` is question set v2, with the same
layout. `results/screen_v2/` is written by `notebooks/04_screen_questions.ipynb`:

```
results/screen_v2/
  screening.md                  which v2 questions were picked and why, with a worked example
  tables/<study>_questions.csv  every candidate: the model's numbers, the rules it failed, picked or not
  tables/<study>_by_level.csv   every model, candidate and thinking level
```

For the pilot analysis:

```
results/pilot/
  summary.md               the report: data quality, Study 1 and Study 2 results, trace features
  figures/*.png            the figures shown in the report
  tables/*.csv             every number in the report, one table per analysis
  hand_coding_sample.csv   200 reasoning traces with empty `code` and `coder_notes` columns
```

Hand coding: label each trace `adjusting`, `retrieving`, `dismissing` or `none`
(see docs/pilot_protocol.md).
