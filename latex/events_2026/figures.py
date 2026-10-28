"""Figures for the short report on the 2026-event questions (latex/events_2026/).

Run from anywhere:  python latex/events_2026/figures.py [--preview]
Writes latex/events_2026/events_2026_figures.pdf (one figure per page, in the order the report
uses them), prints the numbers the report quotes, and with --preview writes PNG previews to
latex/events_2026/preview/ (not committed).

Two reading rules used only here (the stored data is not changed):
  * A reply counts as an answer only if it ends with the requested "Estimate: <number>" line.
    Without that line the old fallback took the last number in the reply, which for the small
    model's refusals was often the year 2026.
  * Box-office questions ask for "million US dollars". When a reply wrote the unit in words
    ("Estimate: $400 million"), the parser turned it into 400,000,000; here it is read as 400.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MaxNLocator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from anchoring_llms.parsing import has_estimate_line, parse_estimate, strip_think  # noqa: E402
from anchoring_llms.run import read_records  # noqa: E402

OUT = ROOT / "latex" / "events_2026"

# Same palette as the full report: orange = Qwen3-32B, blue = the 1.5B model,
# light shade = no thinking, dark shade = thinking.
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID, AXIS, GREY = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#898781"
COMBOS = [  # (key, label, colour)
    ("32B_off", "32B, no thinking", "#f3a07a"),
    ("32B_low", "32B, thinking", ORANGE),
    ("1.5B_off", "1.5B, no thinking", "#86b6ef"),
    ("1.5B_low", "1.5B, thinking", BLUE),
]
LABEL = {k: lab for k, lab, _ in COMBOS}
COLOR = {k: c for k, _, c in COMBOS}
MODELS = {"qwen3-32b": "32B", "r1-distill-qwen-1.5b": "1.5B"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 8, "axes.titleweight": "bold",
    "axes.labelsize": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.linewidth": 0.8,
    "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 7, "ytick.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False, "legend.fontsize": 8,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "pdf.fonttype": 42,
})
W = 6.3  # text width in inches

EVENTS = ["2026 World Cup", "2026 Winter Olympics", "2026 Asian Games", "2026 Commonwealth Games",
          "film box office"]
SHORT = {  # what each question asks, in a few words
    "C2-201": "Total goals", "C2-202": "Total attendance", "C2-203": "Average attendance per match",
    "C2-204": "Goals by the top scorer",
    "C2-205": "USA, all medals", "C2-206": "USA, gold medals", "C2-207": "Italy (host), all medals",
    "C2-208": "Italy (host), gold medals", "C2-209": "Germany, gold medals", "C2-210": "France, all medals",
    "C2-211": "Japan, all medals", "C2-212": "Canada, all medals", "C2-213": "Switzerland, all medals",
    "C2-214": "China, gold medals",
    "C2-215": "Japan (host), gold medals", "C2-216": "Japan (host), all medals", "C2-217": "China, gold medals",
    "C2-218": "South Korea, all medals", "C2-219": "India, all medals", "C2-220": "Iran, gold medals",
    "C2-221": "Chinese Taipei, gold medals",
    "C2-222": "Number of medal events", "C2-223": "Number of athletes", "C2-224": "England, all medals",
    "C2-225": "England, gold medals", "C2-226": "Canada, all medals", "C2-227": "India, all medals",
    "C2-228": "Avatar: Fire and Ash", "C2-229": "Zootopia 2", "C2-230": "The Super Mario Galaxy Movie",
    "C2-231": "Tron: Ares", "C2-232": "The Conjuring: Last Rites", "C2-233": "The Devil Wears Prada 2",
    "C2-234": "Now You See Me: Now You Don't", "C2-235": "Final Destination Bloodlines",
    "C2-236": "28 Years Later", "C2-237": "Downton Abbey: The Grand Finale",
    "C2-238": "How to Train Your Dragon (2025)", "C2-239": "Spider-Man: Brand New Day",
}
REFUSAL = re.compile(r"sorry|cannot|can't|can not|don't have|do not have|unable|not possible|"
                     r"no (?:access|data)|I don’t have", re.IGNORECASE)
ESTIMATE_LINE = re.compile(r"estimate\s*[:=]\s*(.+)", re.IGNORECASE)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    items = pd.read_csv(ROOT / "data" / "items_v2" / "candidates_study2_events.csv").set_index("item_id")
    rows = []
    for model in MODELS:
        rows += read_records(ROOT / "data" / "screen_v2" / "raw" / model / "study2")
    df = pd.DataFrame(rows)
    df = df[df.item_id.isin(items.index)].copy()
    df["key"] = df.model.map(MODELS) + "_" + df.thinking_level
    df["answer"] = df.answer.fillna("")
    df["has_line"] = df.answer.map(has_estimate_line)
    df["refused"] = ~df.has_line & df.answer.str.contains(REFUSAL)
    df["kind"] = np.where(df.has_line, "number", np.where(df.refused, "refused", "other"))

    def value(r) -> float:
        if not r.has_line:
            return np.nan
        v = parse_estimate(r.answer, fallback=False)
        line = ESTIMATE_LINE.findall(strip_think(r.answer).replace("**", ""))[-1]
        if items.at[r.item_id, "unit"] == "million US dollars" and v >= 1e5 \
                and re.search(r"million|billion", line, re.IGNORECASE):
            v /= 1e6  # "$400 million" in a question already asked in millions
        return v

    df["value"] = df.apply(value, axis=1)
    return df, items


def scores(df: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    med = df.groupby(["item_id", "key"]).value.median().unstack()
    R, T = items.reference, items.truth
    out = {}
    for key, *_ in COMBOS:
        m = med[key].reindex(items.index)
        has = m.notna()
        out[key] = {
            "answered": int(has.sum()),
            "right direction": int(((np.sign(m - R) == np.sign(T - R)) & has).sum()),
            "closer than the previous edition": int((((m - T).abs() < (R - T).abs()) & has).sum()),
            "within 25% of the true value": int((((m - T).abs() <= 0.25 * T) & has).sum()),
        }
    return pd.DataFrame(out)


def short_num(x: float, _pos=None) -> str:
    if x == 0:
        return "0"
    if abs(x) >= 1e6:
        return f"{x / 1e6:g}M"
    if abs(x) >= 1e4:
        return f"{x / 1e3:g}k"
    return f"{x:,.0f}" if abs(x) >= 1 else f"{x:g}"


def nice(x: float) -> str:
    if x >= 1000:
        return f"{x:,.0f}"
    return f"{x:g}"


figs: list[tuple[str, plt.Figure]] = []


# ----------------------------------------------------------------------------- F1: did it answer?
def fig_answered(df: pd.DataFrame):
    # One colour per kind of reply (the same in every row), and the meaning written on the bars.
    fig, ax = plt.subplots(figsize=(W, 2.0))
    kinds = [("number", "gave a number", "#1baf7a", INK),
             ("refused", "refused", "#6b6a65", "white"),
             ("other", "other text", "#d9d8d1", INK)]
    for i, (key, label, _) in enumerate(COMBOS):
        y = len(COMBOS) - 1 - i
        g = df[df.key == key]
        left = 0
        for kind, name, kcol, tcol in kinds:
            n = int((g.kind == kind).sum())
            if n:
                ax.barh(y, n, left=left, height=0.6, color=kcol, edgecolor="white", linewidth=1)
            if n >= 100:
                ax.text(left + n / 2, y, f"{n} {name}", ha="center", va="center", fontsize=7.5, color=tcol)
            elif n:  # too thin to hold its label: write it just to the right, on the next segment
                ax.text(left + n + 6, y, f"\u25c0 {n} {name}", ha="left", va="center", fontsize=7,
                        color="white")
            left += n
    ax.set_yticks(range(len(COMBOS)))
    ax.set_yticklabels([lab for _, lab, _ in COMBOS][::-1], color=INK)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 780)
    ax.set_xticks([0, 195, 390, 585, 780])
    ax.set_xlabel("replies (39 questions \u00d7 20 tries = 780 for each row)")
    ax.spines["left"].set_visible(False)
    fig.tight_layout()
    figs.append(("answered", fig))


# ----------------------------------------------------------------------------- F2: how good?
def fig_scores(sc: pd.DataFrame):
    measures = ["right direction", "closer than the previous edition", "within 25% of the true value"]
    titles = ["Right direction", "Closer than previous", "Within 25% of truth"]
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.1), sharey=True)
    for ax, meas, title in zip(axes, measures, titles):
        for i, (key, label, col) in enumerate(COMBOS):
            y = len(COMBOS) - 1 - i
            n = sc.at[meas, key]
            ax.barh(y, n, height=0.62, color=col)
            ax.text(n + 0.8, y, f"{n}", va="center", fontsize=7.5, color=INK)
        ax.set_xlim(0, 39)
        ax.set_xticks([0, 13, 26, 39])
        ax.grid(axis="x")
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=8)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(range(len(COMBOS)))
    axes[0].set_yticklabels([lab for _, lab, _ in COMBOS][::-1])
    axes[1].set_xlabel("questions out of 39 (using the middle of the 20 answers)")
    fig.tight_layout(w_pad=0.6)
    figs.append(("scores", fig))


# ----------------------------------------------------------------------------- F3-F7: every question
def panel(ax, item: str, df: pd.DataFrame, items: pd.DataFrame, rng, show_labels: bool):
    R, T = items.at[item, "reference"], items.at[item, "truth"]
    xmax = 2.2 * max(R, T)
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(COMBOS) - 0.4)
    ax.axvline(R, color=GREY, lw=1.2, ls=(0, (3, 2)), zorder=1)
    ax.axvline(T, color=INK, lw=1.4, zorder=1)
    for i, (key, label, col) in enumerate(COMBOS):
        y = len(COMBOS) - 1 - i
        g = df[(df.item_id == item) & (df.key == key)]
        v = g.value.dropna().to_numpy()
        if len(v) == 0:
            ax.text(xmax * 0.02, y, f"no number in {len(g)} replies", va="center", fontsize=6.3,
                    color=INK2, style="italic")
            continue
        inside = v[v <= xmax]
        ax.scatter(inside, y + rng.uniform(-0.2, 0.2, len(inside)), s=11, color=col, alpha=0.8,
                   edgecolor="white", linewidth=0.4, zorder=3)
        above = int((v > xmax).sum())
        m = float(np.median(v))
        if above:
            ax.plot([xmax], [y], marker=">", ms=4.5, color=col, clip_on=False, zorder=4)
            ax.text(xmax * 1.035, y, f"+{above}", va="center", fontsize=6.3, color=INK2, clip_on=False)
        # the middle answer; if it is beyond the right edge, its diamond sits on the edge
        ax.scatter([min(m, xmax)], [y], s=34, marker="D", color="white", edgecolor=INK, linewidth=1.0,
                   zorder=5, clip_on=False)
        if len(v) < len(g):
            ax.text(xmax * 0.93, y, f"only {len(v)} of {len(g)} gave a number", ha="right",
                    va="center", fontsize=5.8, color=INK2, style="italic")
    ax.set_yticks(range(len(COMBOS)))
    ax.set_yticklabels([lab for _, lab, _ in COMBOS][::-1] if show_labels else [])
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    ax.xaxis.set_major_formatter(FuncFormatter(short_num))
    ax.grid(axis="x", lw=0.4)
    ax.set_axisbelow(True)
    ax.set_title(f"{SHORT[item]}", loc="left", fontsize=7.6, pad=11)
    ax.text(0, 1.02, f"previous {nice(R)}  →  2026: {nice(T)}", transform=ax.transAxes,
            fontsize=6.6, color=INK2)


def legend(fig, y):
    handles = [Line2D([], [], color=GREY, lw=1.2, ls=(0, (3, 2))), Line2D([], [], color=INK, lw=1.4),
               Line2D([], [], marker="o", ls="", color="#9a9a94", ms=4),
               Line2D([], [], marker="D", ls="", mfc="white", mec=INK, ms=5),
               Line2D([], [], marker=">", ls="", color="#9a9a94", ms=5)]
    labels = ["previous edition", "true 2026 value", "one answer", "middle answer",
              "+n answers beyond the edge"]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, y), ncol=5, fontsize=7,
               handlelength=1.6, columnspacing=1.0)


def fig_event(event: str, df: pd.DataFrame, items: pd.DataFrame):
    ids = list(items.index[items.domain == event])
    rows = (len(ids) + 1) // 2
    height = 0.55 + 1.32 * rows
    fig, axes = plt.subplots(rows, 2, figsize=(W, height), squeeze=False)
    rng = np.random.default_rng(7)
    for k, ax in enumerate(axes.flat):
        if k >= len(ids):
            ax.axis("off")
            continue
        panel(ax, ids[k], df, items, rng, show_labels=(k % 2 == 0))
    fig.tight_layout(rect=(0, 0, 0.975, 1 - 0.3 / height), h_pad=1.0, w_pad=1.6)
    legend(fig, 1.0)
    figs.append((event, fig))


def main(preview: bool = False) -> None:
    df, items = load()
    sc = scores(df, items)
    print(df.groupby(["key", "kind"]).size().unstack(fill_value=0))
    print(sc)
    fig_answered(df)
    fig_scores(sc)
    for event in EVENTS:
        fig_event(event, df, items)
    with PdfPages(OUT / "events_2026_figures.pdf") as pdf:
        for _, fig in figs:
            pdf.savefig(fig)
    if preview:
        (OUT / "preview").mkdir(exist_ok=True)
        for i, (name, fig) in enumerate(figs, 1):
            fig.savefig(OUT / "preview" / f"{i:02d}_{name.replace(' ', '_')}.png", dpi=150)
    print(f"wrote {len(figs)} figures to {OUT / 'events_2026_figures.pdf'}")


if __name__ == "__main__":
    main(preview="--preview" in sys.argv)
