# Pilot data

Written by `notebooks/01_run_pilot.ipynb` (through `python -m anchoring_llms.run`).
Smoke tests write the same layout to `data/pilot_smoke/`, which can be deleted at any time.

```
data/pilot/
  raw/<model>/baseline/part-*.jsonl.gz   unanchored answers
  raw/<model>/study1/part-*.jsonl.gz     answers with provided anchors
  raw/<model>/study2/part-*.jsonl.gz     self-generated vs provided starting points
  anchors/<model>.json                   each item's plausible range and the anchors placed from it
  runs/<model>.jsonl                     one line when a run starts and one when it finishes:
                                         code version, GPU, vLLM version, full config
```

Each saved batch is a new `part-*.jsonl.gz` file (gzipped, one JSON record per line), so pushes
to GitHub only add small files. Read them with `anchoring_llms.run.read_records(folder)` or
`anchoring_llms.analysis.load_study("data/pilot", "study1")`.

## One record = one model answer

| Field | Meaning |
| --- | --- |
| `cell_id` | The condition, e.g. `study1\|qwen3-8b\|S1-04\|high\|low\|far\|precise`. Used to resume runs. |
| `study`, `model`, `hf_id`, `item_id`, `sample` | What was asked of which model; `sample` numbers the repeats. |
| `thinking_level`, `budget` | `off` / `low` / `high` and the thinking-token budget (0 / 512 / 2048). |
| `direction`, `distance`, `precision` | Study 1 only: anchor below or above the range, near or far, round or precise. |
| `source`, `instruction` | Study 2 only: `self` or `provided`; `none`, `accuracy` or `opposite`. |
| `anchor`, `anchor_text` | The anchor value and how it was written in the prompt (empty when there is none). |
| `reference`, `truth` | Study 2 starting value; the true answer. |
| `prompt` | The exact user message. |
| `thinking`, `answer` | The reasoning trace and the final reply. |
| `thinking_tokens`, `answer_tokens` | Realised lengths in tokens. |
| `thinking_truncated` | True if the budget ran out and the thinking was closed for the model. |
| `answer_finish_reason` | `stop` normally; `length` if the reply hit the token limit. |
| `estimate`, `comparison` | The number and the higher/lower judgement parsed from the reply (empty if none). |
| `backend`, `timestamp` | `vllm` for real runs, `dryrun` for simulated ones; time saved (UTC). |
