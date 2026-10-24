# Results

Written by `notebooks/02_analyze_pilot.ipynb` (through `python -m anchoring_llms.analysis`).

```
results/pilot/
  summary.md               the report: data quality, Study 1 and Study 2 results, trace features
  figures/*.png            the figures shown in the report
  tables/*.csv             every number in the report, one table per analysis
  hand_coding_sample.csv   200 reasoning traces with empty `code` and `coder_notes` columns
```

Hand coding: label each trace `adjusting`, `retrieving`, `dismissing` or `none`
(see docs/pilot_protocol.md).
