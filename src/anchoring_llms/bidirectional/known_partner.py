"""Known-partner pairs: an obscure item compared with a famous item of the same kind.

Pilot runs A and B (qwen3-32b) found no item anchoring between two World Cup 2026 teams the model
knows nothing about, but a clear pull on cheap products compared with expensive ones the model
knows. The explanation to test: an item can only act as an anchor when the model knows roughly
what the *other* item is worth. Here every pair has one well-known item (Eiffel Tower, Mont
Blanc, ...) and one obscure item of the same kind (a skyscraper in Taichung, a peak in Bolivia).
Predictions: the obscure item moves towards the famous one (in both directions: up when the
famous item is higher, down when it is lower); the famous item hardly moves.

Sources: Wikidata, see data/bidirectional/raw_sources/known_partner/README.md.

    python -m anchoring_llms.bidirectional.known_partner          # entities, pairs, config paths
    python -m anchoring_llms.bidirectional.known_partner --config configs/bidirectional_kp2.yaml
                                                                  # bidir-kp2: two partners per item
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import pandas as pd

from .pairs import make_pair
from .trials import load_config

RAW = Path("data/bidirectional/raw_sources/known_partner")
RETRIEVED = "2026-11-06"
DOMAINS = {
    "mountains": dict(metric="height_above_sea_level", metric_label="height above sea level",
                      unit="metres above sea level", entity_type="mountain",
                      question="How high above sea level is {label}?",
                      definition="Wikidata elevation above sea level (P2044), metres"),
    "buildings": dict(metric="height", metric_label="height", unit="metres", entity_type="building",
                      question="How tall is {label}?",
                      definition="Wikidata height (P2048), metres"),
}
# An obscure building is kept only if Wikidata dates it to 2024 or earlier and does not mark it as
# unfinished; this one is also left out because it is a well-known building under another name
# (the Abraj Al Bait clock tower in Mecca).
EXCLUDE = {"Q18712428"}
BAD_STATES = {"building or structure under construction", "on hold", "permanently closed"}
RATIO = (1.3, 3.0)
MAX_USES = 4          # times a famous item may be a partner, per domain (4 balances the directions better than 3)
PER_DOMAIN = 28       # pairs per domain (screening will drop some)
SEED = 20261106


def _label(r: dict) -> str:
    where = ", ".join(x for x in (r.get("admin", ""), r.get("country", "")) if x)
    return f"{r['name']} (in {where})" if where else r["name"]


def entities() -> pd.DataFrame:
    fam = pd.read_csv(RAW / "famous.tsv", sep="\t", keep_default_na=False)
    obs = pd.read_csv(RAW / "obscure_wikidata.tsv", sep="\t", keep_default_na=False)
    dates = pd.read_csv(RAW / "building_dates_wikidata.tsv", sep="\t", keep_default_na=False).set_index("qid")
    rows = []
    for r in fam.to_dict("records"):
        d = DOMAINS[r["domain"]]
        rows.append(_entity(r, d, label=r["name"], famous=True,
                            verification=f"famous item ({r['sitelinks']} Wikipedia editions); {r['note']}"))
    for r in obs.to_dict("records"):
        if r["qid"] in EXCLUDE:
            continue
        if r["domain"] == "buildings":
            if r["qid"] not in dates.index:
                continue
            x = dates.loc[r["qid"]]
            year = max([int(v) for v in (x["opened_P1619"], x["inception_P571"]) if str(v).isdigit()] or [0])
            if not 0 < year <= 2024 or x["state_of_use_P5817"] in BAD_STATES:
                continue
        d = DOMAINS[r["domain"]]
        rows.append(_entity(r, d, label=_label(r), famous=False,
                            verification=f"obscure item ({r['sitelinks']} Wikipedia editions); one Wikidata statement"))
    return pd.DataFrame(rows)


def _entity(r: dict, d: dict, label: str, famous: bool, verification: str) -> dict:
    url = f"https://www.wikidata.org/wiki/{r['qid']}"
    return dict(entity_id=f"kp-{r['qid']}", dataset="kp", domain=r["domain"], competition="", year="",
                event_end_date="", after_cutoff=False, entity_type=d["entity_type"], entity_name=r["name"],
                entity_label=label, entity_code=r["qid"], team_code="", team_name="", position="",
                famous=famous, metric=d["metric"], metric_label=d["metric_label"],
                metric_definition=d["definition"], scope="fact", unit=d["unit"], value=float(r["value"]),
                integer=False, matches_played="", minutes_played="",
                question=d["question"].format(label=label), source_name="Wikidata",
                source_url=url, source_endpoint="https://query.wikidata.org/sparql",
                retrieved_utc=RETRIEVED, verification=verification,
                notes="known partner" if famous else "obscure target")


def pairs(ents: pd.DataFrame) -> pd.DataFrame:
    """Each obscure item gets one famous partner; the obscure item is lower in half the pairs."""
    rows = []
    for domain in DOMAINS:
        fam = ents[(ents["domain"] == domain) & ents["famous"]].to_dict("records")
        obs = ents[(ents["domain"] == domain) & ~ents["famous"]].to_dict("records")
        uses = {f["entity_id"]: 0 for f in fam}
        rnd = random.Random(f"{SEED}|{domain}")
        want_lower = True
        n = 0
        for o in obs:                       # file order = Wikidata MD5 order, fixed
            if n >= PER_DOMAIN:
                break
            for lower in (want_lower, not want_lower):
                ok = [f for f in fam if uses[f["entity_id"]] < MAX_USES and
                      RATIO[0] <= (f["value"] / o["value"] if lower else o["value"] / f["value"]) <= RATIO[1]]
                if ok:
                    least = min(uses[f["entity_id"]] for f in ok)
                    f = rnd.choice([f for f in ok if uses[f["entity_id"]] == least])
                    break
            else:
                continue
            uses[f["entity_id"]] += 1
            lo, hi = (o, f) if o["value"] < f["value"] else (f, o)
            p = make_pair(pd.Series(lo), pd.Series(hi), {}, 2.0)
            p.update(known_entity_id=f["entity_id"], unknown_entity_id=o["entity_id"],
                     unknown_role="low" if lo is o else "high",
                     ambiguities="Wikidata value; obscure item's value has one statement only")
            rows.append(p)
            want_lower = not want_lower if (lo is o) == want_lower else want_lower
            n += 1
    out = pd.DataFrame(rows)
    assert out["pair_id"].is_unique
    return out


TWO_SIDED_MAX_USES = 8   # each obscure item takes two partners; few famous buildings are short enough, so 8
TWO_SIDED_PER_DOMAIN = 28
# Famous items the model did not know in the bidir-kp1 screening (baselines only): Mount Olympus
# (Greece), baseline median 12% below its height. Left out so its pairs are not lost again.
TWO_SIDED_EXCLUDE_FAMOUS = {"kp-Q80344"}


def pairs_two_sided(ents: pd.DataFrame) -> pd.DataFrame:
    """Design bidir-kp2: each obscure item gets one taller and one shorter famous partner.

    The item effect is then the estimate after the taller partner minus after the shorter one, so
    whatever a co-mention or a comparison does by itself is the same on both sides and cancels.
    Items are taken in file order (Wikidata MD5 order) and kept only if both partners exist.
    """
    rows = []
    for domain in DOMAINS:
        fam = ents[(ents["domain"] == domain) & ents["famous"] &
                   ~ents["entity_id"].isin(TWO_SIDED_EXCLUDE_FAMOUS)].to_dict("records")
        obs = ents[(ents["domain"] == domain) & ~ents["famous"]].to_dict("records")
        uses = {f["entity_id"]: 0 for f in fam}
        rnd = random.Random(f"{SEED}|two-sided|{domain}")
        n = 0
        for o in obs:
            if n >= TWO_SIDED_PER_DOMAIN:
                break
            chosen = []
            for higher in (True, False):
                ok = [f for f in fam if uses[f["entity_id"]] < TWO_SIDED_MAX_USES and
                      RATIO[0] <= (f["value"] / o["value"] if higher else o["value"] / f["value"]) <= RATIO[1]]
                if not ok:
                    break
                least = min(uses[f["entity_id"]] for f in ok)
                chosen.append(rnd.choice([f for f in ok if uses[f["entity_id"]] == least]))
            if len(chosen) < 2:
                continue
            for f in chosen:
                uses[f["entity_id"]] += 1
                lo, hi = (o, f) if o["value"] < f["value"] else (f, o)
                p = make_pair(pd.Series(lo), pd.Series(hi), {}, 2.0)
                p.update(known_entity_id=f["entity_id"], unknown_entity_id=o["entity_id"],
                         unknown_role="low" if lo is o else "high", item_group=o["entity_id"],
                         ambiguities="Wikidata value; obscure item's value has one statement only")
                rows.append(p)
            n += 1
    out = pd.DataFrame(rows)
    assert out["pair_id"].is_unique
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional_kp.yaml")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    paths = cfg["paths"]
    ents = entities()
    pr = pairs_two_sided(ents) if cfg.get("known_partner_design") == "two_sided" else pairs(ents)
    used = set(pr["low_entity_id"]) | set(pr["high_entity_id"])
    ents = ents[ents["entity_id"].isin(used)]
    Path(paths["entities"]).parent.mkdir(parents=True, exist_ok=True)
    ents.to_csv(paths["entities"], index=False)
    pr.to_csv(paths["verified_pairs"], index=False)
    pr.to_csv(paths["candidate_pairs"], index=False)
    pd.DataFrame(columns=["triplet_id", "low_entity_id", "mid_entity_id", "high_entity_id"]).to_csv(
        paths["triplets"], index=False)
    print(f"{len(ents)} entities ({int(ents['famous'].sum())} famous), {len(pr)} pairs")
    print(pr.groupby(["domain", "unknown_role"]).size().to_string())
    print("gap ratio:", pr["gap_ratio"].describe()[["min", "50%", "max"]].round(2).to_dict())


if __name__ == "__main__":
    main()
