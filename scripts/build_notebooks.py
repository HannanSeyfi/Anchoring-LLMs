"""Writes the Colab notebooks in notebooks/. Edit the cells here, then run:

    python scripts/build_notebooks.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = "HannanSeyfi/Anchoring-LLMs"
BRANCH = "main"
NOTEBOOKS = Path(__file__).resolve().parents[1] / "notebooks"


def colab_badge(name: str) -> str:
    url = f"https://colab.research.google.com/github/{REPO}/blob/{BRANCH}/notebooks/{name}"
    return f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({url})"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {"cellView": "form"}, "execution_count": None,
            "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}


def notebook(cells: list[dict], gpu: bool) -> dict:
    meta = {"colab": {"provenance": []},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"}}
    if gpu:
        meta["accelerator"] = "GPU"
        meta["colab"]["gpuType"] = "A100"
    return {"nbformat": 4, "nbformat_minor": 0, "metadata": meta, "cells": cells}


GET_CODE = f'''
#@title 2. Get the code from GitHub
import os, subprocess

def secret(name):
    try:
        from google.colab import userdata
    except ImportError:  # not on Colab
        return os.environ.get(name)
    try:
        return (userdata.get(name) or "").strip()
    except Exception as e:
        raise RuntimeError(f"Add a Colab secret named {{name}} (key icon on the left) "
                           "and switch on 'Notebook access'. See the README.") from e

token = secret("GITHUB_TOKEN")
if not token:
    raise RuntimeError("The GITHUB_TOKEN secret is empty.")

def git(*args, cwd=WORKDIR):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).replace(token, "***"))
    return r.stdout.strip()

url = f"https://x-access-token:{{token}}@github.com/{{REPO}}.git"
if not os.path.isdir(WORKDIR):
    git("clone", "--branch", BRANCH, url, WORKDIR, cwd=os.path.dirname(WORKDIR))
else:
    git("remote", "set-url", "origin", url)  # picks up a token that was changed in the secrets panel
    git("fetch", "origin", BRANCH)
    git("checkout", BRANCH)
    git("pull", "--rebase", "--autostash")
git("config", "user.name", "Hannan Seyfi")
git("config", "user.email", "52991511+HannanSeyfi@users.noreply.github.com")
os.chdir(WORKDIR)
print("Using code at commit", git("log", "-1", "--format=%h %s"))
if SAVE_TO_GITHUB:  # check now that GitHub accepts saves with this token, before any GPU time is spent
    test = subprocess.run(["git", "push", "--dry-run", "origin", BRANCH], cwd=WORKDIR,
                          capture_output=True, text=True)
    if test.returncode != 0:
        raise RuntimeError("GitHub refuses to save with this token. Give the token 'Contents: Read and "
                           "write' on Anchoring-LLMs, put it in the GITHUB_TOKEN secret, and run this "
                           "cell again.\\n" + test.stderr.replace(token, "***")[-300:])
    print("Saving to GitHub works.")
'''

SAVE = '''
#@title {title}
if not SAVE_TO_GITHUB:
    print("SAVE_TO_GITHUB is off, so nothing was saved. Files are only in this Colab session.")
elif not os.path.isdir({folder}):
    print("Nothing to save yet:", {folder}, "does not exist.")
else:
    git("add", {folder})
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", {message})
    git("pull", "--rebase", "--autostash")
    git("push")
    print("Saved on GitHub:", f"https://github.com/{{REPO}}/tree/{{BRANCH}}/{{{folder}}}")
'''


CONFIG_PARAM = '''CONFIG = "configs/pilot_v2.yaml"  #@param ["configs/pilot_v2.yaml", "configs/pilot.yaml"]
# configs/pilot_v2.yaml = question set v2 (new questions the models do not know);
# configs/pilot.yaml = the first question set (pilot runs 1 and 2).'''

CONFIG_DIRS = '''
LABEL = "Pilot v2" if CONFIG.endswith("pilot_v2.yaml") else "Pilot"
DATA_DIR = ("data/pilot_v2" if LABEL == "Pilot v2" else "data/pilot") + ("_smoke" if SMOKE_TEST else "")'''


def run_pilot() -> dict:
    return notebook([
        md(f"""
# Run the anchoring pilot on one model

{colab_badge("01_run_pilot.ipynb")}

This notebook runs the pilot for **one model** on a Colab GPU and saves every answer to GitHub
as it goes, in `data/pilot_v2/` (question set v2, the default) or `data/pilot/` (the first
question set). Run it once for each model.

Question set v2 needs its questions picked first: run `04_screen_questions.ipynb` before this one.

**Before the first run**
1. *Runtime → Change runtime type →* **A100** (an **L4** also works, more slowly). A free **T4**
   only works with the two small models (`qwen3-4b`, `r1-distill-qwen-1.5b`).
2. Add your GitHub token as a Colab secret named `GITHUB_TOKEN`: key icon in the left sidebar,
   *Add new secret*, and switch on *Notebook access*. The README explains how to make the token.

**Then** choose the settings below and press *Runtime → Run all*.
Start with `SMOKE_TEST` ticked: it takes a few minutes and checks the GPU, the model and saving to
GitHub (into `data/pilot_v2_smoke/`). Then untick it for the real run.

**If Colab disconnects**, open the notebook again and *Run all*. The run continues where it
stopped: answers already saved on GitHub are skipped. Answers are pushed about every 10 minutes
and at the end of each phase.
"""),
        code(f'''
#@title 1. Settings
MODEL = "r1-distill-qwen-1.5b"  #@param ["r1-distill-qwen-1.5b", "qwen3-4b", "qwen3-8b", "r1-distill-llama-8b"]
{CONFIG_PARAM}
SMOKE_TEST = True  #@param {{type:"boolean"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
PHASE = "baseline,anchors,study1"  #@param ["baseline,anchors,study1", "all", "baseline", "anchors", "study1", "study2"]
# "baseline,anchors,study1" = Study 1 only (question set v2 has no Study 2 questions yet); "all" = both studies.
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
VLLM_VERSION = ""  #@param {{type:"string"}}
# Leave VLLM_VERSION empty for the latest vLLM; the version used is logged with the data.

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"{CONFIG_DIRS}

import subprocess
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip()
if not gpu:
    raise RuntimeError("No GPU. Runtime > Change runtime type > A100 or L4, then Run all again.")
print("GPU:", gpu)
if "T4" in gpu and MODEL in ("qwen3-8b", "r1-distill-llama-8b"):
    raise RuntimeError("A T4 is too small for this model. Pick an A100 or L4, "
                       "or set MODEL to qwen3-4b or r1-distill-qwen-1.5b.")
'''),
        code(GET_CODE),
        code('''
#@title 3. Install vLLM and this project (a few minutes)
# pip may warn about version conflicts with Colab's own packages; that is fine.
vllm = f"vllm=={VLLM_VERSION}" if VLLM_VERSION else "vllm"
!pip install -q {vllm}
!pip install -q -e .
'''),
        code('''
#@title 4. Run the pilot (answers are pushed to GitHub as it goes)
flags = f"--model {MODEL} --phase {PHASE}"
if SMOKE_TEST:
    flags += " --smoke"
if SAVE_TO_GITHUB:
    flags += " --sync"
!python -m anchoring_llms.run --config {CONFIG} {flags}
'''),
        code(SAVE.format(title="5. Final save to GitHub", folder="DATA_DIR",
                         message='f"{LABEL} data: {MODEL} (final save from Colab)"')),
        code('''
#@title 6. Quick look at the data
!python -m anchoring_llms.peek --data {DATA_DIR} --model {MODEL}
'''),
        md("""
**Next:** run this notebook again with the other model. When both are done, open
`02_analyze_pilot.ipynb` to make the tables, figures and report.
"""),
    ], gpu=True)


def run_pilot_api() -> dict:
    return notebook([
        md(f"""
# Run the anchoring pilot through DeepInfra (no GPU)

{colab_badge("03_run_pilot_deepinfra.ipynb")}

This notebook runs the pilot for **one hosted model** on DeepInfra and saves every answer to
GitHub as it goes, in `data/pilot_v2/` (question set v2, the default) or `data/pilot/` (the first
question set). A normal CPU runtime is enough. DeepInfra charges per token: pilot run 2 with
`qwen3-32b` cost $1.52; with the longer answer limit of v2, expect about $2 per model.
`qwen3-14b` (the middle step of the size ladder) is only in question set v2.

Question set v2 needs its questions picked first: run `04_screen_questions.ipynb` before this one.

**Spending limit.** `MAX_SPEND_USD` is the most this model may cost in total, counted across
restarts. Before each batch the run checks that even the most expensive outcome stays under the
limit, and stops otherwise. What it spent is shown as it runs and saved with the data.

**Before the first run**
1. Make a DeepInfra API key: in your DeepInfra account, open *API keys* and create one.
2. Add it as a Colab secret named `DEEPINFRA_API_KEY` (key icon in the left sidebar,
   *Add new secret*, switch on *Notebook access*), next to the `GITHUB_TOKEN` secret.

**Then** press *Runtime → Run all*. Start with `SMOKE_TEST` ticked: it costs a few cents and
checks the key, the model and saving to GitHub (into `data/pilot_v2_smoke/`). Then untick it.

**If Colab disconnects**, open the notebook again and *Run all*: finished answers are skipped,
and the money already spent still counts towards the limit.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-32b"  #@param ["qwen3-32b", "qwen3-14b"]
{CONFIG_PARAM}
SMOKE_TEST = True  #@param {{type:"boolean"}}
MAX_SPEND_USD = 5  #@param {{type:"number"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
PHASE = "baseline,anchors,study1"  #@param ["baseline,anchors,study1", "all", "baseline", "anchors", "study1", "study2"]
# "baseline,anchors,study1" = Study 1 only (question set v2 has no Study 2 questions yet); "all" = both studies.
BRANCH = "{BRANCH}"  #@param {{type:"string"}}

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"{CONFIG_DIRS}
if MODEL == "qwen3-14b" and LABEL == "Pilot":
    raise RuntimeError("qwen3-14b is only in question set v2: set CONFIG to configs/pilot_v2.yaml.")
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project and read the DeepInfra key
!pip install -q -e ".[api]"
os.environ["DEEPINFRA_API_KEY"] = secret("DEEPINFRA_API_KEY") or ""
if not os.environ["DEEPINFRA_API_KEY"]:
    raise RuntimeError("The DEEPINFRA_API_KEY secret is empty.")
print("DeepInfra key found.")
'''),
        code('''
#@title 4. Run the pilot (answers are pushed to GitHub as it goes)
flags = f"--model {MODEL} --phase {PHASE} --max-spend {MAX_SPEND_USD}"
if SMOKE_TEST:
    flags += " --smoke"
if SAVE_TO_GITHUB:
    flags += " --sync"
!python -m anchoring_llms.run --config {CONFIG} {flags}
'''),
        code('''
#@title 5. How much was spent
import json
from pathlib import Path
spend = Path(DATA_DIR, "runs", f"{MODEL}.spend.json")
if spend.exists():
    s = json.loads(spend.read_text())
    print(f"Spent on {MODEL} so far: ${s['spent_usd']:.2f} (limit ${MAX_SPEND_USD:.2f})")
else:
    print("Nothing spent yet.")
'''),
        code(SAVE.format(title="6. Final save to GitHub", folder="DATA_DIR",
                         message='f"{LABEL} data: {MODEL} (final save from Colab)"')),
        code('''
#@title 7. Quick look at the data
!python -m anchoring_llms.peek --data {DATA_DIR} --model {MODEL}
'''),
        md("""
**Next:** open `02_analyze_pilot.ipynb` to make the tables, figures and report. It analyses every
model in the data folder (`data/pilot_v2/` or `data/pilot/`) together.
"""),
    ], gpu=False)


def analyze_pilot() -> dict:
    return notebook([
        md(f"""
# Analyse the pilot

{colab_badge("02_analyze_pilot.ipynb")}

No GPU needed: a normal CPU runtime is fine. This notebook reads the pilot data from GitHub,
writes tables, figures, a report (`summary.md`) and a sheet of reasoning traces for hand coding
into `results/pilot_v2/` (question set v2) or `results/pilot/` (the first question set), and saves
them to GitHub.

Needs the same `GITHUB_TOKEN` Colab secret as the run notebook.
"""),
        code(f'''
#@title 1. Settings
DATA_DIR = "data/pilot_v2"  #@param ["data/pilot_v2", "data/pilot", "data/pilot_v2_smoke", "data/pilot_smoke"]
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
BRANCH = "{BRANCH}"  #@param {{type:"string"}}

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
RESULTS_DIR = "results/" + DATA_DIR.split("/")[-1]
LABEL = "Pilot v2" if "pilot_v2" in DATA_DIR else "Pilot"
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project
!pip install -q -e .
'''),
        code('''
#@title 4. Run the analysis
!python -m anchoring_llms.analysis --data {DATA_DIR} --out {RESULTS_DIR}
if globals().get("_exit_code", 0) != 0:
    raise RuntimeError("The analysis stopped with the error shown above. Paste it to Claude.")
'''),
        code('''
#@title 5. Show the report and figures
from pathlib import Path
from IPython.display import Image, Markdown, display

report = Path(RESULTS_DIR, "summary.md").read_text()
display(Markdown(report.split("## Figures")[0]))
for fig in sorted(Path(RESULTS_DIR, "figures").glob("*.png")):
    display(Image(str(fig)))
'''),
        code(SAVE.format(title="6. Save the results to GitHub", folder="RESULTS_DIR",
                         message='f"{LABEL} results: analysis from Colab"')),
    ], gpu=False)


def screen_questions() -> dict:
    return notebook([
        md(f"""
# Screen the new questions (question set v2)

{colab_badge("04_screen_questions.ipynb")}

An anchor can only pull a model's answer if the model does **not** know the answer. In pilot run 2,
Qwen3-32B knew 13 of the 15 questions, so there was almost nothing to measure. Question set v2
starts from 206 candidate questions (`data/items_v2/candidates_*.csv`, every true value checked).
This notebook asks one model each candidate question 20 times with thinking off and 20 times with
low thinking, without any anchor, and saves the answers to `data/screen_v2/`. Then it picks the 15
questions per study that the model is most unsure about, writes them to `data/items_v2/study1.csv`
and `study2.csv`, and writes a report to `results/screen_v2/screening.md`.

**Run it twice, in this order**
1. `qwen3-32b` on DeepInfra: a normal CPU runtime is enough. Costs about **$1.50**.
2. `r1-distill-qwen-1.5b` on a free **T4** GPU (*Runtime → Change runtime type → T4 GPU*). Free.

The questions are picked with Qwen3-32B's answers (a question the largest model does not know,
the small one does not know either). The second run checks that the small model also answers
the picked questions with a number, and picks again with both models. After that, run the pilot
with `CONFIG = configs/pilot_v2.yaml` in `03_run_pilot_deepinfra.ipynb` (qwen3-32b, qwen3-14b) and
`01_run_pilot.ipynb` (r1-distill-qwen-1.5b, qwen3-4b).

**Before the first run:** the Colab secrets `GITHUB_TOKEN` and, for hosted models,
`DEEPINFRA_API_KEY` (key icon in the left sidebar, switch on *Notebook access*), as for the other
notebooks.

**Then** press *Runtime → Run all*. Start with `SMOKE_TEST` ticked (2 questions per study, a few
cents, saved into `data/screen_v2_smoke/`), then untick it. If Colab disconnects, *Run all* again:
saved answers are skipped.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-32b"  #@param ["qwen3-32b", "r1-distill-qwen-1.5b", "qwen3-14b", "qwen3-4b", "qwen3-8b", "r1-distill-llama-8b"]
SMOKE_TEST = True  #@param {{type:"boolean"}}
MAX_SPEND_USD = 5  #@param {{type:"number"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
VLLM_VERSION = ""  #@param {{type:"string"}}
# MAX_SPEND_USD only matters for the hosted models (qwen3-32b, qwen3-14b).

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
CONFIG = "configs/pilot_v2.yaml"
HOSTED = MODEL in ("qwen3-32b", "qwen3-14b")
SUFFIX = "_smoke" if SMOKE_TEST else ""
SCREEN_DIR, RESULTS_DIR = "data/screen_v2" + SUFFIX, "results/screen_v2" + SUFFIX

import subprocess
if not HOSTED:
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    if not gpu:
        raise RuntimeError("This model runs on a GPU. Runtime > Change runtime type > T4 GPU, then Run all again.")
    print("GPU:", gpu)
    if "T4" in gpu and MODEL in ("qwen3-8b", "r1-distill-llama-8b"):
        raise RuntimeError("A T4 is too small for this model. Pick an A100 or L4, "
                           "or set MODEL to qwen3-4b or r1-distill-qwen-1.5b.")
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project (and vLLM for GPU models; a few minutes)
if HOSTED:
    !pip install -q -e ".[api]"
    os.environ["DEEPINFRA_API_KEY"] = secret("DEEPINFRA_API_KEY") or ""
    if not os.environ["DEEPINFRA_API_KEY"]:
        raise RuntimeError("The DEEPINFRA_API_KEY secret is empty.")
    print("DeepInfra key found.")
else:
    # pip may warn about version conflicts with Colab's own packages; that is fine.
    vllm = f"vllm=={VLLM_VERSION}" if VLLM_VERSION else "vllm"
    !pip install -q {vllm}
    !pip install -q -e .
'''),
        code('''
#@title 4. Ask the candidate questions (answers are pushed to GitHub as it goes)
flags = f"--model {MODEL}"
if HOSTED:
    flags += f" --max-spend {MAX_SPEND_USD}"
if SMOKE_TEST:
    flags += " --smoke"
if SAVE_TO_GITHUB:
    flags += " --sync"
!python -m anchoring_llms.screen --config {CONFIG} {flags}
if globals().get("_exit_code", 0) != 0:
    raise RuntimeError("Screening stopped with the message shown above.")
'''),
        code('''
#@title 5. Pick the questions
from pathlib import Path
if not Path(SCREEN_DIR, "raw", "qwen3-32b").is_dir():
    print("Qwen3-32B has not been screened yet; the questions are picked with its answers. "
          "Run this notebook with MODEL = qwen3-32b, then run this cell again.")
else:
    flags = ("--smoke" if SMOKE_TEST else "") + (" --sync" if SAVE_TO_GITHUB else "")
    !python -m anchoring_llms.select_items --config {CONFIG} {flags}
'''),
        code('''
#@title 6. Show the screening report
from IPython.display import Markdown, display
report = Path(RESULTS_DIR, "screening.md")
display(Markdown(report.read_text()) if report.exists() else "No report yet.")
'''),
        code('''
#@title 7. Final save to GitHub
folders = [SCREEN_DIR, RESULTS_DIR] + ([] if SMOKE_TEST else ["data/items_v2"])
folders = [f for f in folders if os.path.isdir(f)]
if not SAVE_TO_GITHUB:
    print("SAVE_TO_GITHUB is off, so nothing was saved. Files are only in this Colab session.")
elif folders:
    git("add", *folders)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", f"Screening data: {MODEL} (final save from Colab)")
    git("pull", "--rebase", "--autostash")
    git("push")
    print("Saved on GitHub:", ", ".join(folders))
'''),
        md("""
**Next:** if you screened `qwen3-32b`, run this notebook again with `r1-distill-qwen-1.5b` on a T4.
When both are done, `data/items_v2/study1.csv` and `study2.csv` hold the final questions: run the
pilot with `CONFIG = configs/pilot_v2.yaml` (notebooks 03 and 01), then analyse with notebook 02
(`DATA_DIR = data/pilot_v2`).
"""),
    ], gpu=False)


def main() -> None:
    NOTEBOOKS.mkdir(exist_ok=True)
    for name, nb in [("01_run_pilot.ipynb", run_pilot()), ("02_analyze_pilot.ipynb", analyze_pilot()),
                     ("03_run_pilot_deepinfra.ipynb", run_pilot_api()),
                     ("04_screen_questions.ipynb", screen_questions())]:
        (NOTEBOOKS / name).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", NOTEBOOKS / name)


if __name__ == "__main__":
    main()
