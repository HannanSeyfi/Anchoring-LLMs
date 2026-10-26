# Anchoring in LLMs: adjusting or retrieving?

Code, data and write-ups for a study of **why** large language models show the anchoring effect.
Two human accounts make different predictions: *insufficient adjustment* (start at the anchor and
stop too early) and *selective accessibility* (the anchor brings anchor-consistent facts to mind).
We test them with open-weight reasoning models whose thinking we can read and whose thinking
budget we can control. The full design is in the [proposal](latex/proposal/main.tex).

## Where things are

| Folder | What is in it |
| --- | --- |
| `latex/proposal/` | The research proposal (also in Overleaf). |
| `latex/pilot_summary/` | Plain-language summary of pilot run 1 for the professors (also in Overleaf). |
| `latex/qwen3_report/` | Report on pilot run 2 (Qwen3-32B): results, explanations and feedback (also in Overleaf). |
| `docs/` | [Pilot protocol](docs/pilot_protocol.md), [steps for question set v2](docs/pilot_v2.md) and [which models and why](docs/model_choice.md). |
| `CHANGELOG.md` | What changed between question sets and why. |
| `notebooks/` | Colab notebooks: screen new questions, run the pilot on a GPU or through DeepInfra, then analyse it. |
| `configs/pilot.yaml` | Every setting of the pilot with the first question set: models, reasoning levels, sample sizes. |
| `configs/pilot_v2.yaml` | The same for question set v2, plus the screening rules. |
| `data/items/` | The first 30 pilot questions with their true answers ([notes](data/items/README.md)). |
| `data/items_v2/` | Question set v2: 206 checked candidate questions and the 15 + 15 picked by screening ([notes](data/items_v2/README.md)). |
| `data/screen_v2/` | Screening answers: each candidate asked without an anchor, written by notebook 04. |
| `data/pilot/` | Raw model answers for the first question set (pilot runs 1 and 2), written by the notebooks ([format](data/pilot/README.md)). |
| `data/pilot_v2/` | Raw model answers for question set v2 (same format). |
| `results/pilot/` | Tables, figures, report and hand-coding sheet, written by the analysis. |
| `results/screen_v2/` | Screening report: which v2 questions were picked and why. |
| `results/pilot_v2/` | Analysis of the v2 pilot (same layout as `results/pilot/`). |
| `src/anchoring_llms/` | The Python package that the notebooks call. |
| `scripts/` | Helpers: recompute the calculated answers (both question sets), rebuild the notebooks. |
| `tests/` | Checks for answer parsing, anchor placement and the whole pipeline. |

## Question set v2 (current)

Pilot run 2 showed that Qwen3-32B knew most of the first questions, so anchors had nothing to
pull. Question set v2 screens 206 new candidates and keeps those the models are unsure about.
The steps, in order, are in [docs/pilot_v2.md](docs/pilot_v2.md):

1. Screen: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/04_screen_questions.ipynb)
   first with `qwen3-32b` (CPU, about $1-1.50), then with `r1-distill-qwen-1.5b` (free T4).
2. Run the pilot with `CONFIG = configs/pilot_v2.yaml` in notebooks 03 (`qwen3-32b`) and 01
   (`r1-distill-qwen-1.5b`), as described below.
3. Analyse with notebook 02 and `DATA_DIR = data/pilot_v2`.

## Running the pilot on Colab

1. **Make a GitHub token** so Colab can read the code and save the data. On GitHub:
   *Settings → Developer settings → Personal access tokens → Fine-grained tokens →
   Generate new token*. Under *Repository access* choose *Only select repositories* and pick
   `Anchoring-LLMs`. Under *Permissions → Repository permissions* set **Contents** to
   **Read and write**. Copy the token.
2. **Open the run notebook**:
   [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/01_run_pilot.ipynb)
   (if Colab asks, allow it to see your GitHub repositories, including private ones).
   If Colab's GitHub sign-in fails, upload the notebook instead: open
   `notebooks/01_run_pilot.ipynb` on GitHub, click *Download raw file*, then in Colab use
   *File → Upload notebook*. It works the same, because the notebook fetches the code itself
   with your token.
3. **Add the token to Colab**: key icon in the left sidebar → *Add new secret*, name it
   `GITHUB_TOKEN`, paste the token, and switch on *Notebook access*. You only do this once.
4. **Pick a GPU**: *Runtime → Change runtime type → A100* (L4 also works, more slowly).
5. **Smoke test**: leave `SMOKE_TEST` ticked and *Runtime → Run all*. This takes a few minutes
   and checks the GPU, the model download and saving to GitHub (into `data/pilot_smoke/`).
6. **Real run**: untick `SMOKE_TEST`, *Run all* again. Then repeat with the second model.
   Answers are pushed to GitHub about every 10 minutes. If Colab disconnects, *Run all* again:
   finished answers are skipped.
7. **Analyse**:
   [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/02_analyze_pilot.ipynb)
   No GPU needed. It writes `results/pilot/summary.md`, the figures and the hand-coding sheet,
   and saves them to GitHub.

## Running a hosted model through DeepInfra (no GPU)

`qwen3-32b` and `qwen3-14b` run on [DeepInfra](https://deepinfra.com) instead of a Colab GPU, with the same
thinking limits. DeepInfra charges per token: pilot run 2 cost $1.52 (expect about $2 with question set v2), and the notebook
stops before it can spend more than the limit you set (`MAX_SPEND_USD`, counted across restarts).

1. In your DeepInfra account, open *API keys* and create a key.
2. In Colab, add it as a secret named `DEEPINFRA_API_KEY` (same place as `GITHUB_TOKEN`).
3. Open the notebook:
   [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/HannanSeyfi/Anchoring-LLMs/blob/main/notebooks/03_run_pilot_deepinfra.ipynb)
   Keep the default CPU runtime. Run the smoke test first (a few cents), then untick
   `SMOKE_TEST` for the real run. Then analyse with `02_analyze_pilot.ipynb` as above.

## Working on the code locally

```bash
pip install -e ".[test]"
pytest                                   # fast checks, no GPU needed
python -m anchoring_llms.run --model qwen3-8b --backend dryrun --smoke   # simulated model
python -m anchoring_llms.analysis --data data/pilot_smoke --out results/pilot_smoke
python -m anchoring_llms.screen --model qwen3-32b --backend dryrun --smoke     # question set v2
python -m anchoring_llms.select_items --smoke
```

The `dryrun` backend fakes model answers, so the whole pipeline can be tried without a GPU.
Its numbers mean nothing. If you change a notebook, edit `scripts/build_notebooks.py` and run it,
so the notebooks stay in sync with the code.
