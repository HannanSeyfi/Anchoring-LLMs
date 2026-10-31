"""Figures for the experiment reports (latex/reports/).

Run from anywhere:  python latex/reports/figures.py [--preview]
Writes one PDF per figure to latex/reports/figures/ (the reports include them by name) and, with
--preview, PNG copies to latex/reports/preview/ (not committed). Experiments 1-5 also reuse the
figures of the longer reports (full_report_figures.pdf, study2_figures.pdf, events_2026_figures.pdf).

Colours as in the other reports: orange = Qwen3-32B, blue = R1-Distill-Qwen-1.5B, lighter = less
thinking; green = the model's own starting value, purple = a given one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.parsing import parse_estimate  # noqa: E402
from anchoring_llms.run import read_records  # noqa: E402

OUT = ROOT / "latex" / "reports" / "figures"
BIG, SMALL = "qwen3-32b", "r1-distill-qwen-1.5b"
NAME = {BIG: "Qwen3-32B", SMALL: "R1-Distill-Qwen-1.5B"}
ORANGE, BLUE, AQUA, YELLOW = "#eb6834", "#2a78d6", "#1baf7a", "#eda100"
GREEN, PURPLE = "#1baf7a", "#7b5cd6"
GREY = "#898781"
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
SHADES = {BIG: {"off": "#f6b899", "low": "#eb6834", "high": "#a83f14"},
          SMALL: {"off": "#9fc4f0", "low": "#2a78d6", "high": "#104281"}}
LEVELS = ["off", "low", "high"]
LEVEL_NAME = {"off": "thinking off", "low": "short thinking (512)", "high": "long thinking (2,048)"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 8.5, "axes.titleweight": "bold",
    "axes.labelsize": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 7.5,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "lines.linewidth": 1.6, "lines.solid_capstyle": "round", "pdf.fonttype": 42,
})
W = 6.3  # text width in inches
figs: list[tuple[str, plt.Figure]] = []


def add(name: str, fig: plt.Figure) -> None:
    figs.append((name, fig))


def load(dataset: str, model: str, study: str) -> pd.DataFrame:
    df = pd.DataFrame(read_records(ROOT / "data" / dataset / "raw" / model / study))
    if dataset == "pilot" and model == SMALL:
        df["estimate"] = [parse_estimate(a, fallback=False) for a in df.answer]  # see CHANGELOG.md
    return df


def strip(ax, y, values, color, rng, size=16, jitter=0.13, marker="o", zorder=3):
    v = np.asarray(values, dtype=float)
    ax.scatter(v, y + rng.uniform(-jitter, jitter, len(v)), s=size, color=color, edgecolor="white",
               linewidth=0.5, zorder=zorder, marker=marker)


def boot(values, n=2000, seed=0):
    v = np.asarray([x for x in values if np.isfinite(x)])
    rng = np.random.default_rng(seed)
    means = rng.choice(v, (n, len(v))).mean(axis=1)
    return v.mean(), np.quantile(means, 0.025), np.quantile(means, 0.975), len(v)


# ============================================================================ Experiment 6
S1 = {m: load("pilot_v2", m, "study1") for m in (BIG, SMALL)}
B1 = {m: load("pilot_v2", m, "baseline") for m in (BIG, SMALL)}
ANCH = {m: json.loads((ROOT / "data" / "pilot_v2" / "anchors" / f"{m}.json").read_text()) for m in (BIG, SMALL)}
INDEX = pd.read_csv(ROOT / "results" / "pilot_v2" / "tables" / "anchoring_index.csv")
ITEMS1 = pd.read_csv(ROOT / "data" / "items_v2" / "study1.csv").set_index("item_id")


def anchor_rows(m, item, level, anchors):
    s, b = S1[m], B1[m]
    rows = [("no anchor", b[(b.item_id == item) & (b.thinking_level == level)].estimate.dropna(), None)]
    for lab, a in anchors:
        d = s[(s.item_id == item) & (s.thinking_level == level) & (s.anchor == a)]
        rows.append((lab, d.estimate.dropna(), a))
    return rows


def fig_example_strips(m, item, anchors, levels, truth, unit, ticks, name, xlim):
    fig, axes = plt.subplots(1, len(levels), figsize=(W, 2.6), sharey=True, layout="constrained")
    rng = np.random.default_rng(3)
    for ax, lv in zip(np.atleast_1d(axes), levels):
        rows = anchor_rows(m, item, lv, anchors)
        ax.set_xscale("log")
        ax.axvline(truth, color=INK2, lw=0.8, zorder=1)
        ax.text(truth, 1.0, f" true {truth:,g}", fontsize=6.5, color=INK2, ha="left", va="top",
                transform=ax.get_xaxis_transform())
        for i, (lab, v, a) in enumerate(rows):
            y = len(rows) - 1 - i
            v = v[v > 0]
            strip(ax, y, v, GREY if a is None else SHADES[m][lv], rng)
            if len(v):
                ax.plot([np.median(v)] * 2, [y - 0.3, y + 0.3], color=INK, lw=2, zorder=4)
            if a:
                ax.plot([a], [y + 0.36], marker="v", ms=6, color=INK2, zorder=5)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r[0] for r in rows][::-1])
        ax.tick_params(axis="y", length=0)
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{t:,g}" for t in ticks])
        ax.minorticks_off()
        ax.set_xlim(*xlim)
        ax.grid(axis="x")
        ax.set_title(LEVEL_NAME[lv], loc="left")
        ax.set_ylim(-0.6, len(rows) - 0.1)
    fig.supxlabel(f"{unit} (log scale)   ▼ = the anchor   black bar = middle answer", fontsize=7.5, color=INK2)
    add(name, fig)


def fig_e6_index():
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.7), sharey=True)
    x = np.arange(3)
    for ax, dist in zip(axes, ["near", "far"]):
        ax.axhline(0.49, color=GREY, lw=1.1, ls="--", zorder=1)
        ax.text(2.25, 0.5, "people: 0.49", fontsize=6.8, color=INK2, ha="right", va="bottom")
        for m, off in [(BIG, -0.05), (SMALL, 0.05)]:
            d = INDEX[(INDEX.model == m) & (INDEX.distance == dist)]
            per = d.groupby(["thinking_level", "item_id"]).anchoring_index.mean()
            for i, lv in enumerate(LEVELS):
                mean, lo, hi, n = boot(per.loc[lv].values)
                fill = SHADES[m][lv] if not (m == SMALL and lv == "off") else "white"
                ax.errorbar(i + off, mean, yerr=[[mean - lo], [hi - mean]], color=SHADES[m]["low"], lw=1,
                            capsize=0, zorder=2)
                ax.scatter(i + off, mean, s=34, color=fill, edgecolor=SHADES[m]["low"], lw=1.2, zorder=3,
                           label=NAME[m] if i == 1 else None)
                ax.text(i + off + 0.07, mean, f"{mean:.2f}", fontsize=6.8, color=INK2, va="center")
            means = [boot(per.loc[lv].values)[0] for lv in LEVELS]
            ax.plot(x + off, means, color=SHADES[m]["low"], lw=1, alpha=0.5, zorder=1)
        ax.set_xticks(x)
        ax.set_xticklabels(["off", "short", "long"])
        ax.set_xlim(-0.4, 2.4)
        ax.set_ylim(-0.02, 1.05)
        ax.set_title(f"{dist} anchors", loc="left")
        ax.grid(axis="y")
    axes[0].set_ylabel("anchoring index")
    axes[0].legend(loc="upper left", fontsize=7)
    fig.supxlabel("thinking   (open circle: the small model with thinking off rests on 6-8 questions)",
                  fontsize=7.5, color=INK2)
    fig.tight_layout(w_pad=1)
    add("e6_index", fig)


SHORT1 = {"C1-030": "Lake Neusiedl depth", "C1-035": "Lake Bled area", "C1-036": "Lake Hallstatt area",
          "C1-045": "Alam-Kuh height", "C1-053": "Arlberg Road Tunnel", "C1-075": "Niesen stairway steps",
          "C1-080": "Krimml Waterfalls height", "C1-084": "Vettisfossen free fall",
          "C1-089": "Kuwait Towers height", "C1-091": "Azadi Tower height",
          "C1-102": "Versailles windows", "C1-107": "Andorra-Spain border",
          "C1-131": "distance (C1-131)", "C1-134": "Wellington-Santiago", "C1-137": "distance (C1-137)"}


def short_name(item):
    if item in ("C1-131", "C1-137"):
        q = ITEMS1.question[item]
        a = q.split("between the centres of ")[-1].rstrip("?").replace(" and ", "-")
        return a
    return SHORT1[item]


def fig_e6_items():
    fig, axes = plt.subplots(1, 2, figsize=(W, 3.6), sharey=True)
    order = (INDEX[INDEX.model == BIG].groupby("item_id").anchoring_index.mean().sort_values().index)
    for ax, m in zip(axes, [BIG, SMALL]):
        d = INDEX[INDEX.model == m].groupby(["item_id", "thinking_level"]).anchoring_index.mean().unstack()
        for y, it in enumerate(order):
            vals = [d.loc[it, lv] if lv in d.columns and it in d.index else np.nan for lv in LEVELS]
            fin = [v for v in vals if np.isfinite(v)]
            if fin:
                ax.plot([min(fin), max(fin)], [y, y], color=GRID, lw=2.5, zorder=1)
            for lv, v in zip(LEVELS, vals):
                if np.isfinite(v):
                    ax.scatter(v, y, s=24, color=SHADES[m][lv], edgecolor="white", lw=0.5, zorder=3,
                               label=LEVEL_NAME[lv] if y == 0 else None)
        ax.set_yticks(range(len(order)))
        ax.set_yticklabels([short_name(i) for i in order], fontsize=7)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(-0.1, 1.1)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.grid(axis="x")
        ax.set_title(NAME[m], loc="left")
    handles = [plt.Line2D([], [], ls="", marker="o", ms=5, color=c) for c in
               ["#d8d8d8", "#9a9a9a", "#3a3a3a"]]
    fig.legend(handles, ["thinking off", "short thinking", "long thinking"], ncol=3, loc="lower center",
               bbox_to_anchor=(0.5, 0.0), fontsize=7)
    fig.supxlabel("anchoring index per question (near and far anchors averaged)  ·  lighter dot = less thinking",
                  fontsize=7.5, color=INK2, y=0.06)
    fig.tight_layout(w_pad=1, rect=(0, 0.07, 1, 1))
    add("e6_items", fig)


def outcome_shares(m):
    s = S1[m].copy()
    res = []
    for _, r in s.iterrows():
        v, rg = r.estimate, ANCH[m][r.item_id]["range"]
        if v is None or not np.isfinite(v):
            res.append("none")
        elif abs(v - r.anchor) / abs(r.anchor) <= 0.01:
            res.append("copy")
        elif rg["lo"] <= v <= rg["hi"]:
            res.append("zone")
        else:
            res.append("else")
    s["out"] = res
    return s


def fig_e6_outcomes():
    cats = [("zone", "stayed in its usual range", BLUE), ("else", "moved outside its usual range", AQUA),
            ("copy", "gave the anchor back exactly", ORANGE), ("none", "no answer", YELLOW)]
    fig, ax = plt.subplots(figsize=(W, 2.9))
    rows = []
    for m in (BIG, SMALL):
        s = outcome_shares(m)
        for lv in LEVELS:
            share = s[s.thinking_level == lv].out.value_counts(normalize=True) * 100
            rows.append((f"{NAME[m]}, {['off', 'short', 'long'][LEVELS.index(lv)]}", share))
    for i, (lab, share) in enumerate(rows):
        y = len(rows) - 1 - i + (0.4 if i < 3 else 0)
        left = 0
        for key, clab, col in cats:
            v = share.get(key, 0)
            if v <= 0:
                continue
            ax.barh(y, v, left=left, height=0.7, color=col, edgecolor="white", lw=0.8, label=clab if i == 0 else None)
            if v >= 6:
                ax.text(left + v / 2, y, f"{v:.0f}%", ha="center", va="center", fontsize=6.8,
                        color=INK if col == YELLOW else "white")
            left += v
    ys = [len(rows) - 1 - i + (0.4 if i < 3 else 0) for i in range(len(rows))]
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of answers after an anchor (all 8 anchors; 1,200 or 1,180 answers per row)")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for k, l, c in cats], labels=[l for k, l, c in cats],
              ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=7, handlelength=1, columnspacing=1)
    fig.tight_layout()
    add("e6_outcomes", fig)


def fig_e6_cutoff():
    fig, ax = plt.subplots(figsize=(W * 0.62, 2.4))
    bars = []
    for m in (BIG, SMALL):
        s = S1[m]
        s = s[(s.thinking_level != "off") & s.estimate.notna()].copy()
        s["copied"] = (abs(s.estimate - s.anchor) / s.anchor.abs() <= 0.01)
        for lv in ["low", "high"]:
            for cut in [False, True]:
                d = s[(s.thinking_level == lv) & (s.thinking_truncated == cut)]
                bars.append((m, lv, cut, 100 * d.copied.mean(), len(d)))
    x = 0
    ticks, labels = [], []
    for m in (BIG, SMALL):
        for lv in ["low", "high"]:
            for cut in [False, True]:
                v = next(b for b in bars if b[:3] == (m, lv, cut))
                ax.bar(x, v[3], width=0.8, color=SHADES[m][lv], hatch="////" if cut else None,
                       edgecolor="white", lw=0.5)
                ax.text(x, v[3] + 0.8, f"{v[3]:.0f}%", ha="center", fontsize=6.5, color=INK2)
                x += 1
            ticks.append(x - 1.5)
            labels.append(f"{'short' if lv == 'low' else 'long'}")
            x += 0.4
        x += 0.6
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.text(1.7, -9, NAME[BIG], ha="center", fontsize=7.5, color=INK2)
    ax.text(6.7, -9, NAME[SMALL], ha="center", fontsize=7.5, color=INK2)
    ax.set_ylabel("answers that copy the anchor")
    ax.set_ylim(0, 40)
    ax.grid(axis="y")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor="#bbb"),
                       plt.Rectangle((0, 0), 1, 1, facecolor="#bbb", hatch="////", edgecolor="white")],
              labels=["thinking finished", "thinking stopped at the limit"], loc="upper left", fontsize=7)
    fig.tight_layout()
    add("e6_cutoff", fig)


def fig_e6_precision():
    t = pd.read_csv(ROOT / "results" / "pilot_v2" / "tables" / "precision.csv")
    fig, ax = plt.subplots(figsize=(W * 0.55, 2.2))
    ax.axhline(0, color=AXIS, lw=0.8)
    for m, off in [(BIG, -0.06), (SMALL, 0.06)]:
        per = t[t.model == m].groupby(["thinking_level", "item_id"]).precise_minus_round.mean()
        for i, lv in enumerate(LEVELS):
            if m == SMALL and lv == "off":
                continue  # too few answers with thinking off
            mean, lo, hi, n = boot(per.loc[lv].values)
            ax.errorbar(i + off, mean, yerr=[[mean - lo], [hi - mean]], color=SHADES[m]["low"], lw=1, capsize=0)
            ax.scatter(i + off, mean, s=30, color=SHADES[m][lv], edgecolor=SHADES[m]["low"], zorder=3,
                       label=NAME[m] if i == 1 else None)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["off", "short", "long"])
    ax.set_ylabel("precise minus round\n(shift towards the anchor)")
    ax.legend(fontsize=6.8, loc="upper left")
    ax.grid(axis="y")
    fig.tight_layout()
    add("e6_precision", fig)


# ============================================================================ Experiment 7
ITEMS2 = pd.read_csv(ROOT / "data" / "items_v2" / "study2.csv").set_index("item_id")
S2 = {m: load("pilot_v2", m, "study2") for m in (BIG, SMALL)}
SHORT2 = {"C2-006": "Itokawa", "C2-007": "Bennu", "C2-101": "887 Alinda", "C2-127": "3103 Eger",
          "C2-135": "3671 Dionysus", "C2-151": "1998 OR2", "C2-216": "Japan medals 2026",
          "C2-226": "Canada medals 2026", "C2-230": "Mario Galaxy film",
          "C2-234": "Now You See Me 3"}


def s2_values(m):
    d = S2[m].copy()
    unit = d.item_id.map(ITEMS2.unit)
    v = d.estimate.astype(float)
    d["v"] = np.where(unit.str.startswith("million") & (v >= 1e5), v / 1e6, v)  # "$400 million"
    ref, tr = d.item_id.map(ITEMS2.reference), d.item_id.map(ITEMS2.truth)
    d["atref"] = (abs(d.v - ref) / ref <= 0.02)
    with np.errstate(invalid="ignore", divide="ignore"):
        d["closer"] = np.abs(np.log(d.v / tr)) < np.abs(np.log(ref / tr))
    d["answered"] = d.v.notna() & (d.v > 0)
    return d


def fig_e7_shares():
    fig, axes = plt.subplots(1, 2, figsize=(W, 2.6), sharey=True)
    for ax, (key, title) in zip(axes, [("atref", "A: answer = the starting value"),
                                      ("closer", "B: closer to the truth than the start")]):
        x = 0
        ticks, labels = [], []
        for m in (SMALL, BIG):
            d = s2_values(m)
            d = d[d.answered & (d.thinking_level != "off")]
            for lv in ["low", "high"]:
                for src, col in [("self", GREEN), ("provided", PURPLE)]:
                    v = 100 * d[(d.thinking_level == lv) & (d.source == src)][key].mean()
                    ax.bar(x, v, width=0.8, color=col, alpha=1 if lv == "high" else 0.55, edgecolor="white")
                    ax.text(x, v + 1.2, f"{v:.0f}", ha="center", fontsize=6.3, color=INK2)
                    x += 1
                ticks.append(x - 1.5)
                labels.append("short" if lv == "low" else "long")
                x += 0.3
            x += 0.9
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7)
        ax.text(2.3, -0.16, "1.5B", transform=ax.get_xaxis_transform(), ha="center", fontsize=7.5, color=BLUE)
        ax.text(7.5, -0.16, "32B", transform=ax.get_xaxis_transform(), ha="center", fontsize=7.5, color=ORANGE)
        ax.set_title(title, loc="left")
        ax.set_ylim(0, 100)
        ax.grid(axis="y")
    axes[0].set_ylabel("% of answers")
    axes[0].legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GREEN), plt.Rectangle((0, 0), 1, 1, color=PURPLE)],
                   labels=["own start", "given start"], loc="upper left", fontsize=7)
    fig.tight_layout(w_pad=1)
    add("e7_shares", fig)


def fig_e7_items():
    order = list(SHORT2)
    fig, axes = plt.subplots(2, 5, figsize=(W, 4.1))
    rng = np.random.default_rng(5)
    d = s2_values(SMALL)
    big = s2_values(BIG)
    for ax, it in zip(axes.flat, order):
        ref, tr = ITEMS2.reference[it], ITEMS2.truth[it]
        ax.set_yscale("log")
        x = 0
        for lv in ["low", "high"]:
            for src, col, mk in [("self", GREEN, "o"), ("provided", PURPLE, "s")]:
                v = d[(d.item_id == it) & (d.thinking_level == lv) & (d.source == src) & d.answered].v
                ax.scatter(x + rng.uniform(-0.18, 0.18, len(v)), v, s=7, color=col, alpha=0.55 if lv == "low" else 0.9,
                           marker=mk, edgecolor="none", zorder=3)
                if len(v):
                    ax.plot([x - 0.3, x + 0.3], [np.median(v)] * 2, color=INK, lw=1.6, zorder=4)
                b = big[(big.item_id == it) & (big.thinking_level == lv) & (big.source == src) & big.answered].v
                if len(b):
                    ax.plot([x - 0.3, x + 0.3], [np.median(b)] * 2, color=ORANGE, lw=1.2, ls=(0, (2, 1)), zorder=4)
                x += 1
            x += 0.5
        ax.axhline(ref, color=INK2, lw=0.8, ls="--")
        ax.axhline(tr, color=INK2, lw=0.8, ls=":")
        lo = min(ref, tr) / 4
        hi = max(ref, tr) * 4
        ax.set_ylim(lo, hi)
        ax.set_xticks([0.5, 3.0])
        ax.set_xticklabels(["short", "long"], fontsize=6.5)
        ax.tick_params(axis="y", labelsize=6)
        ax.minorticks_off()
        ax.set_title(SHORT2[it], fontsize=6.6, loc="left")
    fig.text(0.5, 0.005, "dots: R1-Distill-1.5B answers (green circles own start, purple squares given); black bar: "
             "its middle answer;\norange dashed bar: Qwen3-32B's middle answer; dashed line: starting value; "
             "dotted line: truth. Answers outside the panel are cut.",
             ha="center", fontsize=6.6, color=INK2)
    fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=1.0, w_pad=0.6)
    add("e7_items", fig)


def fig_e7_answered():
    fig, ax = plt.subplots(figsize=(W * 0.55, 2.1))
    x = np.arange(3)
    for m, off in [(BIG, -0.18), (SMALL, 0.18)]:
        d = s2_values(m)
        vals = [100 * d[d.thinking_level == lv].answered.mean() for lv in LEVELS]
        ax.bar(x + off, vals, width=0.34, color=[SHADES[m][lv] for lv in LEVELS], label=NAME[m])
        for xi, v in zip(x + off, vals):
            ax.text(xi, v + 2, f"{v:.0f}%", ha="center", fontsize=6.5, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(["off", "short", "long"])
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 50, 100])
    ax.set_ylabel("replies with an answer")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=ORANGE), plt.Rectangle((0, 0), 1, 1, color=BLUE)],
              labels=[NAME[BIG], NAME[SMALL]], fontsize=6.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    fig.tight_layout()
    add("e7_answered", fig)


# ============================================================================ Overview
def fig_overview_index():
    # Near-anchor anchoring index (means over questions) from the analysis tables of each run;
    # run 1 with the strict reading (only replies with an "Estimate:" line).
    series = [("Run 1 (old questions): 1.5B", [0.576, 0.360, 0.437], BLUE, "--", "o"),
              ("Run 2 (old questions): 32B", [0.041, 0.004, 0.045], ORANGE, "--", "o"),
              ("Exp. 6 (new questions): 1.5B", [0.691, 0.831, 0.594], BLUE, "-", "s"),
              ("Exp. 6 (new questions): 32B", [0.352, 0.450, 0.406], ORANGE, "-", "s")]
    fig, ax = plt.subplots(figsize=(W * 0.72, 2.7))
    ax.axhline(0.49, color=GREY, lw=1.1, ls=":", zorder=1)
    ax.text(2.35, 0.5, "people: 0.49", fontsize=6.8, color=INK2, ha="right", va="bottom")
    for lab, vals, col, ls, mk in series:
        ax.plot(range(3), vals, color=col, ls=ls, marker=mk, ms=5, label=lab, mec="white", mew=0.7)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["off", "short", "long"])
    ax.set_xlabel("thinking")
    ax.set_ylabel("anchoring index (near anchors)")
    ax.set_ylim(-0.03, 1.0)
    ax.set_xlim(-0.2, 2.4)
    ax.grid(axis="y")
    ax.legend(fontsize=6.6, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    add("ov_index", fig)


def main():
    fig_example_strips(BIG, "C1-084", [("low, far: 6.7 m", 6.7), ("low, near: 23 m", 23),
                                        ("high, near: 280 m", 280), ("high, far: 970 m", 970)],
                       LEVELS, 275, "metres", [3, 10, 30, 100, 300, 1000], "e6_vettisfossen", (3, 1500))
    fig_example_strips(SMALL, "C1-134", [("low, far: 350 km", 350), ("low, near: 1,300 km", 1300),
                                          ("high, near: 18,000 km", 18000), ("high, far: 65,000 km", 65000)],
                       ["low", "high"], 9351, "kilometres", [100, 1000, 10000, 100000], "e6_wellington",
                       (60, 200000))
    fig_e6_index()
    fig_e6_items()
    fig_e6_outcomes()
    fig_e6_cutoff()
    fig_e6_precision()
    fig_e7_shares()
    fig_e7_items()
    fig_e7_answered()
    fig_overview_index()
    OUT.mkdir(exist_ok=True)
    for name, fig in figs:
        fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
        print("wrote", name)
    if "--preview" in sys.argv:
        prev = OUT.parent / "preview"
        prev.mkdir(exist_ok=True)
        for name, fig in figs:
            fig.savefig(prev / f"{name}.png", dpi=110)


if __name__ == "__main__":
    main()
