"""Read the screening answers (baselines only), describe each entity, and freeze the pairs.

For each entity: share of replies with a number, refusals, median, spread (log10 of q90/q10 of
the answers, +1 so zeros work), error of the median, and how often the answer is within
`known_tolerance` of the true value ("known"). Uncertainty categories are the tertiles of the
spread among post-cutoff entities (strong prior / moderate / high uncertainty).

A pair is eligible when both entities give a number often enough and refuse rarely enough; for
post-cutoff pairs, neither entity may be "known" more than `max_known_share` of the time.
Known-partner pairs (configs/bidirectional_kp.yaml): the famous item's baseline median must be
within `known_partner.max_median_error` of its true value (the model knows it), and the obscure
item may be "known" at most `max_known_share` of the time.
No anchoring trial is used here: the rules see only baseline answers.

Eligible pairs are split into the pilot (`pilot_targets` per block, spread over metrics) and a
held-out confirmatory set. The result is written to frozen_dataset/ with checksums and is never
overwritten unless --force is given.

    python -m anchoring_llms.bidirectional.screen --model qwen3-32b
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

from .run import load_records
from .trials import load_config


def entity_stats(records: list[dict], entities: pd.DataFrame, tol: float) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df = df[df["condition"] == "B"]
    truth = entities.set_index("entity_id")
    rows = []
    for eid, g in df.groupby("target_entity_id"):
        est = g.loc[g["parse_status"] == "ok", "estimate"].astype(float)
        t = float(truth.loc[eid, "value"]) if eid in truth.index else math.nan
        row = dict(entity_id=eid, answers=len(g), parsed=len(est) / len(g),
                   refusals=(g["parse_status"] == "refusal").mean(), cut_off=(g["parse_status"] == "cut_off").mean())
        if len(est):
            q10, q50, q90 = np.quantile(est, [0.1, 0.5, 0.9])
            z = np.log1p(est.clip(lower=0))
            row.update(median=q50, mean=est.mean(), sd=est.std(ddof=1) if len(est) > 1 else 0.0,
                       q10=q10, q90=q90, spread=math.log10((q90 + 1) / (q10 + 1)), sd_log1p=z.std(ddof=1)
                       if len(z) > 1 else 0.0, distinct=est.nunique())
            if t == t and t > 0 and truth.loc[eid, "dataset"] != "young":
                row.update(truth=t, median_rel_error=(q50 - t) / t, abs_log_error=abs(math.log10((q50 + 1) / (t + 1))),
                           known=((est - t).abs() / t <= tol).mean())
        rows.append(row)
    out = pd.DataFrame(rows)
    keep = ["entity_id", "dataset", "domain", "metric", "scope", "entity_label", "after_cutoff", "famous"]
    return entities[keep].merge(out, on="entity_id", how="right")


def add_categories(stats: pd.DataFrame) -> tuple[pd.DataFrame, tuple[float, float]]:
    post = stats[(stats["after_cutoff"].astype(str) == "True") & stats["spread"].notna()]
    cuts = tuple(np.quantile(post["spread"], [1 / 3, 2 / 3])) if len(post) >= 3 else (0.05, 0.15)
    def cat(r):
        if r.get("known", 0) == r.get("known", 0) and r.get("known", 0) >= 0.5:
            return "strong prior (known)"
        s = r["spread"]
        if s != s:
            return "no answers"
        return "strong prior" if s <= cuts[0] else ("moderate" if s <= cuts[1] else "high uncertainty")
    stats = stats.copy()
    stats["uncertainty"] = stats.apply(cat, axis=1)
    return stats, cuts


def eligibility(pairs: pd.DataFrame, stats: pd.DataFrame, sc: dict) -> pd.DataFrame:
    s = stats.set_index("entity_id")
    rows = []
    for p in pairs.to_dict("records"):
        reasons = []
        for side in ("low", "high"):
            eid = p[f"{side}_entity_id"]
            if eid not in s.index:
                reasons.append(f"{side}: not screened")
                continue
            r = s.loc[eid]
            if r["parsed"] < sc["min_parsed"]:
                reasons.append(f"{side}: number in {r['parsed']:.0%} of replies")
            if r["refusals"] > sc["max_refusal"]:
                reasons.append(f"{side}: refused {r['refusals']:.0%}")
            if str(p["after_cutoff"]) == "True" and r.get("known", 0) == r.get("known", 0) \
                    and r.get("known", 0) > sc["max_known_share"]:
                reasons.append(f"{side}: known in {r['known']:.0%} of replies")
            kp = sc.get("known_partner")
            if kp and p.get("known_entity_id"):
                err, known = r.get("median_rel_error"), r.get("known")
                if eid == p["known_entity_id"] and not (err == err and abs(err) <= kp["max_median_error"]):
                    reasons.append(f"{side} (famous): baseline median off by {err:+.0%}")
                if eid == p.get("unknown_entity_id") and known == known and known > sc["max_known_share"]:
                    reasons.append(f"{side} (obscure): known in {known:.0%} of replies")
            p[f"uncertainty_{side}"] = r.get("uncertainty")
            p[f"spread_{side}"] = r.get("spread")
            p[f"baseline_median_{side}"] = r.get("median")
        p["eligible"] = not reasons
        p["exclusion_reason"] = "; ".join(reasons)
        rows.append(p)
    return pd.DataFrame(rows)


def _block(p: dict) -> str:
    return f"{p['dataset']}:{p['domain']}:{p['scope']}"


def _matches(key: str, block: str) -> bool:
    return all(k in ("*", b) for k, b in zip(key.split(":"), block.split(":")))


def split_pairs(el: pd.DataFrame, sc: dict) -> pd.DataFrame:
    el = el.copy()
    el["split"] = np.where(el["eligible"], "confirmatory", "excluded")
    rnd_seed = sc["seed"]
    for groupname, targets in (("pilot", sc["pilot_targets"]), ("robustness", sc.get("robustness", {}))):
        for key, n in targets.items():
            cand = el[el["eligible"] & (el["split"] == "confirmatory") & el.apply(lambda r: _matches(key, _block(r)), axis=1)]
            by_metric = {m: list(g.index) for m, g in cand.groupby("metric")}
            rnd = random.Random(f"{rnd_seed}|{key}")
            for m in by_metric:
                rnd.shuffle(by_metric[m])
            picked = []
            while len(picked) < n and any(by_metric.values()):
                for m in sorted(by_metric):
                    if by_metric[m] and len(picked) < n:
                        picked.append(by_metric[m].pop(0))
            el.loc[picked, "split"] = groupname
    return el


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(cfg: dict, model: str, force: bool = False, records: list[dict] | None = None,
           level: str | None = None) -> Path:
    paths, sc = cfg["paths"], cfg["screening"]
    level = level or cfg["thinking_level"]
    frozen_dir = Path(paths["frozen_dir"])
    if (frozen_dir / "pairs_frozen.csv").exists() and not force:
        raise SystemExit(f"{frozen_dir} already holds a frozen dataset. It is not overwritten, so the "
                         "confirmatory pairs stay fixed. Use --force only if you mean to re-freeze.")
    if records is None:
        records = load_records(Path(paths["runs_dir"]) / "screen" / model / level)
    if not records:
        raise SystemExit(f"No screening answers for {model} yet: run the screen phase first.")
    ents = pd.read_csv(paths["entities"], keep_default_na=False)
    ents["value"] = pd.to_numeric(ents["value"], errors="coerce")
    stats, cuts = add_categories(entity_stats(records, ents, sc["known_tolerance"]))
    pairs = pd.read_csv(paths["verified_pairs"], keep_default_na=False)
    el = split_pairs(eligibility(pairs, stats, sc), sc)
    tri = pd.read_csv(paths["triplets"], keep_default_na=False)
    s = stats.set_index("entity_id")
    def tri_ok(r):
        for k in ("low_entity_id", "mid_entity_id", "high_entity_id"):
            if r[k] not in s.index:
                return False
            x = s.loc[r[k]]
            if x["parsed"] < sc["min_parsed"] or x["refusals"] > sc["max_refusal"] or \
                    (x.get("known", 0) == x.get("known", 0) and x.get("known", 0) > sc["max_known_share"]):
                return False
        return True
    tri_f = tri[tri.apply(tri_ok, axis=1)] if len(tri) else tri
    sdir = Path(paths["screening_dir"]) / model / level
    sdir.mkdir(parents=True, exist_ok=True)
    stats.to_csv(sdir / "entity_stats.csv", index=False)
    el.to_csv(sdir / "pair_eligibility.csv", index=False)
    frozen_dir.mkdir(parents=True, exist_ok=True)
    el.to_csv(frozen_dir / "pairs_frozen.csv", index=False)
    tri_f.to_csv(frozen_dir / "triplets_frozen.csv", index=False)
    info = dict(frozen_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                screening_model=model, thinking_level=level, rules=sc, spread_tertiles=list(cuts),
                counts=el["split"].value_counts().to_dict(), triplets=len(tri_f),
                sha256={f: sha256(frozen_dir / f) for f in ("pairs_frozen.csv", "triplets_frozen.csv")})
    (frozen_dir / "FROZEN.json").write_text(json.dumps(info, indent=2, default=str) + "\n")
    write_report(sdir / "screening_report.md", stats, el, cuts, model, info)
    print(json.dumps(info["counts"]), f"triplets {len(tri_f)}")
    return frozen_dir


def write_report(path: Path, stats: pd.DataFrame, el: pd.DataFrame, cuts, model: str, info: dict) -> None:
    lines = [f"# Screening report: {model}", "",
             f"Frozen {info['frozen_utc']}. Only baseline answers (no comparison) were used.", "",
             f"Uncertainty cut points (spread = log10 of q90/q10): strong prior <= {cuts[0]:.3f} < moderate "
             f"<= {cuts[1]:.3f} < high uncertainty.", "", "## Entities", ""]
    g = stats.groupby(["dataset", "domain", "metric", "scope"]).agg(
        entities=("entity_id", "count"), parsed=("parsed", "mean"), refusals=("refusals", "mean"),
        known=("known", "mean") if "known" in stats else ("parsed", "size"),
        spread=("spread", "median")).reset_index()
    lines += [g.to_markdown(index=False, floatfmt=".2f"), "", "Uncertainty categories:", "",
              stats.groupby(["dataset", "uncertainty"]).size().unstack(fill_value=0).to_markdown(), "",
              "## Pairs", "", el.groupby(["dataset", "domain", "scope", "split"]).size().unstack(fill_value=0).to_markdown(),
              "", "## Why pairs were excluded", ""]
    ex = el[~el["eligible"]]["exclusion_reason"].str.split("; ").explode().str.replace(r"\d+%", "N%", regex=True)
    lines += [ex.value_counts().to_markdown() if len(ex) else "None.", ""]
    path.write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--model", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    freeze(cfg, a.model or cfg["screening"]["model"], a.force)


if __name__ == "__main__":
    main()
