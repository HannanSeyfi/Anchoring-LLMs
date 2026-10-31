"""Figures for the Study 2 report on Qwen3-32B (latex/study2_qwen3/).

Run from anywhere:  python latex/study2_qwen3/figures.py [--preview]
Writes latex/study2_qwen3/study2_figures.pdf (one figure per page, in the order the report uses
them), prints the numbers the report quotes, and with --preview writes PNG previews to
latex/study2_qwen3/preview/ (not committed).

Data: data/pilot_v2/raw/qwen3-32b/study2/ (1,800 answers, run on DeepInfra 28-29 October 2026).
Adjustment = (median answer - starting value) / (true value - starting value):
0 = stayed at the starting value, 1 = reached the true value. Medians are over the 10 answers
of one question in one condition; summaries are medians over questions. Bennu (C2-007) is
left out of the summaries because the model knew it at every level (433 days, true 436.65), so
there was nothing left to adjust.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.run import read_records  # noqa: E402

OUT = ROOT / "latex" / "study2_qwen3"
DATA = ROOT / "data" / "pilot_v2" / "raw" / "qwen3-32b" / "study2"

# Own starting value = green circles, given starting value = purple squares.
OWN, GIVEN = "#159a6c", "#7a5af5"
INK, INK2, GRID, AXIS, GREY = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#898781"
SRC = {"self": ("own starting value", OWN, "o"), "provided": ("given starting value", GIVEN, "s")}
LEVELS = ["off", "low", "high"]
LEVEL_LABEL = {"off": "no thinking", "low": "short thinking\n(max 512)", "high": "long thinking\n(max 2,048)"}
INSTR = {"none": "no extra sentence", "accuracy": "“accuracy matters”",
         "opposite": "“consider why it\nmight be different”"}
SHORT = {"C2-006": "Itokawa", "C2-007": "Bennu", "C2-101": "Alinda", "C2-127": "Eger",
         "C2-135": "Dionysus", "C2-151": "1998 OR2", "C2-216": "Japan medals (Asian G.)",
         "C2-226": "Canada medals (Commonw. G.)", "C2-230": "Mario Galaxy box office",
         "C2-234": "Now You See Me 3 box office"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 8.5, "axes.titleweight": "bold",
    "axes.labelsize": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 8,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42,
})
W = 6.3  # text width in inches


def load() -> pd.DataFrame:
    df = pd.DataFrame(read_records(DATA)).drop_duplicates(["cell_id", "sample"], keep="last")
    return df


def cells(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby(["item_id", "source", "instruction", "thinking_level"])
           .agg(med=("estimate", "median"), R=("reference", "first"), T=("truth", "first"),
                tokens=("thinking_tokens", "mean"), answer_tokens=("answer_tokens", "mean"))
           .reset_index())
    # clip to [-0.5, 1.5] so that one wild median cannot dominate a summary
    m["adj"] = ((m.med - m.R) / (m["T"] - m.R)).clip(-0.5, 1.5)
    return m


def legend_src(ax, loc="upper left", **kw):
    handles = [Line2D([], [], color=c, marker=mk, lw=2, ms=6, label=lab) for lab, c, mk in SRC.values()]
    ax.legend(handles=handles, loc=loc, **kw)


def style(ax):
    ax.grid(axis="y")
    ax.set_axisbelow(True)


def fig_example(df, item, title, ylabel, ref_label, truth_label, ylim=None):
    """10 answers per thinking level, own vs given, no extra sentence."""
    d = df[(df.item_id == item) & (df.instruction == "none")]
    R, T = d.reference.iloc[0], d.truth.iloc[0]
    fig, ax = plt.subplots(figsize=(W, 3.0))
    rng = np.random.default_rng(1)
    for j, src in enumerate(["self", "provided"]):
        lab, c, mk = SRC[src]
        for i, lv in enumerate(LEVELS):
            y = d[(d.source == src) & (d.thinking_level == lv)].estimate.dropna().values
            x = i + (-0.17 if j == 0 else 0.17) + rng.uniform(-0.06, 0.06, len(y))
            ax.scatter(x, y, s=16, color=c, marker=mk, alpha=0.45, lw=0)
            med = np.median(y)
            xm = i + (-0.17 if j == 0 else 0.17)
            ax.plot([xm - 0.11, xm + 0.11], [med, med], color=c, lw=2.4)
            ax.annotate(f"{med:,.0f}", (xm, med), xytext=(0, 5), textcoords="offset points",
                        ha="center", fontsize=7.5, color=INK, fontweight="bold")
    ax.axhline(R, color=GREY, lw=1, ls="--")
    ax.axhline(T, color=INK, lw=1, ls=":")
    ax.text(2.55, R, ref_label, va="center", fontsize=7.5, color=INK2)
    ax.text(2.55, T, truth_label, va="center", fontsize=7.5, color=INK)
    ax.set_xticks(range(3), [LEVEL_LABEL[l] for l in LEVELS])
    ax.set_xlim(-0.5, 3.35)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    handles = [Line2D([], [], color=c, marker=mk, lw=0, ms=5, label=lab) for lab, c, mk in SRC.values()]
    handles.append(Line2D([], [], color=INK2, lw=2.4, label="middle answer (median)"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=3)
    style(ax)
    fig.tight_layout()
    return fig


def fig_main(m):
    """Median adjustment over questions vs thinking level, no extra sentence."""
    s = m[(m.instruction == "none") & (m.item_id != "C2-007")]
    fig, ax = plt.subplots(figsize=(W * 0.72, 3.0))
    for src, (lab, c, mk) in SRC.items():
        y = [s[(s.source == src) & (s.thinking_level == lv)].adj.median() for lv in LEVELS]
        ax.plot(range(3), y, color=c, marker=mk, lw=2, ms=7, label=lab)
        for i, v in enumerate(y):
            ax.annotate(f"{v + 0.0:.2f}".replace("-0.00", "0.00"), (i, v), xytext=(0, 7 if src == "self" else -13),
                        textcoords="offset points", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(range(3), [LEVEL_LABEL[l] for l in LEVELS])
    ax.set_ylim(-0.05, 1.05)
    ax.set_ylabel("how far the answer moved\n(0 = stayed at start, 1 = reached truth)")
    ax.set_title("Thinking moves answers away from the starting value", loc="left")
    legend_src(ax)
    style(ax)
    fig.tight_layout()
    return fig


def fig_items(m):
    """One small panel per question, no extra sentence."""
    s = m[m.instruction == "none"]
    items = list(SHORT)
    fig, axes = plt.subplots(2, 5, figsize=(W, 3.9), sharey=True)
    for ax, it in zip(axes.flat, items):
        for src, (lab, c, mk) in SRC.items():
            y = [s[(s.item_id == it) & (s.source == src) & (s.thinking_level == lv)].adj.iloc[0] for lv in LEVELS]
            ax.plot(range(3), y, color=c, marker=mk, lw=1.6, ms=4.5)
        ax.set_title(SHORT[it].replace(" (", "\n(").replace(" box", "\nbox"), fontsize=7, loc="left")
        ax.set_xticks(range(3), ["off", "short", "long"], fontsize=6.5)
        ax.axhline(0, color=GREY, lw=0.8, ls="--")
        ax.axhline(1, color=INK, lw=0.8, ls=":")
        ax.set_ylim(-0.55, 1.55)
        style(ax)
    for ax in axes[:, 0]:
        ax.set_ylabel("0 = start, 1 = truth", fontsize=7)
    handles = [Line2D([], [], color=c, marker=mk, lw=1.6, ms=5, label=lab) for lab, c, mk in SRC.values()]
    fig.legend(handles=handles, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return fig


def fig_instructions(m):
    """Three panels (one per extra sentence): own vs given across thinking levels."""
    s = m[m.item_id != "C2-007"]
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.8), sharey=True)
    for ax, ins in zip(axes, INSTR):
        for src, (lab, c, mk) in SRC.items():
            y = [s[(s.instruction == ins) & (s.source == src) & (s.thinking_level == lv)].adj.median()
                 for lv in LEVELS]
            ax.plot(range(3), y, color=c, marker=mk, lw=2, ms=6)
            for i, v in enumerate(y):
                ax.annotate(f"{v + 0.0:.2f}".replace("-0.00", "0.00"), (i, v), xytext=(0, 6 if src == "self" else -12),
                            textcoords="offset points", ha="center", fontsize=6.8, color=INK)
        ax.set_title(INSTR[ins], loc="left")
        ax.set_xticks(range(3), ["no\nthinking", "short", "long"])
        ax.set_ylim(-0.05, 1.0)
        style(ax)
    axes[0].set_ylabel("how far the answer moved\n(0 = start, 1 = truth)")
    handles = [Line2D([], [], color=c, marker=mk, lw=2, ms=6, label=lab) for lab, c, mk in SRC.values()]
    fig.legend(handles=handles, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    return fig


def fig_sentence_off(m):
    """No thinking: effect of the extra sentence, and how long the visible answer got."""
    s = m[(m.thinking_level == "off") & (m.item_id != "C2-007")]
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.7))
    x = np.arange(3)
    for j, (src, (lab, c, mk)) in enumerate(SRC.items()):
        y = [s[(s.instruction == ins) & (s.source == src)].adj.median() for ins in INSTR]
        a.bar(x + (j - 0.5) * 0.36, y, 0.34, color=c, label=lab)
        for xi, v in zip(x + (j - 0.5) * 0.36, y):
            a.text(xi, v + 0.02, f"{v + 0.0:.2f}".replace("-0.00", "0.00"), ha="center", fontsize=7, color=INK)
        z = [s[(s.instruction == ins) & (s.source == src)].answer_tokens.mean() for ins in INSTR]
        b.bar(x + (j - 0.5) * 0.36, z, 0.34, color=c, label=lab)
        for xi, v in zip(x + (j - 0.5) * 0.36, z):
            b.text(xi, v + 6, f"{v:.0f}", ha="center", fontsize=7, color=INK)
    for ax in (a, b):
        ax.set_xticks(x, ["none", "accuracy\nmatters", "consider why\ndifferent"])
        style(ax)
    a.set_ylim(0, 0.85)
    a.set_ylabel("how far the answer moved\n(0 = start, 1 = truth)")
    a.set_title("A: how far answers moved", loc="left")
    b.set_ylabel("length of the visible answer (tokens)")
    b.set_title("B: how long the answer was", loc="left")
    a.legend(loc="upper left")
    fig.tight_layout()
    return fig


def fig_cutoff(df, m):
    """A: thinking length piles up at the limit. B: short thinking did not beat no thinking."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.8), gridspec_kw={"width_ratios": [1.3, 1]})
    bins = np.arange(0, 2101, 50)
    for lv, c, lab in [("low", "#f3a07a", "short thinking (max 512)"), ("high", "#eb6834", "long thinking (max 2,048)")]:
        a.hist(df[df.thinking_level == lv].thinking_tokens, bins=bins, color=c, label=lab, rwidth=0.9)
    for x in (512, 2048):
        a.axvline(x, color=INK, lw=0.8, ls=":")
    a.text(530, a.get_ylim()[1] * 0.55, "limit 512", fontsize=7, color=INK)
    a.text(2030, a.get_ylim()[1] * 0.5, "limit\n2,048", fontsize=7, color=INK, ha="right")
    a.set_xlabel("thinking length of one answer (tokens)")
    a.set_ylabel("number of answers")
    a.set_title("A: most thinking was stopped at the limit", loc="left")
    a.legend(loc="upper left", bbox_to_anchor=(0.3, 1.0))
    style(a)
    # B: asteroid questions (Bennu excluded), all conditions pooled, per instruction
    s = m[m.item_id.isin(["C2-006", "C2-101", "C2-127", "C2-135", "C2-151"])]
    for ins, ls, mk in [("none", "-", "o"), ("accuracy", "--", "^"), ("opposite", ":", "D")]:
        y = [s[(s.instruction == ins) & (s.thinking_level == lv)].adj.median() for lv in LEVELS]
        b.plot(range(3), y, color=INK2, ls=ls, marker=mk, lw=1.6, ms=5,
               label=INSTR[ins].replace("\n", " "))
    b.set_xticks(range(3), ["no\nthinking", "short", "long"])
    b.set_ylim(-0.05, 1.0)
    b.set_ylabel("how far the answer moved\n(0 = 365 days, 1 = truth)")
    b.set_title("B: asteroid questions", loc="left")
    b.legend(loc="upper right", fontsize=6.8)
    style(b)
    fig.tight_layout()
    return fig


def report_numbers(df, m):
    print("answers", len(df), "parsed", df.estimate.notna().mean().round(4))
    print(df.groupby("thinking_level").agg(tok=("thinking_tokens", "mean"), cut=("thinking_truncated", "mean"),
                                           ans=("answer_tokens", "median")).round(3))
    noB = m[m.item_id != "C2-007"]
    print(noB.pivot_table(index=["instruction", "source"], columns="thinking_level", values="adj",
                          aggfunc="median")[LEVELS].round(2))
    p = noB.pivot_table(index=["item_id", "instruction", "source"], columns="thinking_level", values="adj")
    for lv in ["low", "high"]:
        g = (p[lv] - p["off"]).unstack("source")
        d = (g["self"] - g["provided"]).unstack("instruction")
        print(lv, "gain own minus given, items where own gained more:", (d > 0).sum().to_dict(),
              "median", d.median().round(2).to_dict())
    o = noB[noB.thinking_level == "off"].pivot_table(index=["item_id", "source"], columns="instruction", values="adj")
    for k in ["accuracy", "opposite"]:
        e = (o[k] - o["none"]).unstack("source")
        d = e["self"] - e["provided"]
        print("no thinking, sentence", k, "own helped more in", (d > 0).sum(), "of", len(d),
              "| median gain own", e["self"].median().round(2), "given", e["provided"].median().round(2))
    h = df[df.thinking_level == "high"]
    print("high cut-off share by item", h.groupby("item_id").thinking_truncated.mean().round(2).to_dict())
    h = h.assign(err=np.abs(np.log(h.estimate / h.truth)))
    x = h.groupby(["item_id", "source", "instruction", "thinking_truncated"]).err.median().unstack().dropna()
    print("high, same condition: cut-off answers further from truth in", (x[True] > x[False]).sum(), "of", len(x),
          "| median log error cut", x[True].median().round(2), "finished", x[False].median().round(2))


def main(preview=False):
    df = load()
    m = cells(df)
    report_numbers(df, m)
    figs = [
        fig_example(df, "C2-230", "Worked example: The Super Mario Galaxy Movie (no extra sentence)",
                    "box office (million US$)", "previous film\n$1,361 m", "true value\n$1,013 m", (600, 2300)),
        fig_example(df, "C2-006", "Worked example: asteroid Itokawa (no extra sentence)",
                    "orbit (days)", "one Earth year\n365 days", "true value\n557 days", (300, 650)),
        fig_main(m),
        fig_items(m),
        fig_instructions(m),
        fig_sentence_off(m),
        fig_cutoff(df, m),
    ]
    with PdfPages(OUT / "study2_figures.pdf") as pdf:
        for f in figs:
            pdf.savefig(f, bbox_inches="tight")
    if preview:
        (OUT / "preview").mkdir(exist_ok=True)
        for i, f in enumerate(figs, 1):
            f.savefig(OUT / "preview" / f"fig{i}.png", dpi=130, bbox_inches="tight")


if __name__ == "__main__":
    main(preview="--preview" in sys.argv)
