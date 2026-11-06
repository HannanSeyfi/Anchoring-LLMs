"""Figures and the Markdown report for one model. Every figure's numbers are saved next to it."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOW_C, HIGH_C = "#1f77b4", "#d62728"   # blue = low entity, red = high entity
ORDER = ["B", "B2", "C1", "C2", "C3", "LT", "LA", "HT", "HA", "C4"]


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def fig_contrasts(summary: pd.DataFrame, path: Path, title: str) -> None:
    plt = _plt()
    s = summary.reset_index(drop=True)
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(s) + 1.2))
    for off, role, col in ((-0.15, "low", LOW_C), (0.15, "high", HIGH_C)):
        m = s[f"{role}_mean"]
        lo, hi = m - s[f"{role}_ci_lo"], s[f"{role}_ci_hi"] - m
        ax.errorbar(m, y + off, xerr=[lo.fillna(0), hi.fillna(0)], fmt="o", color=col,
                    label=f"{role} entity", capsize=3)
    ax.axvline(0, color="grey", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(s["contrast"].str.replace("_vs_", " vs ").str.replace("_", " "))
    ax.invert_yaxis()
    ax.set_xlabel("Assimilation towards the other entity (log1p units; > 0 = towards)")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    s.to_csv(path.with_suffix(".csv"), index=False)


def fig_conditions(df: pd.DataFrame, path: Path) -> None:
    """Mean z minus the entity's B mean, per condition and role (95% bootstrap CI over pairs)."""
    plt = _plt()
    d = df[df["valid"] & df["role"].isin(["low", "high"])].copy()
    base = df[df["valid"] & (df["condition"] == "B")].groupby("target_entity_id")["z"].mean()
    d["dz"] = d["z"] - d["target_entity_id"].map(base)
    cell = d.groupby(["pair_id", "role", "condition"])["dz"].mean().reset_index()
    rng = np.random.default_rng(0)
    rows = []
    for (role, cond), g in cell.groupby(["role", "condition"]):
        v = g["dz"].dropna().values
        if len(v) == 0:
            continue
        b = rng.choice(v, (1000, len(v))).mean(1) if len(v) > 1 else np.array([v[0]])
        rows.append(dict(role=role, condition=cond, mean=v.mean(), lo=np.quantile(b, .025), hi=np.quantile(b, .975), pairs=len(v)))
    t = pd.DataFrame(rows)
    if t.empty:
        return
    conds = [c for c in ORDER if c in set(t["condition"])]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(len(conds))
    for off, role, col in ((-0.15, "low", LOW_C), (0.15, "high", HIGH_C)):
        r = t[t["role"] == role].set_index("condition").reindex(conds)
        ax.errorbar(x + off, r["mean"], yerr=[(r["mean"] - r["lo"]).fillna(0), (r["hi"] - r["mean"]).fillna(0)],
                    fmt="o", color=col, capsize=3, label=f"{role} entity")
    ax.axhline(0, color="grey", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(conds)
    ax.set_ylabel("Estimate vs plain baseline B\n(log1p units)")
    ax.set_title("Estimates in each condition (low entity should rise, high entity fall)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    t.to_csv(path.with_suffix(".csv"), index=False)


def fig_pairs(pe: pd.DataFrame, path: Path) -> None:
    plt = _plt()
    w = pe.pivot_table(index="pair_id", columns="role", values="assim_comparison_vs_C1")
    if w.empty or not {"low", "high"} <= set(w.columns):
        return
    ds = pe.drop_duplicates("pair_id").set_index("pair_id")["dataset"]
    fig, ax = plt.subplots(figsize=(5, 5))
    for name, g in w.groupby(ds.reindex(w.index)):
        ax.scatter(g["low"], g["high"], s=18, label=name)
    ax.axhline(0, color="grey", lw=1)
    ax.axvline(0, color="grey", lw=1)
    ax.set_xlabel("Low entity: assimilation (comparison - C1)")
    ax.set_ylabel("High entity: assimilation (comparison - C1)")
    ax.set_title("Each pair (top right = both moved towards each other)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    w.reset_index().to_csv(path.with_suffix(".csv"), index=False)


def fig_uncertainty(pe: pd.DataFrame, path: Path) -> None:
    plt = _plt()
    d = pe.dropna(subset=["sd_B", "assim_comparison_vs_C1"])
    if len(d) < 3:
        return
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for role, col in (("low", LOW_C), ("high", HIGH_C)):
        g = d[d["role"] == role]
        ax.scatter(g["sd_B"], g["assim_comparison_vs_C1"], s=16, color=col, label=f"{role} entity")
    ax.axhline(0, color="grey", lw=1)
    ax.set_xlabel("Spread of the entity's baseline answers (sd of log1p)")
    ax.set_ylabel("Assimilation (comparison - C1)")
    ax.set_title("Weaker prior, bigger pull?")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    d[["pair_id", "role", "entity_id", "sd_B", "assim_comparison_vs_C1"]].to_csv(path.with_suffix(".csv"), index=False)


def fig_accuracy(acc: pd.DataFrame, path: Path) -> None:
    plt = _plt()
    if acc.empty:
        return
    a = acc[acc["condition"].isin(ORDER)]
    conds = [c for c in ORDER if c in set(a["condition"])]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = np.arange(len(conds))
    for off, role, col in ((-0.2, "low", LOW_C), (0.2, "high", HIGH_C)):
        r = a[a["role"].fillna("") == role].set_index("condition").reindex(conds)
        ax.bar(x + off, r["abs_log_error"], width=0.4, color=col, label=f"{role} entity")
    r = a[a["role"].fillna("") == ""].set_index("condition").reindex(conds)
    ax.bar(x, r["abs_log_error"], width=0.4, color="grey", alpha=0.5, label="baselines")
    ax.set_xticks(x)
    ax.set_xticklabels(conds)
    ax.set_ylabel("Mean |log1p error|")
    ax.set_title("Accuracy by condition (lower = closer to the truth)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


KP_CONTRASTS = ("comparison_vs_C1", "comparison_vs_B", "comparison_vs_B2", "belief_comparison_vs_C1", "C3_vs_C1",
                "C4_pull")


def _kp(t):
    """The known-partner table, only the contrasts that answer its question."""
    return t[t["contrast"].isin(KP_CONTRASTS)]


def write_report(out: Path, df: pd.DataFrame, pe: pd.DataFrame, res: dict, meta: dict, cfg: dict) -> None:
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    if len(res["overall"]):
        fig_contrasts(res["overall"], figs / "contrasts_overall.png", "All primary pairs")
    for ds, g in res["by_dataset"].groupby("dataset") if len(res["by_dataset"]) else []:
        fig_contrasts(g, figs / f"contrasts_{ds}.png", f"Dataset: {ds}")
    fig_conditions(df, figs / "conditions.png")
    fig_pairs(pe, figs / "pairs_low_vs_high.png")
    fig_uncertainty(pe, figs / "uncertainty.png")
    fig_accuracy(res["accuracy"], figs / "accuracy.png")
    fmt = lambda t: t.to_markdown(index=False, floatfmt=".3f") if len(t) else "(none)"  # noqa: E731
    cols = ["contrast", "low_mean", "low_ci_lo", "low_ci_hi", "low_pairs", "high_mean", "high_ci_lo", "high_ci_hi",
            "high_pairs", "pattern", "converge", "converge_ci_lo", "converge_ci_hi", "common_shift",
            "common_shift_ci_lo", "common_shift_ci_hi"]
    banner = ("> **SIMULATED DATA.** These numbers come from the simulated test model, not from any LLM. "
              "They only show that the pipeline works.\n\n" if meta["simulated"] else "")
    lines = [f"# Bidirectional anchoring: {meta['model']} (thinking {meta['level']})", "", banner,
             f"{meta['trials']} trials, {meta['valid']} with a number; {meta['pairs']} pairs.", "",
             "Assimilation is in log1p units: 0.10 means the estimate moved about 10% towards the other entity. "
             "Intervals are 95% bootstrap intervals over pairs. The two directions are tested separately. "
             "converge = (low + high) / 2 per pair: the two estimates move towards each other. "
             "common_shift = (low - high) / 2: both estimates rise together (also the low/high asymmetry). "
             "belief_* rows sign 'towards the partner' by the model's own baselines instead of the true values; "
             "C4_pull is the move towards the number given, measured from the model's own baseline.", "",
             "## Main result (all primary pairs)", "", fmt(res["overall"][cols]) if len(res["overall"]) else "(none)", "",
             "![](figures/contrasts_overall.png)", "", "![](figures/conditions.png)", "",
             *(["## Known partner: obscure item vs famous item", "",
                "Each pair is one obscure item and one famous item. For each side, `low` = pairs where that item "
                "is the lower of the two (a pull towards the partner means its estimate goes up), `high` = pairs "
                "where it is the higher (goes down). Prediction: the obscure item moves in both directions, the "
                "famous one hardly moves. converge and common_shift are empty here because a side holds only "
                "one role per pair.", "",
                fmt(_kp(res["known_partner"])[["kp_side"] + cols[:10]]), "", "By domain:", "",
                fmt(_kp(res["known_partner_by_domain"])[["kp_side", "domain"] + cols[:10]]), ""]
               if "known_partner" in res else []),
             *(["## Two partners: estimate after the taller partner minus after the shorter one", "",
                "Each obscure item was compared once with a taller and once with a shorter famous item. "
                "`taller_minus_shorter` > 0 means the estimate follows the partner (log1p units, over items); "
                "`index` divides by the gap between the two partners (1 = the estimate moves as far as the "
                "partners differ, 0 = not at all). Whatever a condition does by itself cancels in the difference. "
                "`comparison` is the main test; `C4` is the same partners given as plain numbers.", "",
                fmt(res["two_partner"]), ""] if "two_partner" in res else []),
             "## The comparison against each control", "",
             "Each control moves the estimates by itself, so the comparison effect is shown against the plain "
             "baseline (B), the two-turn baseline (B2) and the co-mention (C1). `robust` = the 95% interval is on "
             "the same side of zero against all three (+ = towards the partner).", "",
             fmt(res["controls_side_by_side"]), "",
             "## By dataset", "", fmt(res["by_dataset"][["dataset"] + cols]) if len(res["by_dataset"]) else "(none)", "",
             "## Self-consistency: by the turn-1 answer", "", fmt(res["self_consistency"]), "",
             "## Without trials whose turn-1 reply contained numbers", "",
             fmt(res["without_contaminated"][cols]) if len(res["without_contaminated"]) else "(none)", "",
             "## Robustness: whole-tournament totals", "",
             fmt(res["robustness_tournament_totals"][cols]) if len(res["robustness_tournament_totals"]) else "(none)", "",
             "## Mixed model (check)", "", fmt(res["mixed_model"]), "",
             "## Accuracy", "", fmt(res["accuracy"]), "", "![](figures/accuracy.png)", "",
             "## Prior strength", "", fmt(res["uncertainty"]), "", "![](figures/uncertainty.png)", "",
             "## Triplets", "", fmt(res["triplets"]), "",
             "## Replies without a number", "", fmt(res["exclusions"]), "",
             "![](figures/pairs_low_vs_high.png)", ""]
    (out / "report.md").write_text("\n".join(lines))
