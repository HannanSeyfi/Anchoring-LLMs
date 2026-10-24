"""Pilot analysis: data quality, Study 1 mechanism signatures, Study 2 adjustment.

Everything here is descriptive. Items are the unit of analysis: medians are
taken within each cell, then averaged over items with bootstrap intervals.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .parsing import parse_numbers
from .run import read_records

LEVEL_ORDER = ["off", "low", "high"]


# ----------------------------------------------------------------------------- loading

def load_study(out_dir: str | Path, study: str) -> pd.DataFrame:
    rows = []
    for path in sorted(Path(out_dir, "raw").glob(f"*/{study}")):
        rows.extend(read_records(path))
    df = pd.DataFrame(rows)
    if not df.empty:
        df["thinking_level"] = pd.Categorical(df["thinking_level"], LEVEL_ORDER, ordered=True)
    return df


def load_anchors(out_dir: str | Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(Path(out_dir, "anchors").glob("*.json"))}


def bootstrap_mean(values, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return (np.nan, np.nan, np.nan)
    if len(v) == 1:
        return (float(v[0]), np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boots = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    return (float(v.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975)))


def summarise_over_items(df: pd.DataFrame, value: str, by: list[str]) -> pd.DataFrame:
    """Mean over items with a bootstrap interval; cells within an item are averaged first."""
    out = []
    for keys, g in df.groupby(by, observed=True):
        per_item = g.groupby("item_id")[value].mean().dropna()
        mean, lo, hi = bootstrap_mean(per_item)
        keys = keys if isinstance(keys, tuple) else (keys,)
        out.append({**dict(zip(by, keys)), "mean": mean, "ci_low": lo, "ci_high": hi,
                    "n_items": len(per_item)})
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- data quality

def data_quality(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = []
    for study, df in frames.items():
        if df.empty:
            continue
        for (model, level), g in df.groupby(["model", "thinking_level"], observed=True):
            out.append({
                "study": study, "model": model, "thinking_level": level, "answers": len(g),
                "parse_rate": g["estimate"].notna().mean(),
                "mean_thinking_tokens": g["thinking_tokens"].mean(),
                "truncated_rate": g["thinking_truncated"].mean(),
            })
    return pd.DataFrame(out)


def memorised_items(anchors: dict[str, dict], max_log_width: float = 0.02) -> pd.DataFrame:
    """Items whose unanchored answers barely vary (raw 5-95% range under ~5%)."""
    out = []
    for model, items in anchors.items():
        for item_id, entry in items.items():
            rng = entry.get("range")
            if not rng:
                out.append({"model": model, "item_id": item_id, "status": entry.get("excluded")})
                continue
            if rng["log_scale"] and rng["lo"] > 0:
                raw_width = math.log10(rng["hi"]) - math.log10(rng["lo"])
                if raw_width < max_log_width:
                    out.append({"model": model, "item_id": item_id,
                                "status": f"likely memorised (range {rng['lo']:g}-{rng['hi']:g})"})
    return pd.DataFrame(out, columns=["model", "item_id", "status"])


# ----------------------------------------------------------------------------- Study 1

def _tr(x, log_scale: bool):
    return math.log10(x) if log_scale else x


def study1_cells(s1: pd.DataFrame, base: pd.DataFrame, anchors: dict[str, dict]) -> pd.DataFrame:
    """One row per anchored cell with medians, the anchor, and the proportional shift.

    shift = (median anchored - median baseline) / (anchor - median baseline),
    computed on a log scale for positive quantities: 0 = no pull, 1 = answer equals anchor.
    """
    if s1.empty:
        return pd.DataFrame()
    bmed = (base.dropna(subset=["estimate"])
            .groupby(["model", "item_id", "thinking_level"], observed=True)["estimate"].median())
    rows = []
    keys = ["model", "item_id", "thinking_level", "direction", "distance", "precision"]
    for k, g in s1.dropna(subset=["estimate"]).groupby(keys, observed=True):
        model, item_id, level, direction, distance, precision = k
        rng = anchors.get(model, {}).get(item_id, {}).get("range")
        if rng is None or (model, item_id, level) not in bmed.index:
            continue
        log = rng["log_scale"]
        est = g["estimate"]
        if log:
            est = est[est > 0]
            if est.empty:
                continue
        y, b, a = float(est.median()), float(bmed[(model, item_id, level)]), float(g["anchor"].iloc[0])
        if log and b <= 0:
            continue
        edge = rng["hi"] if direction == "high" else rng["lo"]
        denom = _tr(a, log) - _tr(b, log)
        shift = (_tr(y, log) - _tr(b, log)) / denom if denom else np.nan
        boundary_shift = (_tr(edge, log) - _tr(b, log)) / denom if denom else np.nan
        beyond = (est > edge) if direction == "high" else (est < edge)
        rows.append({
            "model": model, "item_id": item_id, "thinking_level": level, "direction": direction,
            "distance": distance, "precision": precision, "anchor": a, "baseline_median": b,
            "anchored_median": y, "shift": shift, "boundary_shift": boundary_shift,
            "beyond_edge_rate": float(beyond.mean()), "n": len(est),
            "higher_rate": float((g["comparison"] == "higher").mean()),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["thinking_level"] = pd.Categorical(df["thinking_level"], LEVEL_ORDER, ordered=True)
    return df


def anchoring_index(s1: pd.DataFrame) -> pd.DataFrame:
    """Jacowitz & Kahneman (1995): (median_high - median_low) / (anchor_high - anchor_low)."""
    rows = []
    keys = ["model", "item_id", "thinking_level", "distance", "precision"]
    for k, g in s1.dropna(subset=["estimate"]).groupby(keys, observed=True):
        hi, lo = g[g["direction"] == "high"], g[g["direction"] == "low"]
        if hi.empty or lo.empty:
            continue
        a_hi, a_lo = hi["anchor"].iloc[0], lo["anchor"].iloc[0]
        if a_hi == a_lo:
            continue
        ai = (hi["estimate"].median() - lo["estimate"].median()) / (a_hi - a_lo)
        rows.append({**dict(zip(keys, k)), "anchoring_index": float(ai)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["thinking_level"] = pd.Categorical(df["thinking_level"], LEVEL_ORDER, ordered=True)
    return df


def near_far(cells: pd.DataFrame) -> pd.DataFrame:
    """Compare the far-anchor shift with what each account predicts.

    Shift account: the far shift equals the near shift (the whole distribution
    moves the same proportion of the way). Boundary account: answers stop at the
    range edge, so the far shift equals the edge's position relative to the far
    anchor. boundary_score = 0 means pure shift, 1 means pure boundary stopping.
    """
    if cells.empty:
        return pd.DataFrame()
    keys = ["model", "item_id", "thinking_level", "direction", "precision"]
    near = cells[cells["distance"] == "near"].set_index(keys)
    far = cells[cells["distance"] == "far"].set_index(keys)
    j = near[["shift"]].join(far[["shift", "boundary_shift"]], lsuffix="_near", rsuffix="_far",
                             how="inner").reset_index()
    j = j.rename(columns={"boundary_shift": "boundary_pred_far"})
    denom = j["shift_near"] - j["boundary_pred_far"]
    j["boundary_score"] = np.where(denom.abs() > 1e-9, (j["shift_near"] - j["shift_far"]) / denom, np.nan)
    return j


def precision_effect(cells: pd.DataFrame) -> pd.DataFrame:
    if cells.empty:
        return pd.DataFrame()
    keys = ["model", "item_id", "thinking_level", "direction", "distance"]
    p = cells.pivot_table(index=keys, columns="precision", values="shift", observed=True)
    if not {"round", "precise"} <= set(p.columns):
        return pd.DataFrame()
    p = p.reset_index()
    p["precise_minus_round"] = p["precise"] - p["round"]
    return p


# ----------------------------------------------------------------------------- Study 2

def study2_adjustment(s2: pd.DataFrame) -> pd.DataFrame:
    """Proportional adjustment from the reference value R towards the truth T.

    adjustment = (median estimate - R) / (T - R): 0 = stayed at R, 1 = reached T.
    """
    if s2.empty:
        return pd.DataFrame()
    rows = []
    keys = ["model", "item_id", "thinking_level", "source", "instruction"]
    for k, g in s2.dropna(subset=["estimate"]).groupby(keys, observed=True):
        r, t = g["reference"].iloc[0], g["truth"].iloc[0]
        if t is None or r is None or t == r:
            continue
        y = g["estimate"].median()
        rows.append({**dict(zip(keys, k)), "median_estimate": float(y), "reference": r, "truth": t,
                     "adjustment": float((y - r) / (t - r)), "n": len(g)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["thinking_level"] = pd.Categorical(df["thinking_level"], LEVEL_ORDER, ordered=True)
    return df


# ----------------------------------------------------------------------------- traces

_ADJUST = re.compile(r"\b(adjust\w*|start(?:ing)? (?:from|with|at)|subtract\w*|add(?:ing)? |"
                     r"a bit (?:less|more|lower|higher)|slightly (?:less|lower|higher|more))", re.I)
_EVIDENCE = re.compile(r"\b(I recall|I remember|I know|known|according to|reported|fact)\b", re.I)


def _close(a: float, b: float, tol: float = 0.005) -> bool:
    return b != 0 and abs(a - b) / abs(b) <= tol


def trace_features(df: pd.DataFrame) -> pd.DataFrame:
    """Simple, transparent features of each reasoning trace (not a replacement for coding)."""
    df = df[df["thinking"].fillna("").str.len() > 0].copy()
    if df.empty:
        return df
    start_vals = df["anchor"]
    if "reference" in df.columns:  # Study 2: the self-generated start is the reference value
        start_vals = start_vals.where(start_vals.notna(), df["reference"])
    feats = []
    for text, start, est in zip(df["thinking"], start_vals, df["estimate"]):
        nums = parse_numbers(text)
        has = start is not None and not (isinstance(start, float) and math.isnan(start))
        feats.append({
            "n_numbers": len(nums),
            "mentions_start": bool(has and any(_close(x, start) for x in nums)),
            "first_number_is_start": bool(has and nums and _close(nums[0], start)),
            "adjust_words": len(_ADJUST.findall(text)),
            "evidence_words": len(_EVIDENCE.findall(text)),
            "final_in_trace": bool(est is not None and any(_close(x, est, 0.001) for x in nums)),
        })
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(feats)], axis=1)


def hand_coding_sample(frames: dict[str, pd.DataFrame], n: int = 200, seed: int = 0) -> pd.DataFrame:
    """A stratified sample of traces for hand coding, with empty columns for the codes."""
    parts = []
    for study in ("study1", "study2"):
        df = frames.get(study, pd.DataFrame())
        if df.empty:
            continue
        df = df[df["thinking"].fillna("").str.len() > 0]
        parts.append(df.sample(min(len(df), n // 2), random_state=seed))
    if not parts:
        return pd.DataFrame()
    s = pd.concat(parts).reset_index(drop=True)
    cols = ["study", "model", "item_id", "thinking_level", "direction", "distance", "precision",
            "source", "instruction", "anchor", "reference", "prompt", "thinking", "answer", "estimate"]
    s = s[[c for c in cols if c in s.columns]].copy()
    s.insert(0, "trace_id", [f"T{i:04d}" for i in range(len(s))])
    s["code"] = ""   # adjusting / retrieving / dismissing / none
    s["coder_notes"] = ""
    return s


# ----------------------------------------------------------------------------- figures

def _plot_lines(ax, summ: pd.DataFrame, group: str, title: str, ylabel: str):
    for name, g in summ.groupby(group, observed=True):
        g = g.sort_values("thinking_level")
        x = [LEVEL_ORDER.index(str(lv)) for lv in g["thinking_level"]]
        yerr = [g["mean"] - g["ci_low"], g["ci_high"] - g["mean"]]
        ax.errorbar(x, g["mean"], yerr=yerr, marker="o", capsize=3, label=str(name))
    ax.set_xticks(range(len(LEVEL_ORDER)), LEVEL_ORDER)
    ax.set_xlabel("reasoning level")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.axhline(0, color="grey", lw=0.8)
    ax.legend(fontsize=8)


def make_figures(results: dict[str, pd.DataFrame], fig_dir: str | Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = Path(fig_dir)
    fig_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    ai = results.get("anchoring_index", pd.DataFrame())
    if not ai.empty:
        models = sorted(ai["model"].unique())
        fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 4), squeeze=False)
        for ax, m in zip(axes[0], models):
            summ = summarise_over_items(ai[ai["model"] == m], "anchoring_index",
                                        ["distance", "thinking_level"])
            _plot_lines(ax, summ, "distance", f"Study 1 anchoring index: {m}", "anchoring index")
        fig.tight_layout()
        paths.append(fig_dir / "study1_anchoring_index.png")
        fig.savefig(paths[-1], dpi=150)
        plt.close(fig)

    nf = results.get("near_far", pd.DataFrame())
    if not nf.empty:
        models = sorted(nf["model"].unique())
        fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 4), squeeze=False)
        # Shift account: far = near. Boundary account: far = the boundary prediction.
        labels = {"shift_near": "near anchor", "shift_far": "far anchor",
                  "boundary_pred_far": "far, if answers stopped at the range edge"}
        long = nf.melt(id_vars=["model", "item_id", "thinking_level"], value_vars=list(labels),
                       var_name="measure", value_name="shift")
        long["measure"] = long["measure"].map(labels)
        for ax, m in zip(axes[0], models):
            summ = summarise_over_items(long[long["model"] == m], "shift", ["measure", "thinking_level"])
            _plot_lines(ax, summ, "measure", f"Study 1 shift or boundary stop: {m}",
                        "shift towards anchor (0 = none, 1 = anchor)")
        fig.tight_layout()
        paths.append(fig_dir / "study1_near_far.png")
        fig.savefig(paths[-1], dpi=150)
        plt.close(fig)

    adj = results.get("study2_adjustment", pd.DataFrame())
    if not adj.empty:
        models = sorted(adj["model"].unique())
        instr = [i for i in ["none", "accuracy", "opposite"] if i in set(adj["instruction"])]
        fig, axes = plt.subplots(len(models), len(instr), figsize=(4.5 * len(instr), 3.8 * len(models)),
                                 squeeze=False)
        for r, m in enumerate(models):
            for c, ins in enumerate(instr):
                sub = adj[(adj["model"] == m) & (adj["instruction"] == ins)]
                summ = summarise_over_items(sub, "adjustment", ["source", "thinking_level"])
                _plot_lines(axes[r][c], summ, "source", f"{m} | instruction: {ins}",
                            "adjustment (0 = reference, 1 = truth)")
                axes[r][c].axhline(1, color="grey", lw=0.8, ls="--")
        fig.tight_layout()
        paths.append(fig_dir / "study2_adjustment.png")
        fig.savefig(paths[-1], dpi=150)
        plt.close(fig)

    q = results.get("data_quality", pd.DataFrame())
    if not q.empty:
        fig, ax = plt.subplots(figsize=(6, 4))
        for (m, st), g in q.groupby(["model", "study"]):
            g = g.sort_values("thinking_level")
            ax.plot([LEVEL_ORDER.index(str(x)) for x in g["thinking_level"]],
                    g["mean_thinking_tokens"], marker="o", label=f"{m} {st}")
        ax.set_xticks(range(len(LEVEL_ORDER)), LEVEL_ORDER)
        ax.set_ylabel("mean realised thinking tokens")
        ax.set_title("Reasoning budget control")
        ax.legend(fontsize=7)
        fig.tight_layout()
        paths.append(fig_dir / "thinking_tokens.png")
        fig.savefig(paths[-1], dpi=150)
        plt.close(fig)
    return paths


# ----------------------------------------------------------------------------- report

def _fmt_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    if df.empty:
        return "_No data._\n"
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f":
            df[c] = df[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    header = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = "\n".join("| " + " | ".join(map(str, r)) + " |" for r in df.astype(str).values)
    return "\n".join([header, sep, body]) + "\n"


def analyse(out_dir: str | Path, results_dir: str | Path) -> dict[str, pd.DataFrame]:
    out_dir, results_dir = Path(out_dir), Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    frames = {s: load_study(out_dir, s) for s in ("baseline", "study1", "study2")}
    anchors = load_anchors(out_dir)

    res: dict[str, pd.DataFrame] = {"data_quality": data_quality(frames),
                                    "memorised": memorised_items(anchors)}
    cells = study1_cells(frames["study1"], frames["baseline"], anchors)
    res["study1_cells"] = cells
    res["anchoring_index"] = anchoring_index(frames["study1"]) if not frames["study1"].empty else pd.DataFrame()
    res["near_far"] = near_far(cells)
    res["precision"] = precision_effect(cells)
    res["study2_adjustment"] = study2_adjustment(frames["study2"])
    traces = pd.concat([trace_features(frames[s]) for s in ("study1", "study2") if not frames[s].empty],
                       ignore_index=True) if any(not frames[s].empty for s in ("study1", "study2")) else pd.DataFrame()
    res["trace_features"] = traces

    tables = results_dir / "tables"
    tables.mkdir(exist_ok=True)
    for name, df in res.items():
        if name != "trace_features" and not df.empty:
            df.to_csv(tables / f"{name}.csv", index=False)
    coding = hand_coding_sample(frames)
    if not coding.empty:
        coding.to_csv(results_dir / "hand_coding_sample.csv", index=False)
    figs = make_figures(res, results_dir / "figures")
    write_report(res, results_dir / "summary.md", figs, results_dir)
    return res


def write_report(res: dict[str, pd.DataFrame], path: Path, figs: list[Path], results_dir: Path) -> None:
    lines = ["# Pilot results", "",
             "Generated by `anchoring_llms.analysis`. All numbers are averaged over items; "
             "brackets are 95% bootstrap intervals over items.", ""]

    lines += ["## 1. Data quality", "", _fmt_table(res["data_quality"])]
    mem = res["memorised"]
    lines += ["### Items to drop or replace", "",
              _fmt_table(mem) if not mem.empty else "None flagged.\n"]

    ai = res["anchoring_index"]
    lines += ["## 2. Study 1: does anchoring appear?", "",
              "Anchoring index (Jacowitz & Kahneman, 1995). Humans typically score 0.4-0.6.", ""]
    if not ai.empty:
        lines.append(_fmt_table(summarise_over_items(ai, "anchoring_index",
                                                     ["model", "thinking_level", "distance"])))
    nf = res["near_far"]
    lines += ["## 3. Study 1: shift or boundary stopping?", "",
              "Boundary score: 0 means the whole answer distribution shifts towards the anchor "
              "(selective accessibility); 1 means answers stop at the edge of the plausible range "
              "(insufficient adjustment).", ""]
    if not nf.empty:
        agg = (nf.groupby(["model", "thinking_level"], observed=True)
               [["shift_near", "shift_far", "boundary_pred_far"]].mean().reset_index())
        agg["boundary_score"] = ((agg["shift_near"] - agg["shift_far"])
                                 / (agg["shift_near"] - agg["boundary_pred_far"]))
        lines.append("Mean proportional shift towards the anchor (0 = none, 1 = answer equals anchor), "
                     "and the far-anchor shift that boundary stopping would predict:\n")
        lines.append(_fmt_table(agg))
    pr = res["precision"]
    lines += ["## 4. Study 1: precise vs round anchors", "",
              "Positive values mean precise anchors pulled harder (the adjustment prediction).", ""]
    if not pr.empty:
        lines.append(_fmt_table(summarise_over_items(pr, "precise_minus_round", ["model", "thinking_level"])))
    adj = res["study2_adjustment"]
    lines += ["## 5. Study 2: self-generated vs provided anchors", "",
              "Adjustment: 0 = answer stayed at the reference value, 1 = reached the true value. "
              "The key prediction is that more reasoning increases adjustment for `self` but not `provided`.", ""]
    if not adj.empty:
        lines.append(_fmt_table(summarise_over_items(adj, "adjustment",
                                                     ["model", "instruction", "source", "thinking_level"])))
    tf = res["trace_features"]
    lines += ["## 6. Reasoning traces (simple features)", ""]
    if not tf.empty:
        g = tf.groupby(["study", "model", "thinking_level"], observed=True)[
            ["mentions_start", "first_number_is_start", "adjust_words", "evidence_words"]].mean().reset_index()
        lines.append(_fmt_table(g))
        lines.append("A stratified sample for hand coding is in `hand_coding_sample.csv`.\n")
    if figs:
        lines += ["## Figures", ""] + [f"![{p.stem}](figures/{p.name})" for p in figs] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Analyse pilot data.")
    ap.add_argument("--data", default="data/pilot")
    ap.add_argument("--out", default="results/pilot")
    args = ap.parse_args(argv)
    analyse(args.data, args.out)
    print(f"Wrote {args.out}/summary.md")


if __name__ == "__main__":
    main()
