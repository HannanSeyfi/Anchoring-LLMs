"""Known-partner pairs: an obscure item compared with a famous one (configs/bidirectional_kp.yaml)."""

import pandas as pd
import pytest

from anchoring_llms.bidirectional import known_partner as KP
from anchoring_llms.bidirectional.screen import eligibility
from anchoring_llms.bidirectional.trials import generate, load_config
from anchoring_llms.bidirectional.validate import validate_trials


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/bidirectional_kp.yaml")


@pytest.fixture(scope="module")
def pairs(cfg):
    return pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)


def test_files_match_the_builder(cfg, pairs):
    """The committed pairs are exactly what known_partner.py builds from the raw sources."""
    built = KP.pairs(KP.entities())
    assert list(built["pair_id"]) == list(pairs["pair_id"])


def test_one_famous_and_one_obscure_item_per_pair(cfg, pairs):
    ents = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False).set_index("entity_id")
    for p in pairs.to_dict("records"):
        assert {p["known_entity_id"], p["unknown_entity_id"]} == {p["low_entity_id"], p["high_entity_id"]}
        assert str(ents.loc[p["known_entity_id"], "famous"]) == "True"
        assert str(ents.loc[p["unknown_entity_id"], "famous"]) == "False"
        assert KP.RATIO[0] - 1e-9 <= float(p["gap_ratio"]) <= KP.RATIO[1] + 1e-9


def test_obscure_item_is_low_and_high(pairs):
    counts = pairs.groupby("domain")["unknown_role"].value_counts()
    for domain in KP.DOMAINS:
        assert counts[domain]["low"] >= 5 and counts[domain]["high"] >= 5


def test_bank_passes_all_checks(cfg):
    bank = generate(cfg, "bank")
    assert validate_trials(bank, cfg) == []
    for t in bank:
        if t["condition"] in ("LT", "LA", "HT", "HA"):
            assert "UNSURE" not in t["turns"][0]
            assert "GREATER or SMALLER" in t["turns"][0]


def test_famous_item_must_be_known(cfg, pairs):
    p = pairs.iloc[:1].copy()
    known, unknown = p["known_entity_id"].iloc[0], p["unknown_entity_id"].iloc[0]
    def stats(err):
        return pd.DataFrame([dict(entity_id=known, parsed=1.0, refusals=0.0, median_rel_error=err, known=0.9),
                             dict(entity_id=unknown, parsed=1.0, refusals=0.0, median_rel_error=0.5, known=0.0)])
    sc = cfg["screening"]
    assert eligibility(p, stats(0.02), sc)["eligible"].iloc[0]
    out = eligibility(p, stats(0.30), sc)
    assert not out["eligible"].iloc[0] and "famous" in out["exclusion_reason"].iloc[0]


# ----------------------------------------------------------------------------- bidir-kp2

@pytest.fixture(scope="module")
def cfg2():
    return load_config("configs/bidirectional_kp2.yaml")


def test_two_sided_files_match_the_builder(cfg2):
    pairs = pd.read_csv(cfg2["paths"]["verified_pairs"], keep_default_na=False)
    built = KP.pairs_two_sided(KP.entities())
    assert list(built["pair_id"]) == list(pairs["pair_id"])


def test_each_obscure_item_has_a_taller_and_a_shorter_partner(cfg2):
    pairs = pd.read_csv(cfg2["paths"]["verified_pairs"], keep_default_na=False)
    for item, g in pairs.groupby("item_group"):
        assert sorted(g["unknown_role"]) == ["high", "low"]
        assert (g["unknown_entity_id"] == item).all()
        assert g["known_entity_id"].nunique() == 2
    assert not pairs["known_entity_id"].isin(KP.TWO_SIDED_EXCLUDE_FAMOUS).any()


def test_two_sided_bank_estimates_only_the_obscure_item(cfg2):
    pairs = pd.read_csv(cfg2["paths"]["verified_pairs"], keep_default_na=False)
    known = dict(zip(pairs["pair_id"], pairs["known_entity_id"]))
    bank = generate(cfg2, "bank")
    assert validate_trials(bank, cfg2) == []
    pair_trials = [t for t in bank if t["pair_id"]]
    assert pair_trials and all(t["target_entity_id"] != known[t["pair_id"]] for t in pair_trials)
    assert {t["condition"] for t in pair_trials} == {"LT", "LA", "HT", "HA", "C1", "C3", "C4"}
