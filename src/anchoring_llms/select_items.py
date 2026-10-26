"""Pick the final v2 questions from the screening answers.

For each candidate question and each screened model, the unanchored answers
saved by `anchoring_llms.screen` give, per thinking level:

  parsed       share of answers that contained a number
  q10/q90      the 10th and 90th percentile of the answers (median = 50th)
  spread       log10(q90 / q10): 0 = the same answer every time, 0.3 = the high
               answers are twice the low ones, 1 = ten times
  known        share of answers within 2% of the true value
  adjustment   Study 2 only: (median - R) / (T - R), where R is the value a solver
               naturally starts from and T the true value (0 = stayed at R, 1 = reached T)

A question is kept when the reference model (the largest one, which knows the
most) does not know it and is unsure about it, and every screened model
answered it with a number often enough. The limits are in the `screening`
section of configs/pilot_v2.yaml. The picked questions go to the config's
`items` files (data/items_v2/study1.csv and study2.csv), and a plain-language
report to results/screen_v2/screening.md.

Usage (from the repository root):
    python -m anchoring_llms.select_items --config configs/pilot_v2.yaml --sync
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import _close, _fmt_table
from .git_sync import GitSync
from .parsing import parse_numbers
from .run import load_config, read_records
from .screen import STUDIES, candidate_files, load_candidates, screen_dirs

NAN = float("nan")


# ----------------------------------------------------------------------------- statistics

def load_screening(out_dir: str | Path, study: str) -> pd.DataFrame:
    rows = []
    for path in sorted(Path(out_dir, "raw").glob(f"*/{study}")):
        rows.extend(read_records(path))
    return pd.DataFrame(rows)


def _spread(lo: float, hi: float) -> float:
    return math.log10(hi / lo) if lo > 0 and hi > 0 else NAN


def _mentions(text: str, value: float) -> bool:
    return any(_close(x, value) for x in parse_numbers(text or ""))


def level_stats(df: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    """One row per model, question and thinking level."""
    out = []
    for (model, item_id, level), g in df.groupby(["model", "item_id", "thinking_level"], sort=True):
        est = g["estimate"].dropna().astype(float).to_numpy()
        truth = float(g["truth"].iloc[0])
        ref = g["reference"].iloc[0] if "reference" in g else None
        row = {"model": model, "item_id": item_id, "thinking_level": level, "answers": len(g),
               "parsed": len(est) / len(g)}
        if len(est):
            q10, q50, q90 = (float(v) for v in np.quantile(est, [0.1, 0.5, 0.9]))
            row.update(q10=q10, median=q50, q90=q90, spread=_spread(q10, q90),
                       known=float(np.mean(np.abs(est - truth) <= tolerance * abs(truth))),
                       error=abs(math.log10(q50 / truth)) if q50 > 0 and truth > 0 else NAN)
        else:
            row.update(q10=NAN, median=NAN, q90=NAN, spread=NAN, known=NAN, error=NAN)
        if ref is not None and pd.notna(ref) and truth != ref:
            row["adjustment"] = (row["median"] - ref) / (truth - ref)
            traces = g["thinking"].fillna("")
            traces = traces[traces.str.len() > 0]
            # share of reasoning traces that use the reference value (365 days, 9.81 m/s², ...)
            row["mentions_reference"] = float(traces.map(lambda t: _mentions(t, ref)).mean()) if len(traces) else NAN
        out.append(row)
    return pd.DataFrame(out)


def item_summary(levels: pd.DataFrame, level_order: list[str]) -> pd.DataFrame:
    """One row per model and question: the worst case over thinking levels, plus each level."""
    out = []
    for (model, item_id), g in levels.groupby(["model", "item_id"], sort=True):
        row = {"model": model, "item_id": item_id, "answers": int(g["answers"].sum()),
               "parsed_min": g["parsed"].min(), "known_max": g["known"].max(),
               "spread_min": g["spread"].min(skipna=False), "spread_mean": g["spread"].mean(skipna=False),
               "error_max": g["error"].max()}
        by_level = g.set_index("thinking_level")
        for level in level_order:
            if level not in by_level.index:
                continue
            x = by_level.loc[level]
            for col in ("parsed", "median", "q10", "q90", "spread", "known", "adjustment", "mentions_reference"):
                if col in x.index:
                    row[f"{col}_{level}"] = x[col]
        out.append(row)
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- selection

def known_share(r: pd.Series, rules: dict) -> float:
    """The highest share of known answers over the levels the knowledge rule checks (default: all)."""
    levels = rules.get("known_levels")
    if not levels:
        return r["known_max"]
    return max(r.get(f"known_{level}", NAN) for level in levels)


def _known_where(rules: dict) -> str:
    levels = rules.get("known_levels")
    return f"with thinking {', '.join(levels)}" if levels else "at any thinking level"


def _reasons(r: pd.Series, study: str, sc: dict, first_level: str) -> tuple[list[str], float]:
    """Why a question fails the rules on the reference model (empty if it passes), and its rank score."""
    rules, tol = sc[study], sc["known_tolerance"]
    reasons = []
    known = known_share(r, rules)
    if known > sc["max_known_share"]:
        reasons.append(f"known ({known:.0%} of answers within {tol:.0%} of the true value)")
    if study == "study1":
        score = r["spread_mean"]
        if pd.isna(r["spread_mean"]):
            reasons.append("some answers were zero or negative")
        elif r["spread_mean"] < rules["min_spread"]:
            reasons.append(f"answers too similar (spread {r['spread_mean']:.2f})")
        elif r["spread_mean"] > rules["max_spread"]:
            reasons.append(f"answers too scattered (spread {r['spread_mean']:.2f})")
        if r["error_max"] > rules["max_median_error"]:
            reasons.append(f"median {10 ** r['error_max']:.0f} times off the true value (question may be unclear)")
    else:
        a = r.get(f"adjustment_{first_level}", NAN)
        score = 1 - a
        if pd.isna(a):
            reasons.append("no answers to compute the adjustment")
        elif a < rules["min_adjustment"]:
            reasons.append(f"answers move away from the true value (adjustment {a:.2f})")
        elif a > rules["max_adjustment"]:
            what = "answers go far past the true value" if a > 1.2 else "already close to the true value"
            reasons.append(f"{what} (adjustment {a:.2f})")
        if rules.get("min_thinking_gain") is not None:
            last = sc["levels"][-1]
            b = r.get(f"adjustment_{last}", NAN)
            score = thinking_gain(a, b)
            if pd.isna(score) or score < rules["min_thinking_gain"]:
                reasons.append(f"thinking does not bring the answer closer to the true value "
                               f"(adjustment {a:.2f} with thinking {first_level}, {b:.2f} with thinking {last})")
    return reasons, (score if pd.notna(score) else -np.inf)


def thinking_gain(a: float, b: float) -> float:
    """How much closer to the true value the median gets with more thinking, in adjustment units.

    a and b are the adjustments with less and more thinking (0 = at R, 1 = at the true value).
    0.2 means the distance to the true value shrank by a fifth of the distance from R to it;
    going far past the true value counts as moving away from it.
    """
    return abs(1 - a) - abs(1 - b)


def parsed_share(o: pd.Series, sc: dict, ref_model: str) -> float:
    """The lowest share of answers with a number over the levels that the parse rule checks."""
    levels = sc.get("other_models_parse_levels")
    if o["model"] == ref_model or not levels:
        return o["parsed_min"]
    return min(o.get(f"parsed_{level}", NAN) for level in levels)


def pick(summary: pd.DataFrame, items: dict, study: str, sc: dict) -> pd.DataFrame:
    """Apply the rules, rank the questions that pass, and pick `n_items` (at most `max_per_domain` per domain).

    The question rules use the reference model; the parse rule is checked for every screened model,
    so every model can answer the picked questions in the requested format (other models only at
    `other_models_parse_levels`, when set). If too few questions pass, the gap is filled with the
    ones that fail the fewest rules, marked as such.
    """
    rules, ref_model = sc[study], sc["reference_model"]
    first_level = sc["levels"][0]
    ref = summary[summary["model"] == ref_model].set_index("item_id")
    rows = []
    for item_id, r in ref.iterrows():
        reasons, score = _reasons(r, study, sc, first_level)
        for _, o in summary[summary["item_id"] == item_id].iterrows():
            parsed = parsed_share(o, sc, ref_model)
            if parsed < sc["min_parsed"]:
                reasons.append(f"{o['model']}: only {parsed:.0%} of answers had a number")
        item = items[item_id]
        rows.append({"item_id": item_id, "domain": item.domain, "question": item.question,
                     "truth": item.truth, "reference": item.reference, **r.to_dict(),
                     "known_checked": known_share(r, rules), "score": score, "passed": not reasons, "reasons": "; ".join(reasons)})
    df = pd.DataFrame(rows).drop(columns=["model"], errors="ignore")
    if df.empty:
        return df
    if study == "study1":
        df = df.drop(columns=["reference"])

    n, cap = rules["n_items"], rules["max_per_domain"]
    df["n_reasons"] = df["reasons"].map(lambda s: len(s.split("; ")) if s else 0)
    passed = df[df["passed"]].sort_values(["score", "item_id"], ascending=[False, True])
    failed = df[~df["passed"]].sort_values(["n_reasons", "score", "item_id"], ascending=[True, False, True])
    picked: list[str] = []
    per_domain: Counter = Counter()

    def take(frame: pd.DataFrame, use_cap: bool) -> None:
        for item_id, domain in zip(frame["item_id"], frame["domain"]):
            if len(picked) >= n:
                return
            if item_id in picked or (use_cap and per_domain[domain] >= cap):
                continue
            picked.append(item_id)
            per_domain[domain] += 1

    take(passed, use_cap=True)
    take(failed, use_cap=True)
    take(passed, use_cap=False)
    take(failed, use_cap=False)

    def status(r: pd.Series) -> str:
        if r["item_id"] in picked:
            return "picked" if r["passed"] else "picked to fill a gap"
        if r["passed"]:
            return "passed, not picked (domain limit)" if per_domain[r["domain"]] >= cap else "passed, ranked lower"
        return "did not pass"

    df["status"] = df.apply(status, axis=1)
    df["rank"] = df["item_id"].map({i: k + 1 for k, i in enumerate(picked)})
    order = {"picked": 0, "picked to fill a gap": 1, "passed, ranked lower": 2,
             "passed, not picked (domain limit)": 3, "did not pass": 4}
    df = df.sort_values(by=["status", "rank", "score"], key=lambda s: s.map(order) if s.name == "status" else s,
                        ascending=[True, True, False], na_position="last")
    return df.drop(columns=["n_reasons"]).reset_index(drop=True)


def write_items(candidates: Path | list[Path], picked: list[str], target: Path) -> None:
    """Copy the picked rows of the candidate file(s) unchanged (same columns, same order)."""
    fields, rows = None, []
    for path in [candidates] if isinstance(candidates, Path) else candidates:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if fields is not None and reader.fieldnames != fields:
                raise ValueError(f"{path} has different columns from the other candidate files")
            fields = reader.fieldnames
            rows += [r for r in reader if r["item_id"] in set(picked)]
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------------------------------------------------------- report

def _num(x) -> str:
    if x is None or pd.isna(x):
        return ""
    x = float(x)
    if x == 0:
        return "0"
    digits = max(0, 3 - int(math.floor(math.log10(abs(x)))))
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{x:,.0f}"


def _short(text: str, n: int = 70) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _picked_table(df: pd.DataFrame, study: str, sc: dict, others: list[str],
                  summary: pd.DataFrame) -> str:
    lv = sc["levels"]
    rows = []
    for _, r in df[df["status"].str.startswith("picked")].iterrows():
        row = {"#": int(r["rank"]), "id": r["item_id"], "domain": r["domain"], "question": _short(r["question"]),
               "true value": _num(r["truth"])}
        if study == "study2":
            row["start value R"] = _num(r["reference"])
        for level in lv:
            row[f"middle 80% ({level})"] = f"{_num(r.get(f'q10_{level}'))} – {_num(r.get(f'q90_{level}'))}"
        row["known"] = f"{r['known_checked']:.0%}"
        if study == "study1":
            row["spread"] = f"{r['spread_mean']:.2f}"
        else:
            for level in lv:
                a = r.get(f"adjustment_{level}")
                row[f"adjustment ({level})"] = "" if pd.isna(a) else f"{a:.2f}"
        for m in others:
            o = summary[(summary["model"] == m) & (summary["item_id"] == r["item_id"])]
            row[f"{m}: known / parsed"] = (f"{o['known_max'].iloc[0]:.0%} / "
                                           f"{parsed_share(o.iloc[0], sc, sc['reference_model']):.0%}"
                                           if not o.empty else "not screened")
        row["note"] = "" if r["status"] == "picked" else "fills a gap: " + r["reasons"]
        rows.append(row)
    return _fmt_table(pd.DataFrame(rows))


def _reason_counts(df: pd.DataFrame) -> str:
    counts: Counter = Counter()
    for text in df.loc[~df["passed"], "reasons"]:
        for reason in text.split("; "):
            # "known (85% of answers ...)" -> "known"; "qwen3-32b: only 60% ..." -> "qwen3-32b: few numbers"
            key = reason.split(" (")[0]
            if ": only" in key:
                key = key.split(":")[0] + ": too few answers with a number"
            elif key.startswith("median"):
                key = "median far off the true value"
            counts[key] += 1
    if not counts:
        return "Every screened question passed.\n"
    return "\n".join(f"- {k}: {v} question{'s' if v != 1 else ''}" for k, v in counts.most_common()) + "\n"


def _domain_table(df: pd.DataFrame) -> str:
    g = df.groupby("domain").agg(candidates=("item_id", "size"), passed=("passed", "sum"),
                                 picked=("status", lambda s: int(s.str.startswith("picked").sum())))
    return _fmt_table(g.reset_index().sort_values("candidates", ascending=False))


def _example(df: pd.DataFrame, study: str, sc: dict, ref_model: str) -> list[str]:
    picked = df[df["status"] == "picked"]
    if picked.empty:
        return []
    r, lv = picked.iloc[0], sc["levels"][0]
    n = sc["samples"]
    lines = [f"**Worked example ({r['item_id']}).** *{r['question']}* The true value is {_num(r['truth'])}."]
    lines.append(f"With thinking {lv}, {ref_model} answered it {n} times. The middle 80% of its answers ran from "
                 f"{_num(r.get(f'q10_{lv}'))} to {_num(r.get(f'q90_{lv}'))}, with a median of "
                 f"{_num(r.get(f'median_{lv}'))}. "
                 + ("None of its answers" if r["known_checked"] == 0
                    else f"Only {r['known_checked']:.0%} of its answers")
                 + f" were within {sc['known_tolerance']:.0%} of the truth ({_known_where(sc[study])}), so the "
                 "model does not know this number" + (" without thinking." if sc[study].get("known_levels") else "."))
    if study == "study1":
        lines.append(f"Its spread is {r['spread_mean']:.2f}: the high answers are about "
                     f"{10 ** r['spread_mean']:.1f} times the low ones. An anchor has room to pull here.")
    else:
        a, last = r.get(f"adjustment_{lv}"), sc["levels"][-1]
        lines.append(f"Starting from R = {_num(r['reference'])}, its median moved {a:.0%} of the way to the true "
                     f"value (adjustment {a:.2f}), so there is room for more thinking to adjust further.")
        b = r.get(f"adjustment_{last}")
        if last != lv and pd.notna(b):
            lines.append(f"With thinking {last}, its median was {_num(r.get(f'median_{last}'))} "
                         f"(adjustment {b:.2f}).")
    return [" ".join(lines), ""]


def write_report(path: Path, cfg: dict, results: dict, summaries: dict, missing: dict,
                 items_paths: dict, smoke: bool) -> None:
    sc = cfg["screening"]
    ref_model = sc["reference_model"]
    tol = sc["known_tolerance"]
    lines = ["# Question screening (question set v2)", "",
             "Generated by `anchoring_llms.select_items`." + (" **Smoke test: not real data.**" if smoke else ""), "",
             "Each candidate question was asked without an anchor, "
             f"{sc['samples']} times per thinking level ({', '.join(sc['levels'])}). "
             "An anchoring question is only useful if the model does **not** know the answer: in pilot run 2, "
             "Qwen3-32B knew 13 of the 15 questions, so the anchors had nothing to pull. "
             "This screening keeps the questions the model is unsure about.", "",
             "## How to read the numbers", "",
             f"- **known**: share of answers within {tol:.0%} of the true value (the highest share over the "
             "thinking levels). High means the model knows the number.",
             "- **middle 80%**: the 10th to the 90th percentile of the answers. A wide range means the model is unsure.",
             "- **spread** (Study 1): log10 of (90th percentile / 10th percentile), averaged over levels. "
             "0 = the same answer every time, 0.3 = the high answers are twice the low ones, 1 = ten times.",
             "- **adjustment** (Study 2): (median − R) / (true value − R), where R is the value a solver starts "
             "from (365 days, 9.81 m/s², 100 °C, ...). 0 = the answer stayed at R, 1 = it reached the true value.",
             "- **parsed**: share of answers that contained a number.", "",
             "## Rules", "",
             f"Question rules are checked on **{ref_model}**, the largest screened model: a question it does not "
             "know, a smaller model does not know either. The number rule is checked on every screened model.", "",
             f"- every model: at least {sc['min_parsed']:.0%} of answers contain a number (at every level"
             + (f"; models other than {ref_model} only with thinking {', '.join(sc['other_models_parse_levels'])}"
                if sc.get("other_models_parse_levels") else "") + ")",
             f"- {ref_model}: at most {sc['max_known_share']:.0%} of answers within {tol:.0%} of the truth "
             f"(Study 1: {_known_where(sc['study1'])}; Study 2: {_known_where(sc['study2'])})",
             f"- Study 1: spread (averaged over levels) at least {sc['study1']['min_spread']} and at most "
             f"{sc['study1']['max_spread']}; median no more than "
             f"{10 ** sc['study1']['max_median_error']:.0f} times off the truth (else the question may be unclear)",
             f"- Study 2: adjustment with thinking {sc['levels'][0]} between {sc['study2']['min_adjustment']} and "
             f"{sc['study2']['max_adjustment']}"
             + (f"; with thinking {sc['levels'][-1]} the median gets closer to the truth by at least "
                f"{sc['study2']['min_thinking_gain']} (in adjustment units, so thinking has something to work with)"
                if sc["study2"].get("min_thinking_gain") is not None else ""),
             f"- Study 1: at most {sc['study1']['max_per_domain']} questions per topic, "
             f"{sc['study1']['n_items']} questions; Study 2: at most {sc['study2']['max_per_domain']} per topic, "
             f"{sc['study2']['n_items']} questions",
             "- ranking: Study 1 by spread (most unsure first); Study 2 "
             + ("by how much closer thinking brings the answer (largest first)"
                if sc["study2"].get("min_thinking_gain") is not None
                else "by how far the answer stayed from the truth (least adjustment first)"), ""]

    lines += ["## Screened models", ""]
    rows = []
    for study, summary in summaries.items():
        for model, g in summary.groupby("model"):
            rows.append({"study": study, "model": model, "questions": len(g), "answers": int(g["answers"].sum()),
                         "parsed (lowest level)": f"{g['parsed_min'].mean():.0%}",
                         "questions known": int((g["known_max"] > sc["max_known_share"]).sum())})
    lines.append(_fmt_table(pd.DataFrame(rows)))
    for study, models in missing.items():
        if models:
            lines.append(f"**Not screened yet for {study}:** {', '.join(models)}. Their number rule was not "
                         "checked; screen them and run this step again.\n")

    for study in STUDIES:
        df = results.get(study)
        title = "Study 1 (provided anchors)" if study == "study1" else "Study 2 (self-generated anchors)"
        lines += [f"## {title}", ""]
        if df is None or df.empty:
            lines += ["_Not screened._", ""]
            continue
        others = [m for m in sorted(summaries[study]["model"].unique()) if m != ref_model]
        n_pass, n_pick = int(df["passed"].sum()), int(df["status"].str.startswith("picked").sum())
        lines += [f"{len(df)} questions screened, {n_pass} passed the rules, {n_pick} picked "
                  f"→ `{items_paths[study]}`.", ""]
        lines += _example(df, study, sc, ref_model)
        lines += ["### Picked questions", "", _picked_table(df, study, sc, others, summaries[study])]
        lines += ["### Why questions were left out", "", _reason_counts(df)]
        lines += ["### By topic", "", _domain_table(df)]

    lines += ["## Files", "",
              "- `tables/<study>_by_level.csv`: every model, question and thinking level",
              "- `tables/<study>_questions.csv`: every question with the reference model's numbers, the rules it "
              "failed, and whether it was picked", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------- main

def select(cfg: dict, repo: Path, smoke: bool = False) -> dict[str, pd.DataFrame]:
    sc = cfg["screening"]
    data_dir, results_dir = (repo / d for d in screen_dirs(cfg, smoke))
    tables = results_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    results, summaries, missing, items_paths = {}, {}, {}, {}
    for study in STUDIES:
        candidates = [repo / f for f in candidate_files(cfg, study)]
        items = {it.item_id: it for it in load_candidates(repo, cfg, study)}
        df = load_screening(data_dir, study)
        if df.empty:
            print(f"[{study}] no screening answers in {data_dir}; skipped")
            continue
        df = df[df["item_id"].isin(items)].copy()
        # the candidate file is the source of truth for the true and reference values
        df["truth"] = df["item_id"].map(lambda i: items[i].truth)
        df["reference"] = df["item_id"].map(lambda i: items[i].reference)
        levels = level_stats(df, sc["known_tolerance"])
        summary = item_summary(levels, sc["levels"])
        screened = set(summary["model"])
        missing[study] = [m for m in sc["models"] if m not in screened]
        if sc["reference_model"] not in screened:
            raise SystemExit(f"[{study}] {sc['reference_model']} (the reference model) has not been screened yet. "
                             f"Screened so far: {sorted(screened) or 'none'}.")
        picked_df = pick(summary, items, study, sc)
        picked = picked_df.loc[picked_df["status"].str.startswith("picked"), "item_id"].tolist()
        target = (results_dir / "items" / f"{study}.csv") if smoke else repo / cfg["items"][study]
        write_items(candidates, picked, target)
        items_paths[study] = target.relative_to(repo) if target.is_relative_to(repo) else target
        levels.to_csv(tables / f"{study}_by_level.csv", index=False)
        picked_df.to_csv(tables / f"{study}_questions.csv", index=False)
        results[study], summaries[study] = picked_df, summary
        print(f"[{study}] {len(picked_df)} screened, {int(picked_df['passed'].sum())} passed, "
              f"{len(picked)} picked -> {items_paths[study]}")
        for m in missing[study]:
            print(f"[{study}] warning: {m} has not been screened, so its number rule was not checked")
    if not results:
        raise SystemExit(f"No screening answers found in {data_dir}. Run anchoring_llms.screen first.")
    write_report(results_dir / "screening.md", cfg, results, summaries, missing, items_paths, smoke)
    report = results_dir / "screening.md"
    print(f"Report: {report.relative_to(repo) if report.is_relative_to(repo) else report}")
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/pilot_v2.yaml")
    ap.add_argument("--smoke", action="store_true",
                    help="use the smoke-test screening; the picked questions go to the smoke results folder")
    ap.add_argument("--sync", action="store_true", help="commit and push the picked questions and the report")
    ap.add_argument("--repo", default=".", help="repository root")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    cfg = load_config(repo / args.config, smoke=args.smoke)
    if "screening" not in cfg:
        raise SystemExit(f"{args.config} has no `screening` section; use configs/pilot_v2.yaml.")
    select(cfg, repo, args.smoke)
    results_dir = repo / screen_dirs(cfg, args.smoke)[1]
    paths = [results_dir] + ([] if args.smoke else [repo / cfg["items"][s] for s in STUDIES])
    GitSync(repo, [p for p in paths if p.exists()], enabled=args.sync).maybe_sync(
        "Question set v2: picked questions and screening report", force=True)


if __name__ == "__main__":
    main()
