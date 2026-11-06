"""Analysis of the bidirectional study.

Measure. For an answer x, z = log(1 + x) (counts can be 0). For each pair and each of its two
entities, a cell mean is the mean z over the repetitions of a condition. The *shift* of a
condition against a control is the difference of cell means; the *assimilation* is the shift
signed so that a move towards the other entity is positive (+shift for the low entity,
-shift for the high entity). The two directions are always reported separately.

Contrasts (comparison = mean of LT and LA for the low entity, HT and HA for the high one):

    comparison - C1   primary: comparing vs merely naming both
    comparison - B    the classic contrast (vs the plain baseline)
    comparison - B2   vs a two-turn baseline of the same length (C5)
    comparison - C3   explicit answer vs comparison shown but not answered (self-consistency)
    C3 - C1           a comparison cue without any commitment
    C1 - B            does naming the other entity alone move the answer (semantic priming)
    C2 - B2           an irrelevant comparison of the names

Uncertainty intervals: percentile bootstrap over pairs (`bootstrap` resamples). Pattern for
each contrast, from the two intervals: bidirectional (both > 0), low only, high only, contrast
(an interval below 0), equivalent to none (both inside +-SESOI), or no reliable effect. A
mixed model (pairs as groups, entities as a variance component) is fitted as a check.

    python -m anchoring_llms.bidirectional.analysis --model qwen3-32b
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .run import load_records
from .trials import load_config

CONTRASTS = [("comparison", "C1"), ("comparison", "B"), ("comparison", "B2"), ("comparison", "C3"),
             ("C3", "C1"), ("C1", "B"), ("C2", "B2")]
COMP = {"LT": "low", "LA": "low", "HT": "high", "HA": "high"}


# ----------------------------------------------------------------------------- trial table

def trial_table(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["valid"] = (df["parse_status"] == "ok") & df["estimate"].notna() & (df["estimate"].astype(float) >= 0)
    df["z"] = np.where(df["valid"], np.log1p(df["estimate"].where(df["valid"], 0).astype(float)), np.nan)
    if "contaminated" not in df:
        df["contaminated"] = False
    df["contaminated"] = df["contaminated"].fillna(False).astype(bool)
    return df


def baseline_tables(df: pd.DataFrame) -> pd.DataFrame:
    """Per entity: B and B2 means of z, sd of z in B, n."""
    b = df[df["condition"] == "B"].groupby("target_entity_id")["z"].agg(B="mean", sd_B="std", n_B="count")
    b2 = df[df["condition"] == "B2"].groupby("target_entity_id")["z"].agg(B2="mean", n_B2="count")
    return b.join(b2, how="outer")


def percentile_score(df: pd.DataFrame) -> pd.Series:
    """Young et al.'s measure: percentile of each answer among the same entity's B answers (0-100)."""
    base = {e: np.sort(g["estimate"].astype(float).values)
            for e, g in df[(df["condition"] == "B") & df["valid"]].groupby("target_entity_id")}
    def pct(row):
        arr = base.get(row["target_entity_id"])
        if arr is None or not row["valid"] or len(arr) == 0:
            return np.nan
        x = float(row["estimate"])
        return 100 * (np.searchsorted(arr, x, "left") + np.searchsorted(arr, x, "right")) / (2 * len(arr))
    return df.apply(pct, axis=1)


def pair_effects(df: pd.DataFrame, exclude_contaminated: bool = False) -> pd.DataFrame:
    """One row per pair and role (low / high entity) with every condition mean and contrast."""
    d = df[df["valid"]]
    if exclude_contaminated:
        d = d[~d["contaminated"]]
    base = baseline_tables(d)
    rows = []
    pair_trials = d[d["pair_id"].astype(str) != ""]
    for (pid, role), g in pair_trials[pair_trials["role"].isin(["low", "high"])].groupby(["pair_id", "role"]):
        eid = g["target_entity_id"].iloc[0]
        sign = 1 if role == "low" else -1
        m = {c: g.loc[g["condition"] == c, "z"].mean() for c in ("C1", "C2", "C3", "C4")}
        comp = g[g["condition"].isin(COMP)]
        m["comparison"] = comp["z"].mean()
        m["comparison_first"] = comp.loc[comp["order"] == "target_first", "z"].mean()
        m["comparison_second"] = comp.loc[comp["order"] == "target_second", "z"].mean()
        m["C1_first"] = g.loc[(g["condition"] == "C1") & (g["order"] == "target_first"), "z"].mean()
        m["C1_second"] = g.loc[(g["condition"] == "C1") & (g["order"] == "target_second"), "z"].mean()
        m["B"] = base.loc[eid, "B"] if eid in base.index else np.nan
        m["B2"] = base.loc[eid, "B2"] if eid in base.index else np.nan
        row = dict(pair_id=pid, role=role, entity_id=eid, dataset=g["dataset"].iloc[0], domain=g["domain"].iloc[0],
                   metric=g["metric"].iloc[0], scope=g["scope"].iloc[0], split=g["split"].iloc[0] if "split" in g else "",
                   n_comparison=len(comp), sd_B=base.loc[eid, "sd_B"] if eid in base.index else np.nan, **m)
        for a, b in CONTRASTS:
            row[f"shift_{a}_vs_{b}"] = m[a] - m[b]
            row[f"assim_{a}_vs_{b}"] = sign * (m[a] - m[b])
        row["assim_order_first_minus_second"] = sign * (m["comparison_first"] - m["comparison_second"])
        row["assim_C4_vs_B"] = sign * (m["C4"] - m["B"])
        # The same, signed by the model's own beliefs instead of the true values: "towards the
        # partner" = towards the side where the model's baseline (B) puts the partner. When the
        # model has the two entities in the wrong order, the true-value sign misreads the move.
        pid_ = g["partner_entity_id"].iloc[0]
        b_partner = base.loc[pid_, "B"] if pid_ in base.index else np.nan
        belief = np.sign(b_partner - m["B"]) if b_partner == b_partner and m["B"] == m["B"] else np.nan
        row["belief_partner_higher"] = belief
        row["assim_belief_comparison_vs_C1"] = belief * (m["comparison"] - m["C1"])
        row["assim_belief_C3_vs_C1"] = belief * (m["C3"] - m["C1"])
        # C4 measured from the model's own baseline: the move towards the number given, in log
        # units (pull) and as a share of the distance from the baseline to the number.
        c4 = g[g["condition"] == "C4"]
        if len(c4) and m["B"] == m["B"]:
            za = np.log1p(c4["anchor_value"].astype(float)).mean()
            row["anchor_z"] = za
            row["assim_C4_pull"] = np.sign(za - m["B"]) * (m["C4"] - m["B"])
            row["C4_share_of_gap"] = (m["C4"] - m["B"]) / (za - m["B"]) if za != m["B"] else np.nan
        if comp["turn1_correct"].notna().any() if "turn1_correct" in comp else False:
            row["turn1_correct_share"] = comp["turn1_correct"].dropna().astype(float).mean()
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- statistics

def bootstrap_mean(values: np.ndarray, n: int, seed: int) -> tuple[float, float, float]:
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return (np.nan, np.nan, np.nan)
    if len(v) == 1:
        return (float(v[0]), np.nan, np.nan)
    rng = np.random.default_rng(seed)
    boots = rng.choice(v, size=(n, len(v)), replace=True).mean(axis=1)
    return float(v.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def hedges_g(values: np.ndarray) -> float:
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) < 3 or v.std(ddof=1) == 0:
        return np.nan
    d = v.mean() / v.std(ddof=1)
    return float(d * (1 - 3 / (4 * (len(v) - 1) - 1)))


def classify(low: tuple, high: tuple, sesoi: float) -> str:
    (_, l_lo, l_hi), (_, h_lo, h_hi) = low, high
    l_lo, l_hi, h_lo, h_hi = (round(x, 10) if x == x else x for x in (l_lo, l_hi, h_lo, h_hi))  # float dust
    if any(math.isnan(x) for x in (l_lo, l_hi, h_lo, h_hi)):
        return "not enough data"
    if l_lo > 0 and h_lo > 0:
        return "bidirectional assimilation"
    if l_hi < 0 or h_hi < 0:
        return "contrast (moves away)" if (l_hi < 0 and h_hi < 0) else (
            "low entity moves away" if l_hi < 0 else "high entity moves away")
    if l_lo > 0:
        return "low entity only"
    if h_lo > 0:
        return "high entity only"
    if -sesoi < l_lo and l_hi < sesoi and -sesoi < h_lo and h_hi < sesoi:
        return "equivalent to no effect"
    return "no reliable effect"


def summarise(pe: pd.DataFrame, cfg: dict, by: list[str] | None = None) -> pd.DataFrame:
    a = cfg["analysis"]
    keys = [f"assim_{x}_vs_{y}" for x, y in CONTRASTS] + ["assim_order_first_minus_second", "assim_C4_vs_B",
                                                           "assim_belief_comparison_vs_C1", "assim_belief_C3_vs_C1",
                                                           "assim_C4_pull"]
    groups = [((), pe)] if not by else list(pe.groupby(by))
    rows = []
    for gkey, g in groups:
        gkey = gkey if isinstance(gkey, tuple) else (gkey,)
        for k in keys:
            if k not in g:
                continue
            res = {}
            for role in ("low", "high"):
                vals = g.loc[g["role"] == role, k].values
                res[role] = bootstrap_mean(vals, a["bootstrap"], a["seed"])
                res[role + "_g"] = hedges_g(vals)
                res[role + "_n"] = int(np.sum(~np.isnan(np.asarray(vals, float))))
            # Per pair, split the two directions into two parts:
            #   converge     = (low + high) / 2: how much the two estimates move towards each other
            #   common_shift = (low - high) / 2: how much both estimates rise together (< 0: both fall)
            # (with assimilation signed towards the partner, a rise of both looks like "low towards,
            # high away"; common_shift names it). common_shift is also Young et al.'s asymmetry
            # (low moves more than high), which a pure rise of both cannot be told apart from.
            w = g.pivot_table(index="pair_id", columns="role", values=k)
            both = {"low", "high"} <= set(w.columns)
            conv = bootstrap_mean(((w["low"] + w["high"]) / 2).values if both else np.array([]), a["bootstrap"], a["seed"])
            shift = bootstrap_mean(((w["low"] - w["high"]) / 2).values if both else np.array([]), a["bootstrap"], a["seed"])
            row = dict(zip(by or [], gkey))
            row.update(contrast=k.replace("assim_", ""),
                       low_mean=res["low"][0], low_ci_lo=res["low"][1], low_ci_hi=res["low"][2], low_g=res["low_g"],
                       low_pairs=res["low_n"], high_mean=res["high"][0], high_ci_lo=res["high"][1],
                       high_ci_hi=res["high"][2], high_g=res["high_g"], high_pairs=res["high_n"],
                       pattern=classify(res["low"], res["high"], a["sesoi"]),
                       converge=conv[0], converge_ci_lo=conv[1], converge_ci_hi=conv[2],
                       common_shift=shift[0], common_shift_ci_lo=shift[1], common_shift_ci_hi=shift[2])
            rows.append(row)
    return pd.DataFrame(rows)


def mixed_model(df: pd.DataFrame) -> pd.DataFrame:
    """Trial level: y = sign * (z - entity's B mean), comparison and controls vs C1, by role."""
    try:
        import statsmodels.formula.api as smf
    except ImportError:
        return pd.DataFrame([{"term": "statsmodels not installed", "coef": np.nan}])
    d = df[df["valid"] & df["condition"].isin(list(COMP) + ["C1", "C3", "C2"]) & df["role"].isin(["low", "high"])].copy()
    base = baseline_tables(df[df["valid"]])["B"]
    d["y"] = np.where(d["role"] == "low", 1, -1) * (d["z"] - d["target_entity_id"].map(base))
    d["cond"] = np.where(d["condition"].isin(list(COMP)), "comparison", d["condition"])
    d = d.dropna(subset=["y"])
    if d["pair_id"].nunique() < 3:
        return pd.DataFrame([{"term": "too few pairs for a mixed model", "coef": np.nan}])
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = smf.mixedlm("y ~ C(cond, Treatment('C1')) * C(role, Treatment('low'))", d, groups=d["pair_id"],
                            vc_formula={"entity": "0 + C(target_entity_id)"}).fit(reml=True, method="lbfgs")
        ci = m.conf_int()
        return pd.DataFrame({"term": m.params.index, "coef": m.params.values, "se": m.bse.values,
                             "ci_lo": ci[0].values, "ci_hi": ci[1].values, "p": m.pvalues.values,
                             "n_trials": len(d), "n_pairs": d["pair_id"].nunique(), "converged": m.converged})
    except Exception as e:  # report, do not hide
        return pd.DataFrame([{"term": f"mixed model failed: {type(e).__name__}: {e}"[:200], "coef": np.nan}])


def self_consistency(df: pd.DataFrame) -> pd.DataFrame:
    """Comparison trials split by whether the turn-1 answer was right, wrong, or unsure."""
    d = df[df["valid"] & df["condition"].isin(list(COMP))].copy()
    if d.empty or "turn1_answer" not in d:
        return pd.DataFrame()
    base = baseline_tables(df[df["valid"]])["B"]
    d["assim_vs_B"] = np.where(d["role"] == "low", 1, -1) * (d["z"] - d["target_entity_id"].map(base))
    d["turn1"] = np.where(d["turn1_answer"].isin(["more", "fewer"]),
                          np.where(d["turn1_correct"] == True, "correct order", "wrong order"),  # noqa: E712
                          d["turn1_answer"].fillna("no answer"))
    return d.groupby(["role", "turn1"]).agg(trials=("z", "size"), mean_assim_vs_B=("assim_vs_B", "mean"),
                                            contaminated=("contaminated", "mean")).reset_index()


def accuracy(df: pd.DataFrame, entities: pd.DataFrame) -> pd.DataFrame:
    truth = entities.set_index("entity_id")["value"].astype(float)
    ok_ds = entities.set_index("entity_id")["dataset"] != "young"
    d = df[df["valid"]].copy()
    d["truth"] = d["target_entity_id"].map(truth)
    d = d[d["target_entity_id"].map(ok_ds).fillna(False)]
    d["abs_log_error"] = (d["z"] - np.log1p(d["truth"])).abs()
    d["signed_log_error"] = d["z"] - np.log1p(d["truth"])
    d["rel_error"] = (d["estimate"].astype(float) - d["truth"]) / d["truth"]
    grp = d.groupby(["condition", "role"], dropna=False)
    return grp.agg(trials=("z", "size"), abs_log_error=("abs_log_error", "mean"),
                   signed_log_error=("signed_log_error", "mean"), median_rel_error=("rel_error", "median")).reset_index()


def uncertainty_moderation(pe: pd.DataFrame, stats: pd.DataFrame | None) -> pd.DataFrame:
    """Does assimilation grow with the baseline spread of the entity (a weak prior)?"""
    x = pe.copy()
    if stats is not None and len(stats):
        x = x.merge(stats[["entity_id", "uncertainty", "spread", "known"]], on="entity_id", how="left")
    rows = []
    for role, g in x.groupby("role"):
        g = g.dropna(subset=["sd_B", "assim_comparison_vs_C1"])
        if len(g) >= 4:
            r = np.corrcoef(g["sd_B"], g["assim_comparison_vs_C1"])[0, 1]
            slope = np.polyfit(g["sd_B"], g["assim_comparison_vs_C1"], 1)[0]
            rows.append(dict(role=role, pairs=len(g), r_sd_B_vs_assim=r, slope=slope))
        if "uncertainty" in g:
            for cat, h in g.groupby("uncertainty"):
                rows.append(dict(role=role, uncertainty=cat, pairs=len(h),
                                 mean_assim_comparison_vs_C1=h["assim_comparison_vs_C1"].mean()))
    return pd.DataFrame(rows)


def triplet_effects(df: pd.DataFrame) -> pd.DataFrame:
    """Middle entity: estimate after comparing with the high one minus after comparing with the low one."""
    d = df[df["valid"] & (df["condition"] == "TRI")]
    if d.empty:
        return pd.DataFrame()
    m = d.groupby(["pair_id", "role"])["z"].mean().unstack()
    m["mid_high_minus_low"] = m.get("mid_vs_high") - m.get("mid_vs_low")
    return m.reset_index()


def analyse(cfg: dict, model: str, level: str | None = None, records: list[dict] | None = None,
            out: Path | None = None, smoke: bool = False) -> dict:
    level = level or cfg["thinking_level"]
    runs = Path(cfg["paths"]["runs_dir"] + ("_smoke" if smoke else ""))
    if records is None:
        records = []
        for phase in ("core", "numeric", "triplets"):
            records += load_records(runs / phase / model / level)
    df = trial_table(records)
    if df.empty:
        raise SystemExit(f"No answers found for {model} under {runs}.")
    out = out or Path(cfg["paths"]["results_dir"] + ("_smoke" if smoke else "")) / model / level
    (out / "tables").mkdir(parents=True, exist_ok=True)
    ents = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    ents["value"] = pd.to_numeric(ents["value"], errors="coerce")
    df["percentile"] = percentile_score(df)
    simulated = bool(df.get("simulated", pd.Series([False])).fillna(False).astype(bool).any())
    pe = pair_effects(df)
    pe_clean = pair_effects(df, exclude_contaminated=True)
    stats_path = Path(cfg["paths"]["screening_dir"]) / cfg["screening"]["model"] / level / "entity_stats.csv"
    stats = pd.read_csv(stats_path) if stats_path.exists() else None
    primary = pe[pe["split"].isin(["pilot", "confirmatory", ""])] if "split" in pe else pe
    res = {
        "overall": summarise(primary, cfg),
        "by_dataset": summarise(primary, cfg, ["dataset"]),
        "by_domain_metric": summarise(primary, cfg, ["dataset", "domain", "metric"]),
        "robustness_tournament_totals": summarise(pe[pe["split"] == "robustness"], cfg) if "split" in pe else pd.DataFrame(),
        "without_contaminated": summarise(pe_clean[pe_clean["split"].isin(["pilot", "confirmatory", ""])], cfg),
        "mixed_model": mixed_model(df[df["split"].isin(["pilot", "confirmatory", ""]) | (df["pair_id"] == "")]),
        "self_consistency": self_consistency(df),
        "accuracy": accuracy(df, ents),
        "uncertainty": uncertainty_moderation(primary, stats),
        "triplets": triplet_effects(df),
        "exclusions": df.groupby(["condition", "parse_status"]).size().unstack(fill_value=0).reset_index(),
    }
    pe.to_csv(out / "tables" / "pair_effects.csv", index=False)
    df.drop(columns=[c for c in ("history_2",) if c in df]).to_csv(out / "tables" / "trials.csv.gz", index=False)
    for k, v in res.items():
        v.to_csv(out / "tables" / f"{k}.csv", index=False)
    meta = dict(model=model, level=level, trials=len(df), valid=int(df["valid"].sum()), pairs=int(pe["pair_id"].nunique()),
                simulated=simulated)
    (out / "analysis.json").write_text(json.dumps(meta, indent=2) + "\n")
    from .report import write_report
    write_report(out, df, pe, res, meta, cfg)
    print(f"Analysis of {len(df)} trials ({meta['valid']} with a number) -> {out}")
    print(res["overall"][["contrast", "low_mean", "low_ci_lo", "low_ci_hi", "high_mean", "high_ci_lo", "high_ci_hi",
                          "pattern"]].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return res


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--model", default="qwen3-32b")
    ap.add_argument("--level", default=None)
    ap.add_argument("--smoke", action="store_true", help="analyse runs_smoke/ (smoke or simulated runs)")
    a = ap.parse_args(argv)
    analyse(load_config(a.config), a.model, a.level, smoke=a.smoke)


if __name__ == "__main__":
    main()
