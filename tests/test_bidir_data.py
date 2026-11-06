"""Data validation and pair construction (bidirectional study)."""

import math

import pandas as pd
import pytest

from anchoring_llms.bidirectional import pairs as PR
from anchoring_llms.bidirectional.sources import build_entities, nice_name

ENT = "data/bidirectional/candidate_entities.csv"


@pytest.fixture(scope="module")
def ents():
    return pd.read_csv(ENT, keep_default_na=False)


def test_entity_file_is_current(ents):
    fresh = build_entities()
    assert len(fresh) == len(ents)
    assert list(fresh["entity_id"]) == list(ents["entity_id"])
    assert (fresh["value"].astype(float).values == ents["value"].astype(float).values).all()


def test_every_value_has_a_source(ents):
    for col in ("source_url", "source_endpoint", "retrieved_utc", "verification", "metric_definition"):
        assert (ents[col].astype(str).str.len() > 0).all(), col
    assert ents["entity_id"].is_unique


def test_known_fifa_values():
    """The example in the instructions: tournament attempts Argentina 115, France 139 (FIFA)."""
    e = build_entities().set_index("entity_id")
    assert e.loc["wc2026-team-ARG-attempts-tournament", "value"] == 115
    assert e.loc["wc2026-team-FRA-attempts-tournament", "value"] == 139
    assert e.loc["wc2026-team-ARG-attempts-group", "matches_played"] == 3


def test_group_stage_equal_exposure(ents):
    g = ents[(ents["scope"] == "group_stage") & (ents["domain"] == "teams")]
    assert set(g["matches_played"].astype(int)) == {3}


def test_match_sums_equal_fifa_totals():
    m = pd.read_csv("data/bidirectional/raw_sources/fifa_wc2026/team_match_stats.csv")
    t = pd.read_csv("data/bidirectional/raw_sources/fifa_wc2026/team_tournament_totals.csv").set_index("team_code")
    s = m.groupby("team_code")["AttemptAtGoal"].sum()
    assert (s == t.loc[s.index, "AttemptAtGoal"]).all()


def test_olympics_rows_add_up():
    t = pd.read_csv("data/bidirectional/raw_sources/olympics_2026/medal_table_wikipedia.csv")
    assert (t["gold"] + t["silver"] + t["bronze"] == t["total"]).all()
    assert t[["gold", "silver", "bronze", "total"]].sum().tolist() == [116, 118, 115, 349]


def test_nice_name():
    assert nice_name("Juan MUSSO") == "Juan Musso"
    assert nice_name("MOHAMMAD ALDAOUD") == "Mohammad Aldaoud"


def test_verified_pairs_follow_rules():
    cfg = PR.load_config("configs/bidirectional.yaml")
    p = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)
    e = pd.read_csv(ENT, keep_default_na=False).set_index("entity_id")
    assert p["pair_id"].is_unique
    for r in p.to_dict("records"):
        lo, hi = e.loc[r["low_entity_id"]], e.loc[r["high_entity_id"]]
        for k in ("metric", "scope", "unit", "dataset"):
            assert lo[k] == hi[k]
        assert float(lo["value"]) < float(hi["value"])
        if r["dataset"] in ("wc2026", "wc2022", "olympics2026"):
            rule = cfg["pairs"]["rules"][f"{r['dataset']}:{r['domain']}"]
            assert rule["ratio"][0] <= float(hi["value"]) / float(lo["value"]) <= rule["ratio"][1]
        if r["domain"] == "players":
            assert lo["position"] == hi["position"]
        assert "differ" not in str(lo["verification"]).lower()


def test_entity_reuse_is_capped():
    cfg = PR.load_config("configs/bidirectional.yaml")
    p = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)
    for key, rule in cfg["pairs"]["rules"].items():
        ds, dom = key.split(":")
        sub = p[(p["dataset"] == ds) & (p["domain"] == dom)]
        for _, g in sub.groupby(["metric", "scope"]):
            uses = pd.concat([g["low_entity_id"], g["high_entity_id"]]).value_counts()
            assert uses.max() <= rule["max_uses"]


def test_pair_selection_is_deterministic():
    cfg = PR.load_config("configs/bidirectional.yaml")
    e = pd.read_csv(ENT, keep_default_na=False)
    groups = PR.team_groups()
    rules = {"wc2026:teams": cfg["pairs"]["rules"]["wc2026:teams"]}
    c = PR.candidate_pairs(e, rules, groups)
    a = PR.select_pairs(c, rules, 1)
    b = PR.select_pairs(c, rules, 1)
    assert list(a["pair_id"]) == list(b["pair_id"])


def test_triplets_are_ordered():
    t = pd.read_csv("data/bidirectional/triplets.csv")
    assert ((t["truth_low"] < t["truth_mid"]) & (t["truth_mid"] < t["truth_high"])).all()
    ids = pd.concat([t["low_entity_id"], t["mid_entity_id"], t["high_entity_id"]])
    assert ids.is_unique
