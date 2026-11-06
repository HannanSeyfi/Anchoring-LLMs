"""Notebooks 05-08 for the bidirectional anchoring study. Built by scripts/build_notebooks.py."""

from __future__ import annotations

from build_notebooks import BRANCH, GET_CODE, REPO, code, colab_badge, md, notebook

HOSTED = ["qwen3-32b", "qwen3-14b", "llama-3.3-70b", "llama-3.1-8b"]
GPU_MODELS = ["qwen3-8b", "qwen3-4b"]

SECRETS = """
**Before the first run:** Colab secrets `GITHUB_TOKEN` and `DEEPINFRA_API_KEY` (key icon in the
left sidebar, switch on *Notebook access*), the same as for the other notebooks.
"""

SETTINGS_TAIL = f'''
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
CONFIG = "configs/bidirectional.yaml"
HOSTED = MODEL in {HOSTED!r}

import subprocess
if not HOSTED:
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    if not gpu:
        raise RuntimeError("This model runs on a GPU. Runtime > Change runtime type > GPU, then Run all again.")
    print("GPU:", gpu)
'''

INSTALL = '''
#@title 3. Install this project (and vLLM for GPU models; a few minutes)
if HOSTED:
    !pip install -q -e ".[api]"
    os.environ["DEEPINFRA_API_KEY"] = secret("DEEPINFRA_API_KEY") or ""
    if not os.environ["DEEPINFRA_API_KEY"]:
        raise RuntimeError("The DEEPINFRA_API_KEY secret is empty.")
    print("DeepInfra key found.")
else:
    # pip may warn about version conflicts with Colab's own packages; that is fine.
    !pip install -q vllm
    !pip install -q -e .
'''

SAVE_FOLDERS = '''
#@title {title}
folders = [f for f in {folders} if os.path.isdir(f)]
if not SAVE_TO_GITHUB:
    print("SAVE_TO_GITHUB is off, so nothing was saved. Files are only in this Colab session.")
elif folders:
    git("add", *folders)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", {message})
    git("pull", "--rebase", "--autostash")
    git("push")
    print("Saved on GitHub:", ", ".join(folders))
else:
    print("Nothing to save yet.")
'''

CHECK = '''
if globals().get("_exit_code", 0) != 0:
    raise RuntimeError("This step stopped with the message shown above. Paste it to Claude.")
'''


def run_flags() -> str:
    return '''flags = f"--model {MODEL}"
if HOSTED:
    flags += f" --max-spend {MAX_SPEND_USD} --workers {WORKERS}"
if SMOKE_TEST:
    flags += " --smoke"
if SAVE_TO_GITHUB:
    flags += " --sync"'''


def bidir_screen() -> dict:
    return notebook([
        md(f"""
# Bidirectional anchoring, step 1: screen the entities and freeze the pairs

{colab_badge("05_bidir_screen.ipynb")}

Each entity (a World Cup team, a player, an Olympic nation, a mountain, a product, ...) is asked
about **alone**, 20 times, with no other entity and no anchor: "How many attempts at goal did
Paraguay record across its three group-stage matches?". From these answers we learn, for every
entity, whether the model gives a number, how often it refuses, and how spread out its guesses are.
Pairs whose entities fail the rules are dropped, and the rest are **frozen**
(`data/bidirectional/frozen_dataset/`) before any anchoring trial is run. They are never changed
after that, so the questions cannot be picked with the anchoring results.

Run once, with `qwen3-32b` (a normal CPU runtime, about **$0.30-0.60**). The frozen pairs are
then used for every model.
{SECRETS}
**Then** press *Runtime → Run all*. Start with `SMOKE_TEST` ticked (a few answers, under a cent,
saved into `runs_smoke/`; nothing is frozen), then untick it. If Colab disconnects, *Run all*
again: saved answers are skipped.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-32b"  #@param {HOSTED + GPU_MODELS!r}
SMOKE_TEST = True  #@param {{type:"boolean"}}
MAX_SPEND_USD = 3  #@param {{type:"number"}}
WORKERS = 8  #@param {{type:"integer"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
# WORKERS = questions sent at the same time; lower it (4 or 2) if DeepInfra says "too many requests".
{SETTINGS_TAIL}'''),
        code(GET_CODE),
        code(INSTALL),
        code('''
#@title 4. Ask every entity alone (answers are pushed to GitHub as it goes)
!python -m anchoring_llms.bidirectional.trials --config {CONFIG} --phase screen
''' + run_flags() + '''
!python -m anchoring_llms.bidirectional.run --config {CONFIG} --phase screen {flags}
''' + CHECK),
        code('''
#@title 5. Look at a few answers
!python -m anchoring_llms.bidirectional.peek --config {CONFIG} --phase screen --model {MODEL} {"--smoke" if SMOKE_TEST else ""}
'''),
        code('''
#@title 6. Freeze the pairs (real run only)
from pathlib import Path
from IPython.display import Markdown, display
if SMOKE_TEST:
    print("Smoke test: nothing is frozen. Untick SMOKE_TEST and Run all for the real screening.")
elif Path("data/bidirectional/frozen_dataset/pairs_frozen.csv").exists():
    print("The pairs are already frozen; they are not changed. (Ask Claude if they really must be re-frozen.)")
else:
    !python -m anchoring_llms.bidirectional.screen --config {CONFIG} --model {MODEL}
    report = Path("data/bidirectional/screening_results", MODEL, "off", "screening_report.md")
    if report.exists():
        display(Markdown(report.read_text()))
'''),
        code(SAVE_FOLDERS.format(
            title="7. Final save to GitHub",
            folders='["data/bidirectional"]',
            message='f"Bidirectional screening: {MODEL} (final save from Colab)"')),
        md("""
**Next:** open `06_bidir_run.ipynb` with `PHASE = core`.
"""),
    ], gpu=False)


def bidir_run() -> dict:
    return notebook([
        md(f"""
# Bidirectional anchoring, step 2: run the anchoring trials

{colab_badge("06_bidir_run.ipynb")}

Every trial is a fresh conversation. In the main conditions the model first answers a comparison
("Did Cape Verde record more, fewer, or the same number of attempts at goal as Colombia?"), and then,
in the same conversation, estimates one of the two teams. The question is whether **both** teams'
estimates move towards each other, compared with conversations where the two teams are only
mentioned together (C1) or the comparison is shown but not answered (C3).

`PHASE` chooses what to run (needs the frozen pairs from `05_bidir_screen.ipynb`):

| PHASE | what | answers | cost on qwen3-32b |
|---|---|---|---|
| `core` | about 60 pilot pairs + 8 tournament-total pairs: all conditions, 10 repetitions | about 21,000 | about $1 |
| `numeric` | C4: a plain number as the anchor ("higher or lower than 26?") | about 1,800 | about $0.10 |
| `triplets` | low / middle / high teams: does the middle one move both ways? | about 2,000 | about $0.10 |
| `confirmatory` | the held-out pairs (about 115), only after the pilot has been analysed | about 36,000 | about $2 |

Run `core` on `qwen3-32b` first, then analyse it (`07_bidir_analyze.ipynb`). The other models
(`qwen3-14b`, `llama-3.3-70b`, `llama-3.1-8b` on DeepInfra; `qwen3-8b` and `qwen3-4b` on a GPU)
use the same pairs.
{SECRETS}
Start with `SMOKE_TEST` ticked (2 pairs, 2 repetitions, a cent), then untick it. If Colab
disconnects, *Run all* again: saved answers are skipped. `MAX_SPEND_USD` counts across restarts.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-32b"  #@param {HOSTED + GPU_MODELS!r}
PHASE = "core"  #@param ["core", "numeric", "triplets", "confirmatory"]
SMOKE_TEST = True  #@param {{type:"boolean"}}
MAX_SPEND_USD = 3  #@param {{type:"number"}}
WORKERS = 8  #@param {{type:"integer"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
{SETTINGS_TAIL}'''),
        code(GET_CODE),
        code('''
#@title 2b. Check that the pairs are frozen
from pathlib import Path
if not Path("data/bidirectional/frozen_dataset/pairs_frozen.csv").exists():
    raise RuntimeError("No frozen pairs yet. Run 05_bidir_screen.ipynb (SMOKE_TEST unticked) first.")
print(Path("data/bidirectional/frozen_dataset/FROZEN.json").read_text())
'''),
        code(INSTALL),
        code('''
#@title 4. Run the trials (answers are pushed to GitHub as it goes)
!python -m anchoring_llms.bidirectional.trials --config {CONFIG} --phase {PHASE}
''' + run_flags() + '''
!python -m anchoring_llms.bidirectional.run --config {CONFIG} --phase {PHASE} {flags}
''' + CHECK),
        code('''
#@title 5. Look at a few answers
!python -m anchoring_llms.bidirectional.peek --config {CONFIG} --phase {PHASE} --model {MODEL} {"--smoke" if SMOKE_TEST else ""}
'''),
        code(SAVE_FOLDERS.format(
            title="6. Final save to GitHub",
            folders='["data/bidirectional"]',
            message='f"Bidirectional {PHASE}: {MODEL} (final save from Colab)"')),
        md("""
**Next:** `07_bidir_analyze.ipynb` with the same `MODEL`.
"""),
    ], gpu=False)


def bidir_analyze() -> dict:
    return notebook([
        md(f"""
# Bidirectional anchoring, step 3: analyse one model

{colab_badge("07_bidir_analyze.ipynb")}

No GPU and no DeepInfra key needed. Reads every saved answer of one model (core, numeric and
triplets), writes tables, figures and `report.md` to `results/bidirectional_v2/<model>/off/`, works
out how many pairs the confirmatory run needs (power), and saves it all to GitHub.

Needs the `GITHUB_TOKEN` Colab secret. Tick `SMOKE_TEST` to analyse smoke-test answers (saved
into `results/bidirectional_v2_smoke/`; those numbers mean nothing).
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-32b"  #@param {HOSTED + GPU_MODELS!r}
SMOKE_TEST = False  #@param {{type:"boolean"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
CONFIG = "configs/bidirectional.yaml"  #@param ["configs/bidirectional.yaml", "configs/bidirectional_v1.yaml"]
# configs/bidirectional_v1.yaml = pilot run A (comparison allowed UNSURE), kept for reference.
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project
!pip install -q -e .
'''),
        code('''
#@title 4. Run the analysis
import yaml
RESULTS_DIR = yaml.safe_load(open(CONFIG))["paths"]["results_dir"] + ("_smoke/" if SMOKE_TEST else "/") + MODEL + "/off"
!python -m anchoring_llms.bidirectional.analysis --config {CONFIG} --model {MODEL} {"--smoke" if SMOKE_TEST else ""}
''' + CHECK + '''
#@markdown Power: how many pairs the confirmatory run needs, with the spread seen here.
!python -m anchoring_llms.bidirectional.power --from-pilot {RESULTS_DIR}/tables/pair_effects.csv --out {RESULTS_DIR}/power.csv
'''),
        code('''
#@title 5. Show the report and figures
from pathlib import Path
from IPython.display import Image, Markdown, display
display(Markdown(Path(RESULTS_DIR, "report.md").read_text().split("![]")[0]))
for fig in sorted(Path(RESULTS_DIR, "figures").glob("*.png")):
    display(Image(str(fig)))
'''),
        code(SAVE_FOLDERS.format(
            title="6. Save the results to GitHub",
            folders='[RESULTS_DIR]',
            message='f"Bidirectional results: {MODEL} (analysis from Colab)"')),
    ], gpu=False)


def bidir_confidence() -> dict:
    nb = notebook([
        md(f"""
# Bidirectional anchoring, step 4: the model's confidence (GPU)

{colab_badge("08_bidir_confidence.ipynb")}

DeepInfra does not give the probabilities of a prompt's words, so this part runs an open model on
a Colab GPU. For each entity the model scores 12 fixed candidate answers ("Estimate: 20",
"Estimate: 26", ...), alone and after each kind of comparison. From these scores we get how sure
the model is (the share of the most likely candidate) and how far the whole distribution moved.
Question: do entities the model is less sure about move more?

*Runtime → Change runtime type →* **T4 GPU** is enough for `qwen3-4b` (about 1-2 hours for the
pilot pairs); `qwen3-8b` needs an **L4** or **A100**. Free on Colab; no DeepInfra key needed.
Needs the frozen pairs from `05_bidir_screen.ipynb` and the `GITHUB_TOKEN` secret.

Start with `SMOKE_TEST` ticked (2 pairs, a few minutes), then untick it.
"""),
        code(f'''
#@title 1. Settings
MODEL = "qwen3-4b"  #@param {GPU_MODELS[::-1]!r}
SMOKE_TEST = True  #@param {{type:"boolean"}}
SAVE_TO_GITHUB = True  #@param {{type:"boolean"}}
BRANCH = "{BRANCH}"  #@param {{type:"string"}}
REPO = "{REPO}"
WORKDIR = "/content/Anchoring-LLMs"
CONFIG = "configs/bidirectional.yaml"

import subprocess
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip()
if not gpu:
    raise RuntimeError("No GPU. Runtime > Change runtime type > T4 GPU, then Run all again.")
print("GPU:", gpu)
if "T4" in gpu and MODEL == "qwen3-8b":
    raise RuntimeError("A T4 is too small for qwen3-8b. Pick an L4 or A100, or set MODEL to qwen3-4b.")
'''),
        code(GET_CODE),
        code('''
#@title 3. Install this project
!pip install -q -e ".[confidence]"
'''),
        code('''
#@title 4. Score the candidate answers
!python -m anchoring_llms.bidirectional.confidence --config {CONFIG} --model {MODEL} {"--limit 2" if SMOKE_TEST else ""}
''' + CHECK),
        code(SAVE_FOLDERS.format(
            title="5. Save the results to GitHub",
            folders='[__import__("yaml").safe_load(open(CONFIG))["paths"]["results_dir"] + "/confidence"]',
            message='f"Bidirectional confidence: {MODEL} (from Colab)"')),
    ], gpu=True)
    nb["metadata"]["colab"]["gpuType"] = "T4"
    return nb


NOTEBOOKS = [("05_bidir_screen.ipynb", bidir_screen), ("06_bidir_run.ipynb", bidir_run),
             ("07_bidir_analyze.ipynb", bidir_analyze), ("08_bidir_confidence.ipynb", bidir_confidence)]
