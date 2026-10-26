# Pilot with question set v2: what to run, in order

Question set v2 replaces the pilot questions with ones the models do not know (pilot run 2
showed that Qwen3-32B knew 13 of the 15). The design is otherwise the one in
[pilot_protocol.md](pilot_protocol.md), with the fixes listed in [CHANGELOG.md](../CHANGELOG.md).
All settings: [`configs/pilot_v2.yaml`](../configs/pilot_v2.yaml).

## Step 1: screen the candidate questions

Notebook `04_screen_questions.ipynb`. Each candidate (299 of them) is asked 20 times with thinking
off and 20 times with low thinking, without an anchor.

| Run | Runtime | Cost | Saves |
| --- | --- | --- | --- |
| `MODEL = qwen3-32b` | CPU (DeepInfra) | about $1-1.50 | `data/screen_v2/raw/qwen3-32b/` |
| `MODEL = r1-distill-qwen-1.5b` | free T4 GPU | free | `data/screen_v2/raw/r1-distill-qwen-1.5b/` |

Run them in this order: the questions are picked from Qwen3-32B's answers, and the second run
then checks that the small model can also answer them with a number. Each run ends by picking
the questions again with every model screened so far.

The picked questions are written to `data/items_v2/study1.csv` and `study2.csv` (15 each), and
the report to `results/screen_v2/screening.md`. Read the report before going on: it shows, for
every picked question, the range of the model's answers and how often it gave the true value,
with a worked example at the top of each study.

**What to check in the report**
- 15 Study 1 and 10 Study 2 questions were picked, and none of them is marked "picked to fill a gap". If some
  are, fewer questions passed the rules than needed; tell Claude, and we can add candidates or
  relax a limit in the `screening` section of the config.
- The worked examples look like questions a person could also be unsure about.

## Step 2: run the pilot on the picked questions

Same notebooks as before, with `CONFIG = configs/pilot_v2.yaml` (now the default). Data goes to
`data/pilot_v2/`.

**Study 1** runs with `PHASE = baseline,anchors,study1` (the default). **Study 2** runs with
`PHASE = study2`, on the 10 questions where thinking moved Qwen3-32B's answer towards the truth
(see CHANGELOG.md: two batches were added and screened, 54 near-Earth asteroid orbits and 39
numbers from 2026 events, and a rule was added after that screening). `PHASE = all` runs both.

| Model | Notebook | Runtime | Cost |
| --- | --- | --- | --- |
| `qwen3-32b` | `03_run_pilot_deepinfra.ipynb` | CPU | about $2 |
| `r1-distill-qwen-1.5b` | `01_run_pilot.ipynb` | free T4 | free |

Start each with `SMOKE_TEST` ticked, then untick it for the real run. Pilot run 2 cost $1.52 for
Qwen3-32B; v2 can cost a little more because answers may now be up to 1,536 tokens long.

## Step 3: analyse

Notebook `02_analyze_pilot.ipynb` with `DATA_DIR = data/pilot_v2`. It writes
`results/pilot_v2/summary.md`, the figures, and the hand-coding sheet.

## Later: the size ladder

The same questions can then be run on more Qwen3 sizes, to see whether the mechanism changes
with scale: `qwen3-14b` (notebook 03, about $2), `qwen3-4b` (notebook 01 on a free T4) and
`qwen3-8b` (notebook 01 on an A100 or L4). For a fair comparison the questions stay the ones
picked with Qwen3-32B; screening a smaller model only adds its parse check to the report.

## For the paper

- The candidate lists, the screening answers, the rules and the report are all in the
  repository, so the choice of questions can be reproduced and described exactly.
- Picking questions with the same model that is then tested is a form of selection: the
  questions are, by construction, ones Qwen3-32B is unsure about. That is the point (anchoring
  needs uncertainty), but the paper should say so and report how many candidates were screened.
- The screening answers are unanchored, like the baseline, but they are not reused as the
  baseline: the pilot asks the baseline again, so the anchors are placed from fresh answers.
