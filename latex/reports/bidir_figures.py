"""Figures for the bidirectional-study reports (latex/reports/exp8_bidirectional.tex and short/).

    python latex/reports/bidir_figures.py [--preview DIR]

Writes one multi-page PDF, latex/reports/figures/bidir_figures.pdf (the reports include its pages
with \\bfig{N}), and with --preview PNG copies of each page to DIR. Every number is read from the
saved results (results/bidirectional*/qwen3-32b/off/), nothing is typed in.

Pages: 1 UNSURE in run A, 2 turn-1 answers by option order, 3 numeric pull, 4 the comparison
against each control, 5 what the co-mention does alone, 6 three mountains, 7 every obscure item,
8 turn-1 answers by which item is named first.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.bidirectional.analysis import bootstrap_mean, summarise  # noqa: E402
from anchoring_llms.bidirectional.trials import load_config  # noqa: E402

R1 = ROOT / "results/bidirectional/qwen3-32b/off/tables"
R2 = ROOT / "results/bidirectional_v2/qwen3-32b/off/tables"
RK = ROOT / "results/bidirectional_kp/qwen3-32b/off/tables"
OUT = ROOT / "latex/reports/figures/bidir_figures.pdf"

ORANGE, DARK, LIGHT = "#eb6834", "#a83f14", "#f6b899"
GREY, GREY2 = "#898781", "#c3c2b7"
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9, "axes.titleweight": "bold",
    "axes.labelsize": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 7.5,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42,
})
W = 6.3
NAMES = {"wc2026": "World Cup 2026", "olympics2026": "Winter Olympics 2026", "wc2022": "World Cup 2022",
         "facts": "Known facts", "young": "Young et al. products", "kp": "Obscure vs famous item"}
ORDER = ["wc2026", "olympics2026", "wc2022", "facts", "young", "kp"]
COMP = ["LT", "LA", "HT", "HA"]


def ok(s: pd.Series) -> pd.Series:
    return s.astype(str).isin(["True", "1", "1.0"])


def load():
    cfg = load_config(ROOT / "configs/bidirectional.yaml")
    t1 = pd.read_csv(R1 / "trials.csv.gz", low_memory=False)
    t2 = pd.read_csv(R2 / "trials.csv.gz", low_memory=False)
    tk = pd.read_csv(RK / "trials.csv.gz", low_memory=False)
    pe2 = pd.read_csv(R2 / "pair_effects.csv")
    pe2 = pe2[pe2["split"] == "pilot"]
    pek = pd.read_csv(RK / "pair_effects.csv")
    kp = pd.read_csv(ROOT / "data/bidirectional/known_partner/frozen_dataset/pairs_frozen.csv")
    return cfg, t1, t2, tk, pe2, pek, kp


SHORT = {"wc2026": "World Cup\n2026", "olympics2026": "Winter Olympics\n2026", "wc2022": "World Cup\n2022",
         "facts": "Known\nfacts", "young": "Young et al.\nproducts", "kp": "Obscure vs\nfamous item"}


def finish(fig, title, top=0.88, bottom=0.0, right=1.0):
    """A left-aligned title over the whole figure, then a layout that keeps everything on the page."""
    fig.text(0.01, 0.985, title, ha="left", va="top", fontsize=9, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, bottom, right, top))
    return fig


def bar_labels(ax, bars, fmt="{:.0f}%"):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, fmt.format(b.get_height()),
                ha="center", va="bottom", fontsize=7.5, color=INK)


def fig_unsure(t1):
    c = t1[t1["condition"].isin(COMP)]
    s = c.groupby("dataset")["turn1_answer"].apply(lambda x: (x == "unsure").mean() * 100)
    ds = [d for d in ORDER if d in s.index]
    fig, ax = plt.subplots(figsize=(W, 2.3))
    bars = ax.bar([SHORT[d] for d in ds], [s[d] for d in ds],
                  color=[ORANGE if d in ("wc2026", "olympics2026") else GREY2 for d in ds], width=0.6)
    bar_labels(ax, bars)
    ax.set_ylim(0, 110)
    ax.set_ylabel("answered UNSURE (%)")
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    return finish(fig, "Run A: with UNSURE allowed, the model rarely chose a side on the 2026 events")


def fig_option_order(t2, tk):
    rows = []
    for t in (t2, tk):
        c = t[t["condition"].isin(COMP)].copy()
        c["ok"] = ok(c["turn1_correct"])
        c["first_higher"] = (c["role"] == "high") == (c["order"] == "target_first")
        rows.append(c[["dataset", "ok", "first_higher"]])
    c = pd.concat(rows)
    g = c.groupby(["dataset", "first_higher"])["ok"].mean().unstack() * 100
    ds = [d for d in ORDER if d in g.index]
    x = np.arange(len(ds))
    fig, ax = plt.subplots(figsize=(W, 3.1))
    b1 = ax.bar(x - 0.19, [g.loc[d, True] for d in ds], 0.36, color=GREY2,
                label="right answer = the first option (MORE, GREATER)")
    b2 = ax.bar(x + 0.19, [g.loc[d, False] for d in ds], 0.36, color=ORANGE,
                label="right answer = the second option (FEWER, SMALLER, LESS)")
    bar_labels(ax, b1); bar_labels(ax, b2)
    ax.axhline(50, color=INK2, lw=0.8, ls=(0, (3, 3)))
    ax.set_xticks(x, [SHORT[d] for d in ds], fontsize=7.5)
    ax.set_ylim(0, 112)
    ax.set_ylabel("turn-1 answers right (%)")
    ax.legend(loc="upper center", ncol=1, bbox_to_anchor=(0.5, 1.22), fontsize=7.5)
    return finish(fig, "Turn 1 is often a reflex: the model picks the first option it is offered", top=0.97)


def fig_numeric(pe2, pek):
    vals = {d: pe2.loc[pe2["dataset"] == d, "C4_share_of_gap"].dropna() for d in ORDER[:4]}
    vals["kp_obscure"] = pek.loc[pek["kp_side"] == "obscure", "C4_share_of_gap"].dropna()
    vals["kp_famous"] = pek.loc[pek["kp_side"] == "famous", "C4_share_of_gap"].dropna()
    labels = {**SHORT, "kp_obscure": "Obscure\nitems", "kp_famous": "Famous\nitems"}
    keys = list(vals)
    med = [vals[k].median() * 100 for k in keys]
    fig, ax = plt.subplots(figsize=(W, 2.5))
    bars = ax.bar([labels[k] for k in keys], med, width=0.6,
                  color=[ORANGE if k == "wc2026" else GREY2 for k in keys])
    bar_labels(ax, bars)
    ax.set_ylim(0, max(med) * 1.25)
    ax.set_ylabel("share of the way to the number (%)")
    ax.tick_params(axis="x", labelsize=7.5)
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    return finish(fig, "A plain number pulls hardest where the answer is unknown (median over pairs)")


def controls_table(cfg, pek):
    by = pd.read_csv(R2 / "by_dataset.csv")
    ob = pek[pek["kp_side"] == "obscure"].copy()
    ob["dataset"] = "kp"
    by = pd.concat([by[by["dataset"] != "kp"], summarise(ob, cfg, ["dataset"])])
    return by[by["contrast"].isin(["comparison_vs_B", "comparison_vs_B2", "comparison_vs_C1"])]


def fig_controls(cfg, pek):
    by = controls_table(cfg, pek)
    ctrl = {"comparison_vs_B": ("vs plain baseline (B)", GREY, "o"),
            "comparison_vs_B2": ("vs two-turn baseline (B2)", GREY, "D"),
            "comparison_vs_C1": ("vs co-mention (C1)", ORANGE, "s")}
    ds = [d for d in ORDER if d in set(by["dataset"])]
    fig, axes = plt.subplots(1, 2, figsize=(W, 3.6), sharey=True)
    for ax, role, title in ((axes[0], "low", "Low item (should move up)"),
                            (axes[1], "high", "High item (should move down)")):
        for j, (k, (lab, col, mk)) in enumerate(ctrl.items()):
            for i, d in enumerate(ds):
                r = by[(by["dataset"] == d) & (by["contrast"] == k)]
                if r.empty:
                    continue
                r = r.iloc[0]
                y = i + (j - 1) * 0.24
                ax.plot([r[f"{role}_ci_lo"], r[f"{role}_ci_hi"]], [y, y], color=col, lw=1.1)
                ax.plot(r[f"{role}_mean"], y, mk, color=col, ms=4.5, label=lab if i == 0 else None)
        ax.axvline(0, color=INK2, lw=0.8)
        ax.set_title(title, loc="left")
        ax.xaxis.grid(True); ax.set_axisbelow(True)
    axes[0].set_yticks(range(len(ds)), [NAMES[d] for d in ds])
    axes[0].invert_yaxis()
    fig.supxlabel("move towards the partner (log units; 0.1 = about 10%)", fontsize=8.5, color=INK2, y=0.1)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, bbox_to_anchor=(0.55, 0.0))
    return finish(fig, "The same comparison looks different against each control (Qwen3-32B, 95% intervals)",
                  top=0.94, bottom=0.12)


def fig_comention(cfg, pe2, pek):
    ob = pek[pek["kp_side"] == "obscure"].copy()
    ob["dataset"] = np.where(ob["domain"] == "mountains", "kp_m", "kp_b")
    d = pd.concat([pe2, ob])
    labels = {**NAMES, "kp_m": "Obscure mountains", "kp_b": "Obscure buildings"}
    ds = ["wc2026", "olympics2026", "wc2022", "facts", "young", "kp_m", "kp_b"]
    fig, ax = plt.subplots(figsize=(W, 3.0))
    for j, (role, col, mk, lab) in enumerate((("low", ORANGE, "o", "low item"), ("high", DARK, "s", "high item"))):
        for i, k in enumerate(ds):
            v = (d.loc[(d["dataset"] == k) & (d["role"] == role), "C1"] -
                 d.loc[(d["dataset"] == k) & (d["role"] == role), "B"]).values
            m, lo, hi = bootstrap_mean(v, cfg["analysis"]["bootstrap"], cfg["analysis"]["seed"])
            y = i + (j - 0.5) * 0.3
            ax.plot([lo, hi], [y, y], color=col, lw=1.1)
            ax.plot(m, y, mk, color=col, ms=4.5, label=lab if i == 0 else None)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(ds)), [labels[k] for k in ds])
    ax.invert_yaxis()
    ax.set_xlabel("change of the estimate when the other item is only named (log units; + = higher)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.legend(loc="lower right")
    return finish(fig, "Naming the other item, with no comparison, already moves the estimates")


def fig_mountains(pek, kp):
    names = {"Qutani": "K2", "Laram Salla": "K2", "Wamanripa": "Mount Everest"}
    lab = {**dict(zip(kp["low_entity_id"], kp["low_label"])), **dict(zip(kp["high_entity_id"], kp["high_label"]))}
    tru = {**dict(zip(kp["low_entity_id"], kp["truth_low"])), **dict(zip(kp["high_entity_id"], kp["truth_high"]))}
    ob = pek[pek["kp_side"] == "obscure"].copy()
    ob["label"] = ob["entity_id"].map(lab)
    fig, ax = plt.subplots(figsize=(W, 3.0))
    yt = []
    for i, (n, partner) in enumerate(names.items()):
        r = ob[ob["label"].str.startswith(n)].iloc[0]
        b, c1, comp = np.expm1(r["B"]), np.expm1(r["C1"]), np.expm1(r["comparison"])
        t = tru[r["entity_id"]]
        ax.plot([min(b, c1, comp), max(b, c1, comp)], [i, i], color=GREY2, lw=2, zorder=1)
        ax.plot(b, i, "o", color=GREY, ms=7, label="asked alone (B)" if i == 0 else None, zorder=3)
        ax.plot(c1, i, "s", color=ORANGE, ms=7, label=f"named next to the famous peak (C1)" if i == 0 else None, zorder=3)
        ax.plot(comp, i, "D", color=DARK, ms=6, label="after \"higher or lower than ...?\"" if i == 0 else None, zorder=3)
        ax.plot(t, i, "|", color=INK, ms=14, mew=1.6, label="true height" if i == 0 else None, zorder=2)
        for v, dy in ((b, 0.34), (c1, 0.34), (comp, -0.34)):
            ax.text(v, i + dy, f"{v:,.0f}", ha="center", va="center", fontsize=6.8, color=INK2)
        yt.append(f"{n}  (partner: {partner})")
    ax.set_yticks(range(len(yt)), yt)
    ax.set_ylim(len(yt) - 0.4, -0.6)
    ax.set_xlabel("estimated height above sea level (m; geometric mean of the answers)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.3), ncol=2, fontsize=7)
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    return finish(fig, "Naming K2 lifts a Bolivian peak; answering the comparison undoes it")


def fig_kp_items(pek):
    ob = pek[pek["kp_side"] == "obscure"]
    groups = [("mountains", "low"), ("mountains", "high"), ("buildings", "low"), ("buildings", "high")]
    lab = {"low": "lower than its partner", "high": "higher than its partner"}
    fig, ax = plt.subplots(figsize=(W, 2.6))
    rng = np.random.default_rng(1)
    for i, (dom, role) in enumerate(groups):
        v = ob.loc[(ob["domain"] == dom) & (ob["role"] == role), "assim_comparison_vs_B"].dropna().clip(-1, 1)
        ax.scatter(v, i + rng.uniform(-0.15, 0.15, len(v)), s=14, color=ORANGE if role == "low" else DARK,
                   alpha=0.8, edgecolor="none")
        ax.plot([v.median()] * 2, [i - 0.3, i + 0.3], color=INK, lw=1.6)
        ax.text(1.02, i, f"median {v.median():+.2f}, {np.mean(v > 0):.0%} towards", va="center",
                fontsize=7, color=INK2, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(groups)), [f"{d.capitalize()}, {lab[r]}" for d, r in groups])
    ax.invert_yaxis()
    ax.set_xlim(-1.05, 1.05)
    ax.set_xlabel("move towards the famous partner, vs asked alone (log units)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    return finish(fig, "Every obscure item: no pull towards the famous partner", right=0.76)


def fig_fame(tk, kp):
    unk = dict(zip(kp["pair_id"], kp["unknown_entity_id"]))
    c = tk[tk["condition"].isin(COMP)].copy()
    c["ok"] = ok(c["turn1_correct"])
    is_unk = c["target_entity_id"] == c["pair_id"].map(unk)
    c["obscure"] = np.where(is_unk == (c["role"] == "low"), "lower", "higher")
    c["first"] = np.where(is_unk == (c["order"] == "target_first"), "obscure item named first",
                          "famous item named first")
    g = c.groupby(["obscure", "first"])["ok"].mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(W, 2.3))
    x = np.arange(2)
    cats = ["lower", "higher"]
    b1 = ax.bar(x - 0.19, [g.loc[k, "famous item named first"] for k in cats], 0.36, color=GREY2,
                label="\"Is <famous> greater or smaller than <obscure>?\"")
    b2 = ax.bar(x + 0.19, [g.loc[k, "obscure item named first"] for k in cats], 0.36, color=ORANGE,
                label="\"Is <obscure> greater or smaller than <famous>?\"")
    bar_labels(ax, b1); bar_labels(ax, b2)
    ax.axhline(50, color=INK2, lw=0.8, ls=(0, (3, 3)))
    ax.set_xticks(x, ["obscure item really lower", "obscure item really higher"])
    ax.set_ylim(0, 125)
    ax.set_ylabel("turn-1 answers right (%)")
    ax.legend(loc="upper right", fontsize=7)
    return finish(fig, "Named first, the famous item is almost always called the greater one")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None)
    a = ap.parse_args(argv)
    cfg, t1, t2, tk, pe2, pek, kp = load()
    figs = [fig_unsure(t1), fig_option_order(t2, tk), fig_numeric(pe2, pek), fig_controls(cfg, pek),
            fig_comention(cfg, pe2, pek), fig_mountains(pek, kp), fig_kp_items(pek), fig_fame(tk, kp)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT, metadata={"CreationDate": None, "ModDate": None}) as pdf:
        for f in figs:
            pdf.savefig(f)
    if a.preview:
        p = Path(a.preview); p.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(figs, 1):
            f.savefig(p / f"page{i}.png", dpi=110)
    print(f"{len(figs)} pages -> {OUT}")


if __name__ == "__main__":
    main()
