"""Build entity pairs (and triplets) from candidate_entities.csv.

Rules (set in configs/bidirectional.yaml, chosen before any model saw a question):

* the two entities have the same metric, scope and unit, and different true values;
* the high value is between `ratio[0]` and `ratio[1]` times the low one, so the gap is real but
  not absurd;
* players are only compared with players in the same position;
* entities whose sums disagreed with FIFA's own totals are left out;
* each entity is used at most `max_uses` times per metric, so the pairs do not lean on a few teams;
* pairs are spread over two gap sizes and, for teams, over 0, 1 or 2 former world champions.

Which entity is "low" and which is "high" comes only from the true values, never from model
behaviour. `candidate_pairs.csv` has every pair that passes the rules; `verified_pairs.csv` has
the spread-out selection that is screened; `triplets.csv` has low/middle/high triples.

    python -m anchoring_llms.bidirectional.pairs --config configs/bidirectional.yaml
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
from pathlib import Path

import pandas as pd
import yaml

FACT_PAIRS = [("C1-051", "C1-042"), ("C1-043", "C1-044"), ("C1-041", "C1-046"), ("C1-040", "C1-047"),
              ("C1-023", "C1-026"), ("C1-021", "C1-027"), ("C1-086", "C1-088"), ("C1-090", "C1-085"),
              ("C1-083", "C1-082")]


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def team_groups() -> dict[tuple[str, str], str]:
    out = {}
    for year in (2026, 2022):
        f = Path(f"data/bidirectional/raw_sources/fifa_wc{year}/team_match_stats.csv")
        if f.exists():
            m = pd.read_csv(f)
            for code, grp in zip(m["team_code"], m["group"]):
                if isinstance(grp, str) and grp:
                    out[(f"wc{year}", code)] = grp
    return out


def _usable(e: pd.DataFrame) -> pd.DataFrame:
    bad = e["verification"].str.contains("differ", case=False, na=False)
    return e[~bad & e["value"].notna()]


def make_pair(lo: pd.Series, hi: pd.Series, groups: dict, ratio_split: float) -> dict:
    a, b = sorted([lo, hi], key=lambda r: r["entity_label"])
    ratio = hi["value"] / lo["value"] if lo["value"] > 0 else math.inf
    same_group = ""
    if lo["entity_type"] == "team":
        ga, gb = groups.get((lo["dataset"], lo["entity_code"])), groups.get((hi["dataset"], hi["entity_code"]))
        same_group = bool(ga and ga == gb)
    famous = [x for x in (lo["famous"], hi["famous"]) if str(x) in ("True", "False")]
    amb = []
    if lo["dataset"] == "young":
        amb.append("no true value: low/high from human pilot means")
    if lo["scope"] == "tournament":
        amb.append("totals depend on matches played")
    if lo["domain"] == "olympics":
        amb.append("secondary source (Wikipedia)")
    short = {"wc2026": "WC26", "wc2022": "WC22", "olympics2026": "OLY26", "facts": "FACT", "young": "YNG", "kp": "KP"}
    pid = f"{short[lo['dataset']]}-{lo['domain'][:4].upper()}-{lo['metric'][:6]}-{lo['scope'][:4]}-{lo['entity_code']}-{hi['entity_code']}"
    return dict(
        pair_id=pid, dataset=lo["dataset"], domain=lo["domain"], competition=lo["competition"],
        year=lo["year"], metric=lo["metric"], metric_label=lo["metric_label"],
        metric_definition=lo["metric_definition"], scope=lo["scope"], unit=lo["unit"],
        entity_type=lo["entity_type"], entity_a_id=a["entity_id"], entity_b_id=b["entity_id"],
        entity_a=a["entity_label"], entity_b=b["entity_label"], truth_a=a["value"], truth_b=b["value"],
        low_entity_id=lo["entity_id"], high_entity_id=hi["entity_id"], low_label=lo["entity_label"],
        high_label=hi["entity_label"], low_name=lo["entity_name"], high_name=hi["entity_name"],
        truth_low=lo["value"], truth_high=hi["value"], gap_abs=hi["value"] - lo["value"],
        gap_ratio=round(ratio, 4), log10_gap=round(math.log10(ratio), 4) if ratio != math.inf else None,
        ratio_bin="small" if ratio < ratio_split else "large",
        matches_played_low=lo["matches_played"], matches_played_high=hi["matches_played"],
        minutes_played_low=lo["minutes_played"], minutes_played_high=hi["minutes_played"],
        position=lo["position"], famous_low=lo["famous"], famous_high=hi["famous"],
        n_famous=sum(str(x) == "True" for x in famous) if famous else "",
        same_group=same_group, team_low=lo["team_code"], team_high=hi["team_code"],
        source_url_low=lo["source_url"], source_url_high=hi["source_url"],
        source_endpoint_low=lo["source_endpoint"], source_endpoint_high=hi["source_endpoint"],
        retrieved_utc=lo["retrieved_utc"], event_end_date=lo["event_end_date"],
        after_cutoff=lo["after_cutoff"],
        verification_status="reference only" if lo["dataset"] == "young" else "verified",
        verification_low=lo["verification"], verification_high=hi["verification"],
        quality_review="passed automatic rules; not yet reviewed by a person",
        ambiguities="; ".join(amb))


def candidate_pairs(entities: pd.DataFrame, rules: dict, groups: dict) -> pd.DataFrame:
    """Every pair that passes the rules, for each (dataset, domain) rule block."""
    e = _usable(entities)
    rows = []
    for key, rule in rules.items():
        dataset, domain = key.split(":")
        sub = e[(e["dataset"] == dataset) & (e["domain"] == domain)]
        if "metrics" in rule:
            sub = sub[sub["metric"].isin(rule["metrics"])]
        if "scopes" in rule:
            sub = sub[sub["scope"].isin(rule["scopes"])]
        lo_r, hi_r = rule["ratio"]
        split = rule.get("ratio_split", math.sqrt(lo_r * hi_r))
        for (_, _, _), grp in sub.groupby(["metric", "scope", "unit"]):
            recs = grp.to_dict("records")
            for x, y in itertools.combinations(recs, 2):
                if x["value"] == y["value"]:
                    continue
                if rule.get("same_position") and x["position"] != y["position"]:
                    continue
                lo, hi = (x, y) if x["value"] < y["value"] else (y, x)
                if lo["value"] <= 0 or not (lo_r <= hi["value"] / lo["value"] <= hi_r):
                    continue
                rows.append(make_pair(pd.Series(lo), pd.Series(hi), groups, split))
    return pd.DataFrame(rows)


def select_pairs(cands: pd.DataFrame, rules: dict, seed: int) -> pd.DataFrame:
    """A spread-out subset: round-robin over (gap size, famous count) cells, capped entity reuse."""
    out = []
    for key, rule in rules.items():
        dataset, domain = key.split(":")
        sub = cands[(cands["dataset"] == dataset) & (cands["domain"] == domain)]
        for (metric, scope), grp in sub.groupby(["metric", "scope"]):
            rnd = random.Random(f"{seed}|{key}|{metric}|{scope}")
            rows = grp.to_dict("records")
            rnd.shuffle(rows)
            cells: dict[tuple, list] = {}
            for r in rows:
                cells.setdefault((r["ratio_bin"], str(r["n_famous"])), []).append(r)
            order = sorted(cells)
            uses: dict[str, int] = {}
            picked = []
            target = rule["per_metric"]
            while len(picked) < target and any(cells[c] for c in order):
                for c in order:
                    while cells[c]:
                        r = cells[c].pop(0)
                        if uses.get(r["low_entity_id"], 0) < rule["max_uses"] and \
                                uses.get(r["high_entity_id"], 0) < rule["max_uses"]:
                            picked.append(r)
                            uses[r["low_entity_id"]] = uses.get(r["low_entity_id"], 0) + 1
                            uses[r["high_entity_id"]] = uses.get(r["high_entity_id"], 0) + 1
                            break
                    if len(picked) >= target:
                        break
            out.extend(picked)
    return pd.DataFrame(out)


def fixed_pairs(entities: pd.DataFrame, groups: dict) -> pd.DataFrame:
    """Hand-listed familiar-fact pairs and the 16 Young et al. product pairs (low x high)."""
    e = entities.set_index("entity_id")
    rows = []
    for a, b in FACT_PAIRS:
        x, y = e.loc[f"facts-{a}"].copy(), e.loc[f"facts-{b}"].copy()
        x["entity_id"], y["entity_id"] = f"facts-{a}", f"facts-{b}"
        lo, hi = (x, y) if x["value"] < y["value"] else (y, x)
        rows.append(make_pair(lo, hi, groups, 1.8))
    young = entities[entities["dataset"] == "young"]
    lows = young[young["notes"].str.startswith("low")]
    highs = young[young["notes"].str.startswith("high")]
    for _, lo in lows.iterrows():
        for _, hi in highs.iterrows():
            rows.append(make_pair(lo, hi, groups, 100))
    return pd.DataFrame(rows)


def triplets(entities: pd.DataFrame, rules: dict, seed: int) -> pd.DataFrame:
    """Low < middle < high triples: each step between ratio[0] and ratio[1]; entities not reused."""
    e = _usable(entities)
    rows = []
    for key, rule in rules.items():
        dataset, domain = key.split(":")
        sub = e[(e["dataset"] == dataset) & (e["domain"] == domain) & (e["metric"] == rule["metric"])
                & (e["scope"] == rule.get("scope", e["scope"]))]
        recs = sorted(sub.to_dict("records"), key=lambda r: r["value"])
        rnd = random.Random(f"{seed}|triplets|{key}")
        combos = [(a, b, c) for a, b, c in itertools.combinations(recs, 3)
                  if a["value"] > 0 and rule["ratio"][0] <= b["value"] / a["value"] <= rule["ratio"][1]
                  and rule["ratio"][0] <= c["value"] / b["value"] <= rule["ratio"][1]]
        rnd.shuffle(combos)
        used: set[str] = set()
        n = 0
        for lo, mid, hi in combos:
            ids = {lo["entity_id"], mid["entity_id"], hi["entity_id"]}
            if ids & used:
                continue
            used |= ids
            n += 1
            rows.append(dict(
                triplet_id=f"TRI-{dataset}-{rule['metric']}-{lo['entity_code']}-{mid['entity_code']}-{hi['entity_code']}",
                dataset=dataset, domain=domain, metric=rule["metric"], scope=lo["scope"], unit=lo["unit"],
                low_entity_id=lo["entity_id"], mid_entity_id=mid["entity_id"], high_entity_id=hi["entity_id"],
                low_label=lo["entity_label"], mid_label=mid["entity_label"], high_label=hi["entity_label"],
                truth_low=lo["value"], truth_mid=mid["value"], truth_high=hi["value"],
                ratio_mid_low=round(mid["value"] / lo["value"], 4), ratio_high_mid=round(hi["value"] / mid["value"], 4)))
            if n >= rule["n"]:
                break
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    paths = cfg["paths"]
    ents = pd.read_csv(paths["entities"])
    groups = team_groups()
    rules = cfg["pairs"]["rules"]
    cands = candidate_pairs(ents, rules, groups)
    fixed = fixed_pairs(ents, groups)
    sel = pd.concat([select_pairs(cands, rules, cfg["pairs"]["seed"]), fixed], ignore_index=True)
    allc = pd.concat([cands, fixed], ignore_index=True)
    for df in (allc, sel):
        assert df["pair_id"].is_unique, df["pair_id"][df["pair_id"].duplicated()].tolist()[:5]
    # The full list is long (mostly player pairs); keep the columns needed to audit the rules.
    slim = ["pair_id", "dataset", "domain", "metric", "scope", "position", "low_entity_id", "high_entity_id",
            "low_label", "high_label", "truth_low", "truth_high", "gap_ratio", "ratio_bin", "n_famous", "same_group"]
    allc[slim].to_csv(paths["candidate_pairs"], index=False)
    sel.to_csv(paths["verified_pairs"], index=False)
    tri = triplets(ents, cfg["triplets"]["rules"], cfg["pairs"]["seed"])
    tri.to_csv(paths["triplets"], index=False)
    print(f"{len(allc)} candidate pairs -> {paths['candidate_pairs']}")
    print(f"{len(sel)} selected pairs -> {paths['verified_pairs']}")
    print(sel.groupby(["dataset", "domain", "metric", "scope"]).size().to_string())
    print(f"{len(tri)} triplets -> {paths['triplets']}")


if __name__ == "__main__":
    main()
