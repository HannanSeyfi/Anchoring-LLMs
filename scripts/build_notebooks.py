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
        return userdata.get(name)
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

if not os.path.isdir(WORKDIR):
    git("clone", "--branch", BRANCH, f"https://x-access-token:{{token}}@github.com/{{REPO}}.git",
        WORKDIR, cwd=os.path.dirname(WORKDIR))
else:
    git("fetch", "origin", BRANCH)
    git("checkout", BRANCH)
    git("pull", "--rebase", "--autostash")
git("config", "user.name", "Hannan Seyfi")
git("config", "user.email", "52991511+HannanSeyfi@users.noreply.github.com")
os.chdir(WORKDIR)
print("Using code at commit", git("log", "-1", "--format=%h %s"))
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


def run_pilot() -> dict:
    return notebook([
        md(f"""
# Run the anchoring pilot on one model

{colab_badge("01_run_pilot.ipynb")}

This notebook runs the pilot for **one model** on a Colab GPU and saves every answer to GitHub
as it goes, in `data/pilot/`. Run it once for each model.

**Before the first run**
1. *Runtime → Change runtime type →* **A100** (an **L4** also works, more slowly). A free **T4**
   only works with the two small fallback models (`qwen3-4b`, `r1-distill-qwen-1.5b`).
2. Add your GitHub token as a Colab secret named `GITHUB_TOKEN`: key icon in the left sidebar,
   *Add new secret*, and switch on *Notebook access*. The README explains how to make the token.

**Then** choose the settings below and press *Runtime → Run all*.
Start with `SMOKE_TEST` ticked: it takes a few minutes and checks the GPU, the model and saving to
GitHub (into `data/pilot_smoke/`). Then untick it for the real run.

**If Colab disconnects**, open the notebook again and *Run all*. The run continues where it
stopped: answers already saved on GitHub are skipped. Answers are pushed about every 10 minutes
and at the end of each phase.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-8b"  #@param ["qwen3-8b", "r1-distill-llama-8b", "qwen3-4b", "r1-distill-qwen-1.5b"]
SMOKE_TEST = True  #@param {{type:"boolean"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
PHASE = "all"  #@param ["all", "baseline", "anchors", "study1", "study2"]
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
VLLM_VERSION = ""  #@param {{type:"string"}}
# Leave VLLM_VERSION empty for the latest vLLM; the version used is logged with the data.

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
DATA_DIR = "data/pilot_smoke" if SMOKE_TEST else "data/pilot"

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
!python -m anchoring_llms.run --config configs/pilot.yaml {flags}
'''),
        code(SAVE.format(title="5. Final save to GitHub", folder="DATA_DIR",
                         message='f"Pilot data: {MODEL} (final save from Colab)"')),
        code('''
#@title 6. Quick look at the data
!python -m anchoring_llms.peek --data {DATA_DIR} --model {MODEL}
'''),
        md("""
**Next:** run this notebook again with the other model. When both are done, open
`02_analyze_pilot.ipynb` to make the tables, figures and report.
"""),
    ], gpu=True)


def analyze_pilot() -> dict:
    return notebook([
        md(f"""
# Analyse the pilot

{colab_badge("02_analyze_pilot.ipynb")}

No GPU needed: a normal CPU runtime is fine. This notebook reads the pilot data from GitHub,
writes tables, figures, a report (`summary.md`) and a sheet of reasoning traces for hand coding
into `results/pilot/`, and saves them to GitHub.

Needs the same `GITHUB_TOKEN` Colab secret as the run notebook.
"""),
        code(f'''
#@title 1. Settings
DATA_DIR = "data/pilot"  #@param ["data/pilot", "data/pilot_smoke"]
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
BRANCH = "{BRANCH}"  #@param {{type:"string"}}

REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
RESULTS_DIR = "results/" + DATA_DIR.split("/")[-1]
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project
!pip install -q -e .
'''),
        code('''
#@title 4. Run the analysis
!python -m anchoring_llms.analysis --data {DATA_DIR} --out {RESULTS_DIR}
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
                         message='"Pilot results: analysis from Colab"')),
    ], gpu=False)


def main() -> None:
    NOTEBOOKS.mkdir(exist_ok=True)
    for name, nb in [("01_run_pilot.ipynb", run_pilot()), ("02_analyze_pilot.ipynb", analyze_pilot())]:
        (NOTEBOOKS / name).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", NOTEBOOKS / name)


if __name__ == "__main__":
    main()
