"""Build the index of every question and every answer in the project (folder index/).

Run from the repository root:  python scripts/build_index.py

It reads the question files (data/items/, data/items_v2/) and every raw answer file
(data/pilot/, data/screen_v2/, data/pilot_v2/; small test runs in *_smoke/ are left out) and writes

  index/questions.csv     one row per question ever written, with its set, source, true answer,
                          whether screening picked it, which experiments asked it, how many answers
  index/questions.md      the same as readable tables, one per question set
  index/experiments.csv   one row per experiment: date, model, data folder, answers, cost, report
  index/answers/<id>.csv  every answer to one question (the final reply, not the thinking),
                          with the experiment, model, thinking level, anchor and parsed number

`estimate_saved` is the number the run saved at the time. `estimate_checked` re-reads the reply
with today's rules: only a number on an "Estimate:" line counts, and "$400 million" in a question
that already asks in millions is 400. Rerun this script after every new run.
"""

from __future__ import annotations

import csv
import glob
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.parsing import parse_estimate  # noqa: E402

OUT = ROOT / "index"

QUESTION_FILES = [
    # file, question set, study
    ("data/items/study1_provided.csv", "Set 1: first pilot questions", "Study 1"),
    ("data/items/study2_self_anchor.csv", "Set 1: first pilot questions", "Study 2"),
    ("data/items_v2/candidates_study1.csv", "Set 2a: v2 candidates", "Study 1"),
    ("data/items_v2/candidates_study2.csv", "Set 2b: v2 candidates (classic starting values)", "Study 2"),
    ("data/items_v2/candidates_study2_neo.csv", "Set 2c: asteroid orbits", "Study 2"),
    ("data/items_v2/candidates_study2_events.csv", "Set 2d: 2026 events and films", "Study 2"),
]
PICKS = {"data/items_v2/study1.csv": "picked for Study 1 (v2)",
         "data/items_v2/study2.csv": "picked for Study 2 (v2)"}

EXPERIMENTS = [
    # number, name, date, models, data folder, what was asked, cost, report
    (1, "Pilot run 1", "2026-10-24", "R1-Distill-Qwen-1.5B", "data/pilot",
     "Set 1 (30 questions): no anchor, Study 1, Study 2", "free (Colab T4)", "exp1_pilot_run1"),
    (2, "Pilot run 2", "2026-10-26", "Qwen3-32B", "data/pilot",
     "Set 1 (30 questions): no anchor, Study 1, Study 2", "$1.52", "exp2_pilot_run2"),
    (3, "Screening, round 1", "2026-10-26", "Qwen3-32B, R1-Distill-Qwen-1.5B", "data/screen_v2",
     "Sets 2a + 2b (206 questions), no anchor", "$0.97", "exp3_screening1"),
    (4, "Screening, round 2", "2026-10-26", "Qwen3-32B, R1-Distill-Qwen-1.5B", "data/screen_v2",
     "Sets 2c + 2d (93 questions), no anchor", "$0.44", "exp4_screening2"),
    (5, "Study 2, large model", "2026-10-28 to 29", "Qwen3-32B", "data/pilot_v2",
     "10 picked Study 2 questions: own vs given starting value", "$0.62", "exp5_study2"),
    (6, "Study 1, new questions", "2026-10-30", "Qwen3-32B, R1-Distill-Qwen-1.5B", "data/pilot_v2",
     "15 picked Study 1 questions: no anchor, then anchored", "$0.94", "exp6_study1"),
    (7, "Study 2, small model", "2026-10-30", "R1-Distill-Qwen-1.5B", "data/pilot_v2",
     "10 picked Study 2 questions: own vs given starting value", "free (Colab T4)", "exp7_study2_small"),
]
MODEL_SHORT = {"qwen3-32b": "32B", "r1-distill-qwen-1.5b": "1.5B", "qwen3-14b": "14B"}

ANSWER_COLUMNS = ["experiment", "model", "phase", "thinking_level", "thinking_budget",
                  "anchor", "direction", "distance", "precision", "start_source", "instruction",
                  "sample", "comparison", "estimate_saved", "estimate_checked", "thinking_tokens",
                  "thinking_cut_off", "answer_cut_off", "cell_id", "raw_file", "answer"]


def experiment_of(folder: str, row: dict) -> int | None:
    model, study, item = row["model"], row["study"], row["item_id"]
    if folder == "pilot":
        return 1 if model == "r1-distill-qwen-1.5b" else 2 if model == "qwen3-32b" else None
    if folder == "screen_v2":
        return 4 if item.startswith(("C2-1", "C2-2")) else 3
    if folder == "pilot_v2":
        if study == "study2":
            return 5 if model == "qwen3-32b" else 7 if model == "r1-distill-qwen-1.5b" else None
        return 6
    return None


def phase_of(study: str) -> str:
    return {"baseline": "no anchor", "study1": "Study 1 (anchor given)",
            "study2": "Study 2 (starting value)"}.get(study, "screening (no anchor)")


def num(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return f"{x:g}" if isinstance(x, float) else str(x)


def load_questions() -> tuple[dict, list]:
    questions, order = {}, []
    for path, qset, study in QUESTION_FILES:
        with open(ROOT / path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row = {k: (v or "").strip() for k, v in row.items()}
                row.update(question_set=qset, study=study, file=path, picked="")
                questions[row["item_id"]] = row
                order.append(row["item_id"])
    for path, label in PICKS.items():
        with open(ROOT / path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                questions[row["item_id"]]["picked"] = label
    return questions, order


def main() -> None:
    questions, order = load_questions()
    answers = defaultdict(list)
    per_exp = Counter()
    per_exp_models = defaultdict(set)
    changed = Counter()
    for folder in ("pilot", "screen_v2", "pilot_v2"):
        for path in sorted(glob.glob(str(ROOT / "data" / folder / "raw" / "*" / "*" / "*.jsonl.gz"))):
            rel = Path(path).relative_to(ROOT).as_posix()
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    exp = experiment_of(folder, r)
                    q = questions[r["item_id"]]
                    checked = parse_estimate(r.get("answer") or "", fallback=False, unit=q["unit"])
                    saved = r.get("estimate")
                    if not (saved == checked or (saved is None and checked is None)):
                        changed[exp] += 1
                    per_exp[exp] += 1
                    per_exp_models[exp].add(MODEL_SHORT.get(r["model"], r["model"]))
                    answers[r["item_id"]].append({
                        "experiment": exp, "model": r["model"], "phase": phase_of(r["study"]),
                        "thinking_level": r.get("thinking_level", ""),
                        "thinking_budget": r.get("budget", ""),
                        "anchor": num(r.get("anchor")), "direction": r.get("direction", ""),
                        "distance": r.get("distance", ""), "precision": r.get("precision", ""),
                        "start_source": {"self": "own", "provided": "given"}.get(r.get("source"), r.get("source") or ""),
                        "instruction": r.get("instruction", ""), "sample": r.get("sample", ""),
                        "comparison": r.get("comparison") or "",
                        "estimate_saved": num(saved), "estimate_checked": num(checked),
                        "thinking_tokens": r.get("thinking_tokens", ""),
                        "thinking_cut_off": r.get("thinking_truncated", ""),
                        "answer_cut_off": r.get("answer_finish_reason") == "length",
                        "cell_id": r["cell_id"], "raw_file": rel,
                        "answer": (r.get("answer") or "").strip(),
                    })

    # answers/<id>.csv
    adir = OUT / "answers"
    adir.mkdir(parents=True, exist_ok=True)
    for old in adir.glob("*.csv"):
        old.unlink()
    for item_id, rows in answers.items():
        rows.sort(key=lambda a: (a["experiment"], a["model"], a["cell_id"], a["sample"]))
        with open(adir / f"{item_id}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ANSWER_COLUMNS)
            w.writeheader()
            w.writerows(rows)

    # questions.csv
    qcols = ["item_id", "question_set", "study", "question", "unit", "truth", "reference", "domain",
             "source", "truth_note", "picked", "experiments", "answers_total", "answers_32B",
             "answers_1.5B", "file", "answers_file"]
    qrows = []
    for item_id in order:
        q = questions[item_id]
        rows = answers.get(item_id, [])
        exps = sorted({a["experiment"] for a in rows})
        by_model = Counter(MODEL_SHORT.get(a["model"], a["model"]) for a in rows)
        qrows.append({**{k: q.get(k, "") for k in qcols},
                      "experiments": "; ".join(str(e) for e in exps) or "never asked",
                      "answers_total": len(rows), "answers_32B": by_model.get("32B", 0),
                      "answers_1.5B": by_model.get("1.5B", 0),
                      "answers_file": f"index/answers/{item_id}.csv" if rows else ""})
    with open(OUT / "questions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=qcols)
        w.writeheader()
        w.writerows(qrows)

    # experiments.csv
    with open(OUT / "experiments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["experiment", "name", "date", "models", "data_folder", "what_was_asked",
                    "answers", "answers_reparsed_differently", "cost", "report"])
        for n, name, date, models, folder, what, cost, report in EXPERIMENTS:
            w.writerow([n, name, date, models, folder, what, per_exp[n], changed[n], cost,
                        f"latex/reports/{report}.tex"])

    # questions.md
    lines = ["# Every question in the project", "",
             "Made by `scripts/build_index.py`; do not edit by hand. The same data is in "
             "[questions.csv](questions.csv). Click a number in the *Answers* column to see every "
             "answer the models gave to that question. Experiments are numbered as in "
             "[experiments.csv](experiments.csv) and the reports.", ""]
    for qset in dict.fromkeys(q["question_set"] for q in questions.values()):
        rows = [r for r in qrows if r["question_set"] == qset]
        asked = sum(r["answers_total"] > 0 for r in rows)
        lines += [f"## {qset} ({len(rows)} questions, {asked} asked)", "",
                  "| ID | Question | Unit | True answer | Starting value | Picked | Experiments | Answers |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in rows:
            link = f"[{r['answers_total']}](answers/{r['item_id']}.csv)" if r["answers_total"] else "0"
            text = r["question"].replace("|", "\\|")
            lines.append(f"| {r['item_id']} | {text} | {r['unit']} | {r['truth']} | {r['reference']} | "
                         f"{'yes, ' + r['picked'].split(' for ')[1] if r['picked'] else ''} | "
                         f"{r['experiments']} | {link} |")
        lines.append("")
    (OUT / "questions.md").write_text("\n".join(lines), encoding="utf-8")

    total = sum(per_exp.values())
    print(f"{len(qrows)} questions, {len(answers)} asked, {total} answers")
    for n, *_ in EXPERIMENTS:
        print(f"  experiment {n}: {per_exp[n]} answers, models {sorted(per_exp_models[n])}, "
              f"{changed[n]} re-read differently")


if __name__ == "__main__":
    main()
