# Index: every question and every answer

This folder answers two questions: **"what did we ever ask the models?"** and **"what did they
answer?"**. Everything here is made by `scripts/build_index.py` from the question files and the
raw answer files, so do not edit it by hand; rerun the script after each new run
(`python scripts/build_index.py`).

| File | What it is |
| --- | --- |
| [questions.md](questions.md) | Every question ever written (329), as readable tables, one per question set. |
| [questions.csv](questions.csv) | The same as a spreadsheet: set, source, true answer, picked or not, which experiments asked it, how many answers. |
| [experiments.csv](experiments.csv) | The 7 experiments: date, model, data folder, number of answers, cost, report. |
| `answers/<ID>.csv` | Every answer to one question, e.g. [answers/C2-007.csv](answers/C2-007.csv) for Bennu. |

## How to look something up (example: Bennu)

1. Open [questions.md](questions.md) and search the page (Ctrl+F) for "Bennu". The row says:
   ID `C2-007`, "How many Earth days does it take the asteroid 101955 Bennu to orbit the Sun
   once?", true answer 436.65 days, starting value 365 days, picked for Study 2, asked in
   experiments 3, 5 and 7, **440 answers**.
2. Click 440. GitHub shows [answers/C2-007.csv](answers/C2-007.csv) as a table you can search.
   Each row is one answer: which experiment, which model, thinking level, whether the starting
   value was the model's own or given, the number it gave and its full final reply.
3. The model's thinking is not in this table (it would make the folder about 8 times bigger).
   To read it, take the `raw_file`, `cell_id` and `sample` columns of that row; the raw file is
   gzipped JSON lines, readable with
   `pandas.read_json("<raw_file>", lines=True)` (column `thinking`).

## The question sets

| Set | IDs | Questions | Where they are | Asked in experiments |
| --- | --- | --- | --- | --- |
| 1: first pilot questions | `S1-01..15`, `S2-01..15` | 30 | `data/items/` | 1, 2 |
| 2a: v2 Study 1 candidates | `C1-001..137` | 137 | `data/items_v2/candidates_study1.csv` | 3; the 15 picked also 6 |
| 2b: v2 Study 2 candidates | `C2-001..069` | 69 | `data/items_v2/candidates_study2.csv` | 3; the 2 picked (Itokawa, Bennu) also 5, 7 |
| 2c: asteroid orbits | `C2-101..154` | 54 | `data/items_v2/candidates_study2_neo.csv` | 4; the 4 picked also 5, 7 |
| 2d: 2026 events and films | `C2-201..239` | 39 | `data/items_v2/candidates_study2_events.csv` | 4; the 4 picked also 5, 7 |

Every one of the 329 questions was asked at least once. `data/items_v2/study1.csv` (15) and
`study2.csv` (10) are copies of the picked rows, not new questions. Small test runs
(`data/*_smoke/`) are left out of the index.

## The exact wording sent to the models

Every prompt is one message built from the question and one of these endings (code:
`src/anchoring_llms/prompts.py`). It is the same for every question set.

**No anchor** (screening, the no-anchor runs, and the "own starting value" version of Study 2):

```
How many Earth days does it take the asteroid 25143 Itokawa to orbit the Sun once?

Give your best estimate. End your reply with a final line of the form
Estimate: <number>
where <number> is a single number in days (not a range).
```

**Anchor given** (Study 1, and the "given starting value" version of Study 2):

```
How many Earth days does it take the asteroid 25143 Itokawa to orbit the Sun once?

First, is it higher or lower than 365 days? Then give your best estimate. End your reply with these two lines:
Comparison: <higher or lower>
Estimate: <number>
where <number> is a single number in days (not a range).
```

Study 2 also adds one sentence after the question in two of its three versions:
"Accuracy matters here: take as much care as you need to make your estimate as close as possible
to the true value." or "Before answering, consider reasons why the true value might be quite
different from the first value that comes to mind." (with a given value: "... different from
365 days."). In the answer files these are `instruction` = `accuracy` and `opposite`.

## Two columns for the number: `estimate_saved` and `estimate_checked`

`estimate_saved` is what the run saved at the time. `estimate_checked` reads the same reply again
with today's rules:

- only a number on the `Estimate:` line counts. Before 30 October, a reply without that line was
  given its last number, which was often the anchor repeated back or a year from a refusal
  ("I can't know events of 2026" was read as 2026);
- in questions already asked in millions, "Estimate: $400 million" is 400, not 400,000,000.

How many answers the two columns disagree on is in `experiments.csv`
(`answers_reparsed_differently`). The reports use the checked reading, except pilot run 2
(Qwen3-32B, 182 thinking-off replies without the line, not re-read yet). The large model's
screening answers, which decided the picks, are the same either way.
