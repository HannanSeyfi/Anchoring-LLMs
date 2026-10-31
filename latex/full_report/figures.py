"""Figures for the full step-by-step report (latex/full_report/).

Run from anywhere:  python latex/full_report/figures.py [--preview]
Writes latex/full_report/full_report_figures.pdf (one figure per page, in the order the report
uses them) and, with --preview, PNG previews in latex/full_report/preview/ (not committed).
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.parsing import parse_estimate  # noqa: E402
from anchoring_llms.run import read_records  # noqa: E402

OUT = ROOT / "latex" / "full_report"

# Colours: the first four categorical slots of the reference palette (validated for colour
# blindness), a neutral grey for "no anchor", and a light-to-dark blue ramp for thinking levels.
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GREY = "#898781"
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
LEVEL_COL = {"off": "#86b6ef", "low": "#2a78d6", "high": "#104281"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9, "axes.titleweight": "bold",
    "axes.labelsize": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 8,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "lines.linewidth": 1.6, "lines.solid_capstyle": "round", "pdf.fonttype": 42,
})
W = 6.3  # text width in inches


def load(dataset: str, model: str, study: str) -> pd.DataFrame:
    df = pd.DataFrame(read_records(ROOT / "data" / dataset / "raw" / model / study))
    if dataset == "pilot" and model == "r1-distill-qwen-1.5b":
        # Run 1 was saved with the old reading (last number when there is no "Estimate:" line),
        # which with thinking off often gave the anchor or a refusal year. Corrected 2026-10-30.
        df["estimate"] = [parse_estimate(a, fallback=False) for a in df.answer]
    return df


def fmt_num(x: float) -> str:
    if x >= 1000:
        return f"{x:,.0f}"
    if x >= 10:
        return f"{x:.0f}"
    return f"{x:g}"


def log_ticks(ax, axis="x", vals=None):
    vals = vals or [0.01, 0.1, 1, 10, 100]
    labels = [("1/100" if v == 0.01 else "1/10" if v == 0.1 else f"{v:g}" if v < 1 else f"{v:g}") for v in vals]
    if axis == "x":
        ax.set_xticks(vals)
        ax.set_xticklabels(labels)
    else:
        ax.set_yticks(vals)
        ax.set_yticklabels(labels)


def strip(ax, y, values, color, rng, size=18, jitter=0.12, zorder=3, marker="o"):
    v = np.asarray(values, dtype=float)
    ax.scatter(v, y + rng.uniform(-jitter, jitter, len(v)), s=size, color=color, edgecolor="white",
               linewidth=0.6, zorder=zorder, marker=marker)


figs: list[tuple[str, plt.Figure]] = []


def add(name: str, fig: plt.Figure):
    figs.append((name, fig))


# ----------------------------------------------------------------------------- F1: two mechanisms
def fig_mechanisms():
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.3))
    rng = np.random.default_rng(3)
    base = rng.normal(0, 0.55, 26)
    for ax, title in zip(axes, ["A. Adjusting", "B. Retrieving"]):
        ax.set_xlim(-1.9, 7.2)
        ax.set_ylim(-0.2, 2.6)
        ax.spines["left"].set_visible(False)
        ax.set_xticks([])
        ax.set_title(title, loc="left")
        ax.axvspan(-1.0, 1.0, ymin=0.0, ymax=1, color="#eef3fb", zorder=0)
        ax.text(0, 2.42, "values the model\nfinds plausible", ha="center", va="top", fontsize=7, color=INK2)
        ax.axvline(0, color=INK2, lw=0.8, zorder=1)
        ax.text(0, -0.15, "own answer", ha="center", va="top", fontsize=7, color=INK2)
        ax.plot([6.3], [0.15], marker="v", ms=9, color=ORANGE, zorder=4)
        ax.text(6.3, -0.15, "anchor", ha="center", va="top", fontsize=7, color=INK2)
        strip(ax, 1.55, base, GREY, rng, size=14, jitter=0.1)
        ax.set_yticks([0.75, 1.55])
        ax.set_yticklabels(["after anchor", "no anchor"], fontsize=7)
        ax.tick_params(axis="y", length=0)
    # A: start at the anchor, step down, stop at the edge of the plausible range
    ax = axes[0]
    xs = [6.3, 5.0, 3.8, 2.7, 1.8, 1.15]
    for a, b in zip(xs[:-1], xs[1:]):
        ax.annotate("", xy=(b, 0.75), xytext=(a, 0.75),
                    arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.2, shrinkA=1, shrinkB=1))
    strip(ax, 0.75, rng.normal(1.25, 0.18, 10), BLUE, rng, size=14, jitter=0.08)
    ax.text(3.7, 1.0, "small steps away\nfrom the anchor", ha="center", fontsize=7, color=INK2)
    # B: some answers are the model's own memory, some jump to an anchor-like value
    ax = axes[1]
    strip(ax, 0.75, np.r_[rng.normal(0.1, 0.5, 6), rng.normal(5.9, 0.35, 5)], BLUE, rng, size=14, jitter=0.08)
    ax.text(3.5, 1.0, "each answer is either\nits own memory or\none that fits the anchor", ha="center",
            fontsize=7, color=INK2)
    fig.tight_layout(w_pad=2)
    add("mechanisms", fig)


# ----------------------------------------------------------------------------- F2: anchor placement
def fig_anchor_design():
    fig, ax = plt.subplots(figsize=(W, 1.9))
    ax.set_xscale("log")
    ax.set_xlim(8, 2.2e5)
    ax.set_ylim(-0.6, 1.6)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    lo, hi = 310, 5555
    ax.axvspan(lo, hi, color="#eef3fb", zorder=0)
    ax.text(np.sqrt(lo * hi), 1.45, "normal zone: 310 to 5,555 m\n(the model's own answers, no anchor)",
            ha="center", va="top", fontsize=7.5, color=INK2)
    ax.axvline(979, color=INK2, lw=0.8)
    ax.text(979, -0.45, "true: 979 m", ha="center", fontsize=7.5, color=INK2)
    anchors = [(17, "far low\n17 m", BLUE), (150, "near low\n150 m", AQUA),
               (11000, "near high\n11,000 m", AQUA), (99000, "far high\n99,000 m", BLUE)]
    for a, lab, col in anchors:
        ax.plot([a], [0.35], marker="v", ms=10, color=col)
        ax.text(a, -0.05, lab, ha="center", va="top", fontsize=7.5, color=INK)
    ax.set_xticks([10, 100, 1000, 10000, 100000])
    ax.set_xticklabels(["10 m", "100 m", "1,000 m", "10,000 m", "100,000 m"])
    fig.tight_layout()
    add("anchor_design", fig)


# ----------------------------------------------------------------------------- F3: Angel Falls, run 1
def fig_angel():
    b = load("pilot", "r1-distill-qwen-1.5b", "baseline")
    s = load("pilot", "r1-distill-qwen-1.5b", "study1")
    b = b[(b.item_id == "S1-06") & (b.thinking_level == "low")]
    s = s[(s.item_id == "S1-06") & (s.thinking_level == "low") & (s.precision == "round")]
    rows = [("no anchor", b, None, GREY),
            ("high, near: 11,000 m", s[(s.direction == "high") & (s.distance == "near")], 11000, AQUA),
            ("high, far: 99,000 m", s[(s.direction == "high") & (s.distance == "far")], 99000, BLUE),
            ("low, near: 150 m", s[(s.direction == "low") & (s.distance == "near")], 150, AQUA),
            ("low, far: 17 m", s[(s.direction == "low") & (s.distance == "far")], 17, BLUE)]
    fig, ax = plt.subplots(figsize=(W, 2.6))
    rng = np.random.default_rng(1)
    ax.set_xscale("log")
    ax.axvspan(310, 5555, color="#eef3fb", zorder=0)
    ax.axvline(979, color=INK2, lw=0.8, zorder=1)
    for i, (lab, d, a, col) in enumerate(rows):
        y = len(rows) - 1 - i
        v = d.estimate.dropna()
        v = v[v > 0]
        strip(ax, y, v, col, rng, size=20)
        if a:
            ax.plot([a], [y + 0.38], marker="v", ms=7, color=ORANGE, zorder=4)
        ax.text(1.05, y, f"{len(v)} answers", transform=ax.get_yaxis_transform(), va="center", fontsize=7,
                color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(8, 3e5)
    ax.set_ylim(-0.6, len(rows) - 0.3)
    ax.set_xticks([10, 100, 1000, 10000, 100000])
    ax.set_xticklabels(["10 m", "100 m", "1,000 m", "10,000 m", "100,000 m"])
    ax.text(979, len(rows) - 0.35, "true 979 m", ha="center", fontsize=7, color=INK2)
    ax.grid(axis="x")
    fig.tight_layout()
    add("angel_falls_run1", fig)


# ----------------------------------------------------------------------------- F4: anchoring index
def fig_index():
    fig, ax = plt.subplots(figsize=(W * 0.66, 2.8))
    x = np.arange(3)
    # Run 1 counts only replies with an "Estimate:" line (corrected 2026-10-30; was 0.816 at off).
    r1 = (np.array([0.576, 0.360, 0.437]), np.array([0.210, 0.179, 0.214]), np.array([0.185, 0.193, 0.204]))
    r2 = (np.array([0.041, 0.004, 0.045]), np.array([0.047, 0.004, 0.045]), np.array([0.080, 0.007, 0.063]))
    ax.axhline(0.49, color=GREY, lw=1.2, label="people (Jacowitz & Kahneman, 1995): 0.49")
    for (m, lo, hi), col, lab, off in [(r1, BLUE, "run 1: R1-Distill-Qwen-1.5B", -0.04),
                                       (r2, ORANGE, "run 2: Qwen3-32B", 0.04)]:
        ax.errorbar(x + off, m, yerr=[lo, hi], color=col, marker="o", ms=5, capsize=0, lw=1.6,
                    elinewidth=1, label=lab, mec="white", mew=0.8)
        for xi, mi in zip(x + off, m):
            ax.text(xi + 0.08, mi + 0.035, f"{mi:.2f}", fontsize=7, color=INK2, va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels(["off", "low", "high"])
    ax.set_xlabel("thinking level")
    ax.set_ylabel("anchoring index (near anchors)")
    ax.set_ylim(-0.05, 1.32)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlim(-0.3, 2.4)
    ax.grid(axis="y")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.98))
    fig.tight_layout()
    add("anchoring_index", fig)


# ----------------------------------------------------------------------------- F5: what single answers did, run 1
def fig_run1_outcomes():
    # Only replies with an "Estimate:" line count (corrected 2026-10-30).
    rows = [("off, near", 7, 8, 4, 81), ("off, far", 10, 4, 4, 82), ("low, near", 54, 28, 17, 1),
            ("low, far", 54, 18, 26, 2), ("high, near", 51, 31, 16, 2), ("high, far", 55, 15, 28, 1)]
    cats = [("stayed in own normal zone", BLUE), ("copied the anchor", ORANGE),
            ("landed elsewhere", AQUA), ("no Estimate line", YELLOW)]
    fig, ax = plt.subplots(figsize=(W, 2.4))
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        left = 0
        for j, (lab, col) in enumerate(cats):
            v = r[1 + j]
            if v == 0:
                continue
            ax.barh(y, v - 0.6, left=left + 0.3, height=0.62, color=col, label=lab if i == 0 else None)
            if v >= 8:
                ax.text(left + v / 2, y, f"{v}%", ha="center", va="center", fontsize=7,
                        color="#0b0b0b" if col == YELLOW else "white")
            left += v
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of answers (200 per row): thinking level, anchor distance (anchors above the zone)")
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=7.3, handlelength=1, columnspacing=1)
    fig.tight_layout()
    add("run1_outcomes", fig)


# ----------------------------------------------------------------------------- F6: trace reading, run 1
def fig_trace_reading():
    rows = [("recalled its own value and kept it", 23), ("\"remembered\" the anchor itself and kept it", 8),
            ("own value, then pushed towards the anchor", 4), ("other (unit slips, borrowed digits)", 4),
            ("started at the anchor and adjusted away", 1)]
    fig, ax = plt.subplots(figsize=(W, 1.9))
    y = np.arange(len(rows))[::-1]
    ax.barh(y, [r[1] for r in rows], height=0.55, color=BLUE)
    for yi, (lab, v) in zip(y, rows):
        ax.text(v + 0.4, yi, str(v), va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 26)
    ax.set_xlabel("number of traces (40 read)")
    fig.tight_layout()
    add("trace_reading", fig)


# ----------------------------------------------------------------------------- F7: thinking tokens
def fig_tokens():
    dq = pd.read_csv(ROOT / "results/pilot/tables/data_quality.csv")
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.4), sharey=True)
    for ax, study, title in zip(axes, ["study1", "study2"], ["Study 1 questions", "Study 2 questions"]):
        for model, col, lab, off in [("r1-distill-qwen-1.5b", BLUE, "run 1 (1.5B)", -0.17),
                                     ("qwen3-32b", ORANGE, "run 2 (32B)", 0.17)]:
            d = dq[(dq.study == study) & (dq.model == model)].set_index("thinking_level")
            v = [d.loc[lv, "mean_thinking_tokens"] for lv in ["low", "high"]]
            ax.bar(np.arange(2) + off, v, width=0.32, color=col, label=lab)
            for xi, vi in zip(np.arange(2) + off, v):
                ax.text(xi, vi - 40, f"{vi:.0f}", ha="center", va="top", fontsize=7, color="white")
        for xi, lim in zip([0, 1], [512, 2048]):
            ax.plot([xi - 0.4, xi + 0.4], [lim, lim], color=INK2, lw=1)
            ax.text(xi, lim + 40, f"budget {lim}", ha="center", fontsize=7, color=INK2)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["low", "high"])
        ax.set_title(title, loc="left")
        ax.grid(axis="y")
        ax.set_ylim(0, 2300)
    axes[0].set_ylabel("thinking tokens per answer (mean)")
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    add("thinking_tokens", fig)


# ----------------------------------------------------------------------------- F8: how sure: three panels
SHORT1 = {"S1-01": "Panama Canal length", "S1-02": "Suez Canal length", "S1-03": "London Underground stations",
          "S1-04": "Malta land area", "S1-05": "hummingbird species", "S1-06": "Angel Falls height",
          "S1-07": "Lake Baikal depth", "S1-08": "Eiffel Tower steps", "S1-09": "Mt Kosciuszko height",
          "S1-10": "Lhasa elevation", "S1-11": "Lake Titicaca area", "S1-12": "Trans-Siberian length",
          "S1-13": "Lake Superior volume", "S1-14": "Liechtenstein population",
          "S1-15": "lakes in Finland"}
SHORTV2 = {"C1-102": "Versailles windows", "C1-035": "Lake Bled area", "C1-036": "Lake Hallstatt area",
           "C1-134": "Wellington-Santiago", "C1-084": "Vettisfossen free fall", "C1-030": "Lake Neusiedl depth",
           "C1-107": "Andorra-Spain border", "C1-137": "Kathmandu-Nairobi", "C1-089": "Kuwait Towers",
           "C1-080": "Krimml Waterfalls", "C1-053": "Arlberg Road Tunnel", "C1-075": "Niesen stairway steps",
           "C1-131": "Anchorage-Honolulu", "C1-045": "Alam-Kuh height", "C1-091": "Azadi Tower height"}


def ranges(df, order, truth_col="truth"):
    out = []
    for item in order:
        g = df[df.item_id == item].estimate.dropna()
        g = g[g > 0]
        t = df[df.item_id == item][truth_col].iloc[0]
        out.append((item, np.quantile(g, 0.1) / t, np.median(g) / t, np.quantile(g, 0.9) / t))
    return out


def _range_panel(ax, rr, color, offset=0.0, lw=2.2, dot=INK):
    for i, (item, lo, med, hi) in enumerate(rr):
        y = len(rr) - 1 - i + offset
        ax.plot([max(lo, 1.1e-4), min(hi, 900)], [y, y], color=color, lw=lw, solid_capstyle="round")
        ax.plot([max(med, 1.1e-4)], [y], marker="o", ms=4.2, color=dot, mec="white", mew=0.6, zorder=3)


def fig_sureness():
    """First question set: how unsure each model was without an anchor."""
    b1 = load("pilot", "r1-distill-qwen-1.5b", "baseline")
    b2 = load("pilot", "qwen3-32b", "baseline")
    order = list(SHORT1)
    fig, axes = plt.subplots(1, 2, figsize=(W, 3.3), sharey=True)
    for ax, (title, rr) in zip(axes, [("Run 1: R1-Distill-Qwen-1.5B", ranges(b1, order)),
                                      ("Run 2: Qwen3-32B", ranges(b2, order))]):
        ax.set_xscale("log")
        ax.set_xlim(1e-4, 1e3)
        ax.axvline(1, color=INK2, lw=0.8, zorder=1)
        _range_panel(ax, rr, BLUE)
        ax.set_yticks(range(len(rr)))
        ax.set_yticklabels([SHORT1[r[0]] for r in rr][::-1], fontsize=7.5)
        ax.tick_params(axis="y", length=0)
        ax.set_xticks([1e-3, 1e-2, 1e-1, 1, 10, 100])
        ax.set_xticklabels(["÷1000", "÷100", "÷10", "true", "×10", "×100"], fontsize=6.5)
        ax.minorticks_off()
        ax.grid(axis="x")
        ax.set_title(title, loc="left", fontsize=8)
        ax.set_ylim(-0.6, len(rr) - 0.4)
    fig.supxlabel("answer divided by the true value (bar: middle 80% of the answers without an anchor, up to 60; dot: median)",
                  fontsize=7.5, color=INK2)
    fig.tight_layout(w_pad=1.0)
    add("sureness_first_set", fig)


def fig_sureness_v2():
    """Question set v2: the 15 picked Study 1 questions, Qwen3-32B, thinking off and low."""
    sc = load("screen_v2", "qwen3-32b", "study1")
    picked = pd.read_csv(ROOT / "results/screen_v2/tables/study1_questions.csv")
    picked = picked[picked.status == "picked"].sort_values("rank").item_id.tolist()
    fig, ax = plt.subplots(figsize=(W, 3.3))
    ax.set_xscale("log")
    ax.set_xlim(0.08, 12)
    ax.axvline(1, color=INK2, lw=0.8, zorder=1)
    for lv, off, col in [("off", 0.17, LEVEL_COL["off"]), ("low", -0.17, LEVEL_COL["low"])]:
        rr = ranges(sc[sc.thinking_level == lv], picked)
        _range_panel(ax, rr, col, offset=off, lw=2.4)
        ax.plot([], [], color=col, lw=2.4, label=f"thinking {lv}")
    ax.set_yticks(range(len(picked)))
    ax.set_yticklabels([SHORTV2[i] for i in picked][::-1], fontsize=7.5)
    ax.tick_params(axis="y", length=0)
    ax.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax.set_xticklabels(["1/10", "1/5", "1/2", "true", "2x", "5x", "10x"], fontsize=7)
    ax.minorticks_off()
    ax.grid(axis="x")
    ax.set_ylim(-0.6, len(picked) - 0.4)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    ax.set_xlabel("answer divided by the true value (bar: middle 80% of 20 answers; dot: median)")
    fig.tight_layout()
    add("sureness_v2", fig)


# ----------------------------------------------------------------------------- F9: Liechtenstein
def fig_liech():
    fig, ax = plt.subplots(figsize=(W * 0.62, 2.4))
    data = {"after a low anchor": [7.5, 5], "no anchor": [20, 30], "after a high anchor": [32.5, 50]}
    cols = [BLUE, GREY, ORANGE]
    x = np.arange(2)
    for k, ((lab, v), col) in enumerate(zip(data.items(), cols)):
        xs = x + (k - 1) * 0.24
        ax.bar(xs, v, width=0.22, color=col, label=lab)
        for xi, vi in zip(xs, v):
            ax.text(xi, vi + 1, f"{vi:g}%", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(["low thinking", "high thinking"])
    ax.set_ylabel("answers near 390,000\n(true value: 39,600)")
    ax.set_ylim(0, 60)
    ax.grid(axis="y")
    ax.legend(loc="upper left", fontsize=7.3)
    fig.tight_layout()
    add("liechtenstein", fig)


# ----------------------------------------------------------------------------- F10: two memories
def fig_two_memories():
    b2 = load("pilot", "qwen3-32b", "baseline")
    sc = load("screen_v2", "qwen3-32b", "study1")
    li = b2[b2.item_id == "S1-14"]
    ve = sc[sc.item_id == "C1-102"]
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.3))
    rng = np.random.default_rng(2)
    for ax, d, truth, title, xt, xl, lv in [
        (axes[0], li, 39600, "Liechtenstein population (run 2)", [1e4, 3e4, 1e5, 3e5, 1e6],
         ["10,000", "30,000", "100,000", "300,000", "1 million"], ["off", "low", "high"]),
        (axes[1], ve, 2143, "Versailles windows (screening)", [500, 1000, 3000, 10000, 30000],
         ["500", "1,000", "3,000", "10,000", "30,000"], ["off", "low"])]:
        ax.set_xscale("log")
        for i, level in enumerate(lv):
            y = len(lv) - 1 - i
            v = d[d.thinking_level == level].estimate.dropna()
            strip(ax, y, v, LEVEL_COL[level], rng, size=18, jitter=0.15)
        ax.axvline(truth, color=INK2, lw=0.8)
        ax.text(truth, len(lv) - 0.45, f"  true {truth:,}", ha="left", fontsize=7, color=INK2)
        ax.set_yticks(range(len(lv)))
        ax.set_yticklabels([f"thinking {x}" for x in lv][::-1])
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_xticks(xt)
        ax.set_xticklabels(xl, fontsize=7)
        ax.set_xlim(xt[0] * 0.7, xt[-1] * 1.4)
        ax.set_ylim(-0.6, len(lv) - 0.3)
        ax.grid(axis="x")
        ax.set_title(title, loc="left", fontsize=8)
    fig.tight_layout(w_pad=1.5)
    add("two_memories", fig)


# ----------------------------------------------------------------------------- F11: screening Study 1 scatter
def fig_screen_s1():
    q = pd.read_csv(ROOT / "results/screen_v2/tables/study1_questions.csv")
    fig, ax = plt.subplots(figsize=(W, 2.8))
    rng = np.random.default_rng(4)
    ax.add_patch(plt.Rectangle((-0.02, 0.1), 0.52, 1.9, color="#eef3fb", zorder=0))
    ax.text(0.01, 1.42, "keep zone: known at most 50%\nand spread 0.1 to 2.0", fontsize=7, color=INK2, va="top")
    groups = [("left out", q[q.status != "picked"], GREY, 14), ("picked (15)", q[q.status == "picked"], ORANGE, 26)]
    for lab, g, col, s in groups:
        x = g.known_max + rng.uniform(-0.008, 0.008, len(g))
        ax.scatter(x, g.spread_mean.clip(upper=1.48), s=s, color=col, edgecolor="white", linewidth=0.6,
                   label=lab, zorder=3 if lab.startswith("picked") else 2)
    ve = q[q.item_id == "C1-102"].iloc[0]
    ax.annotate("Versailles windows", xy=(ve.known_max, ve.spread_mean), xytext=(0.18, 1.2), fontsize=7,
                color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    ax.set_xlabel("known: share of answers within 2% of the true value (highest over thinking levels)")
    ax.set_ylabel("spread (0 = same answer\nevery time; 1 = ten-fold)")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.04, 1.5)
    ax.grid(True)
    ax.legend(loc="upper right")
    fig.tight_layout()
    add("screen_study1", fig)


# ----------------------------------------------------------------------------- F12: why candidates were left out
def fig_reasons():
    s1 = [("answers too similar", 105), ("known", 94)]
    s2 = [("thinking does not bring the\nanswer closer to the truth", 134), ("already close to the true\nvalue without thinking", 76),
          ("known", 49), ("answers move away from\nthe true value", 19), ("answers go far past\nthe true value", 17)]
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.3), gridspec_kw={"width_ratios": [1, 1.25]})
    for ax, rows, title in [(axes[0], s1, "Study 1 (137 screened)"),
                            (axes[1], s2, "Study 2 (162 screened)")]:
        y = np.arange(len(rows))[::-1]
        ax.barh(y, [r[1] for r in rows], height=0.55, color=GREY)
        for yi, (_, v) in zip(y, rows):
            ax.text(v + 2, yi, str(v), va="center", fontsize=7.5, color=INK)
        ax.set_yticks(y)
        ax.set_yticklabels([r[0] for r in rows], fontsize=7)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(0, 165)
        ax.set_ylim(-0.6, 4.6)
        ax.set_title(title, loc="left", fontsize=8)
        ax.set_xlabel("questions (one can fail several rules)", fontsize=7.5)
    fig.tight_layout(w_pad=1.5)
    add("screen_reasons", fig)


# ----------------------------------------------------------------------------- F13: 2026 events direction
def fig_events():
    q = pd.read_csv(ROOT / "results/screen_v2/tables/study2_questions.csv")
    ev = pd.read_csv(ROOT / "data/items_v2/candidates_study2_events.csv")
    q = q[q.item_id.isin(ev.item_id)]
    fig, ax = plt.subplots(figsize=(W * 0.72, 3.4))
    t = q.truth / q.reference
    for lv, col, mk in [("off", LEVEL_COL["off"], "o"), ("low", LEVEL_COL["low"], "o")]:
        m = q[f"median_{lv}"] / q.reference
        ax.scatter(t, m, s=22, color=col, edgecolor="white", linewidth=0.6, label=f"thinking {lv}", zorder=3,
                   marker=mk)
    lim = (0.25, 4.5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.plot(lim, lim, color=INK2, lw=0.8)
    ax.axhline(1, color=AXIS, lw=0.8)
    ax.axvline(1, color=AXIS, lw=0.8)
    ax.fill_between([lim[0], 1], lim[0], 1, color="#eef3fb", zorder=0)
    ax.fill_between([1, lim[1]], 1, lim[1], color="#eef3fb", zorder=0)
    ax.text(0.27, 0.29, "right direction:\nboth went down", fontsize=7, color=INK2)
    ax.text(4.3, 3.3, "right direction:\nboth went up", fontsize=7, color=INK2, ha="right", va="top")
    ax.text(0.27, 4.2, "model said up,\nit went down", fontsize=7, color=INK2, va="top")
    ax.text(4.3, 0.27, "model said down,\nit went up", fontsize=7, color=INK2, ha="right")
    ticks = [0.25, 0.5, 1, 2, 4]
    labs = ["1/4", "1/2", "same", "2x", "4x"]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labs)
    ax.set_yticks(ticks)
    ax.set_yticklabels(labs)
    ax.minorticks_off()
    ax.set_xlabel("true 2026 value compared with the previous edition")
    ax.set_ylabel("model's median compared with\nthe previous edition")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    add("events_direction", fig)


# ----------------------------------------------------------------------------- F14: Bennu and World Cup
def fig_bennu_worldcup():
    sc = load("screen_v2", "qwen3-32b", "study2")
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.2))
    rng = np.random.default_rng(5)
    for ax, item, ref, truth, title, xlim, log in [
        (axes[0], "C2-007", 365, 436.65, "Bennu orbit (days)", (300, 480), False),
        (axes[1], "C2-201", 172, 308, "2026 World Cup goals", (90, 4000), True)]:
        d = sc[sc.item_id == item]
        if log:
            ax.set_xscale("log")
        for i, lv in enumerate(["off", "low"]):
            y = 1 - i
            strip(ax, y, d[d.thinking_level == lv].estimate.dropna(), LEVEL_COL[lv], rng, size=18, jitter=0.15)
        for v, lab, ha in [(ref, f"start R = {ref} ", "right"), (truth, f" true {truth:g}", "left")]:
            ax.axvline(v, color=INK2 if ha == "left" else ORANGE, lw=0.9)
            ax.text(v, 1.5, lab, ha=ha, fontsize=7, color=INK2)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["thinking low", "thinking off"])
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(*xlim)
        ax.set_ylim(-0.5, 1.75)
        ax.grid(axis="x")
        ax.set_title(title, loc="left", fontsize=8)
        if log:
            ax.set_xticks([100, 300, 1000, 3000])
            ax.set_xticklabels(["100", "300", "1,000", "3,000"])
            ax.minorticks_off()
    fig.tight_layout(w_pad=1.5)
    add("bennu_worldcup", fig)


# ----------------------------------------------------------------------------- F15: Study 2 screening scatter
def fig_screen_s2():
    q = pd.read_csv(ROOT / "results/screen_v2/tables/study2_questions.csv")
    neo = set(pd.read_csv(ROOT / "data/items_v2/candidates_study2_neo.csv").item_id)
    ev = set(pd.read_csv(ROOT / "data/items_v2/candidates_study2_events.csv").item_id)
    q["batch"] = np.where(q.item_id.isin(neo), "asteroids", np.where(q.item_id.isin(ev), "2026 events", "first batch"))
    fig, ax = plt.subplots(figsize=(W, 3.0))
    lo, hi = -1.0, 2.0
    ax.add_patch(plt.Rectangle((0, lo), 0.8, hi - lo, color="#eef3fb", zorder=0))
    ax.plot([lo, hi], [lo, hi], color=AXIS, lw=0.8)
    ax.text(0.02, 1.9, "keep zone: adjustment with\nthinking off from 0 to 0.8", fontsize=7, color=INK2, va="top")
    for b, col in [("first batch", BLUE), ("asteroids", AQUA), ("2026 events", YELLOW)]:
        g = q[q.batch == b]
        ax.scatter(g.adjustment_off.clip(lo, hi), g.adjustment_low.clip(lo, hi), s=16, color=col,
                   edgecolor="white", linewidth=0.5, label=f"{b} ({len(g)})", zorder=2)
    p = q[q.status == "picked"]
    ax.scatter(p.adjustment_off.clip(lo, hi), p.adjustment_low.clip(lo, hi), s=70, facecolor="none",
               edgecolor=ORANGE, linewidth=1.4, label="picked (10)", zorder=3)
    ax.set_xlim(lo - 0.05, hi + 0.05)
    ax.set_ylim(lo - 0.05, hi + 0.05)
    ax.axhline(1, color=INK2, lw=0.6)
    ax.text(lo + 0.02, 1.03, "reached the true value", fontsize=7, color=INK2, ha="left", va="bottom")
    ax.axhline(0, color=AXIS, lw=0.6)
    ax.set_xlabel("adjustment with thinking off (0 = stayed at the start value, 1 = reached the truth)")
    ax.set_ylabel("adjustment with\nthinking low")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.3)
    ax.grid(True)
    fig.tight_layout()
    add("screen_study2", fig)


# ----------------------------------------------------------------------------- F16: Study 2 picks dumbbell
SHORT2 = {"C2-007": "Bennu orbit", "C2-006": "Itokawa orbit", "C2-234": "Now You See Me 3 box office",
          "C2-135": "Dionysus orbit", "C2-226": "Canada medals, Commonwealth 2026", "C2-151": "1998 OR2 orbit",
          "C2-101": "Alinda orbit", "C2-216": "Japan medals, Asian Games 2026",
          "C2-230": "Super Mario Galaxy box office", "C2-127": "Eger orbit"}


def fig_s2_picks():
    q = pd.read_csv(ROOT / "results/screen_v2/tables/study2_questions.csv")
    p = q[q.status == "picked"].sort_values("rank")
    fig, ax = plt.subplots(figsize=(W, 2.9))
    for i, r in enumerate(p.itertuples()):
        y = len(p) - 1 - i
        ax.annotate("", xy=(r.adjustment_low, y), xytext=(r.adjustment_off, y),
                    arrowprops=dict(arrowstyle="-|>", color=GREY, lw=1.2, shrinkA=3, shrinkB=3))
        ax.plot([r.adjustment_off], [y], "o", ms=6, color=LEVEL_COL["off"], mec="white", mew=0.6)
        ax.plot([r.adjustment_low], [y], "o", ms=6, color=LEVEL_COL["low"], mec="white", mew=0.6)
        ax.text(1.04, y, f"R {fmt_num(r.reference)} → true {fmt_num(r.truth)}", va="center", fontsize=7,
                color=INK2)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.axvline(1, color=INK2, lw=0.8)
    ax.set_yticks(range(len(p)))
    ax.set_yticklabels([SHORT2[i] for i in p.item_id][::-1], fontsize=7.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-0.05, 1.45)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xticklabels(["0\nstart value", "0.25", "0.5", "0.75", "1\ntrue value"])
    ax.grid(axis="x")
    ax.plot([], [], "o", color=LEVEL_COL["off"], label="thinking off")
    ax.plot([], [], "o", color=LEVEL_COL["low"], label="thinking low")
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    fig.tight_layout()
    add("study2_picks", fig)


def main():
    for f in [fig_mechanisms, fig_anchor_design, fig_angel, fig_index, fig_run1_outcomes, fig_trace_reading,
              fig_tokens, fig_sureness, fig_sureness_v2, fig_liech, fig_two_memories, fig_screen_s1, fig_reasons, fig_events,
              fig_bennu_worldcup, fig_screen_s2, fig_s2_picks]:
        f()
    with PdfPages(OUT / "full_report_figures.pdf", metadata={"CreationDate": None, "ModDate": None}) as pdf:
        for i, (name, fig) in enumerate(figs, 1):
            pdf.savefig(fig)
            print(f"page {i}: {name}")
    if "--preview" in sys.argv:
        prev = OUT / "preview"
        prev.mkdir(exist_ok=True)
        for i, (name, fig) in enumerate(figs, 1):
            fig.savefig(prev / f"{i:02d}_{name}.png", dpi=110)


if __name__ == "__main__":
    main()
