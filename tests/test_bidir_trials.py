"""Question generation and condition assignment (bidirectional study)."""

import re

import pandas as pd
import pytest

from anchoring_llms.bidirectional import prompts as P
from anchoring_llms.bidirectional.trials import generate, load_config, pair_trials, entity_trials
from anchoring_llms.bidirectional.validate import check_baselines_name_no_partner, contains_number, validate_trials


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/bidirectional.yaml")


@pytest.fixture(scope="module")
def bank(cfg):
    return generate(cfg, "bank")


@pytest.fixture(scope="module")
def ents(cfg):
    e = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    return {r["entity_id"]: r for r in e.to_dict("records")}


def test_bank_passes_all_checks(cfg, bank):
    assert validate_trials(bank, cfg) == []


def test_six_core_conditions_per_pair(cfg, bank):
    pairs = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)
    by = {}
    for t in bank:
        by.setdefault(t["pair_id"], set()).add(t["condition"])
    base = {t["target_entity_id"] for t in bank if t["condition"] == "B"}
    for p in pairs.to_dict("records"):
        assert {"LT", "LA", "HT", "HA", "C1", "C2", "C3"} <= by[p["pair_id"]]
        assert p["low_entity_id"] in base and p["high_entity_id"] in base


def test_roles_and_order(bank, ents):
    for t in bank:
        if t["condition"] in ("LT", "LA", "HT", "HA"):
            tgt, par = ents[t["target_entity_id"]], ents[t["partner_entity_id"]]
            if tgt["dataset"] != "young":
                assert (float(tgt["value"]) < float(par["value"])) == (t["condition"] in ("LT", "LA"))
            first = t["turns"][0]
            target_first = first.find(tgt["entity_label"]) < first.find(par["entity_label"])
            assert target_first == (t["condition"] in ("LT", "HT"))
            assert t["turns"][1] == P.estimate_prompt(tgt)


def test_lt_and_ha_share_the_comparison_question(cfg, ents):
    p = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False).iloc[0]
    ts = pair_trials(cfg, "x", p, ents, 2, ["C1"])
    for r in (0, 1):
        lt = next(t for t in ts if t["condition"] == "LT" and t["repetition"] == r)
        ha = next(t for t in ts if t["condition"] == "HA" and t["repetition"] == r)
        assert lt["turns"][0] == ha["turns"][0]  # same comparison, different estimated entity


def test_baselines_name_no_other_entity(cfg, bank):
    pairs = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)
    assert check_baselines_name_no_partner(bank, pairs) == []
    for t in bank:
        if t["condition"] == "B":
            assert t["partner_entity_id"] == "" and len(t["turns"]) == 1


def test_no_true_values_in_item_prompts(bank, ents):
    for t in bank:
        if t["condition"] == "C4":
            continue
        text = "\n".join(t["turns"])
        for eid in (t["target_entity_id"], t["partner_entity_id"]):
            if eid and ents[eid]["dataset"] != "young":
                assert not contains_number(text, float(ents[eid]["value"])), (t["trial_id"], text)


def test_numeric_anchor_is_partner_value(bank, ents):
    c4 = [t for t in bank if t["condition"] == "C4"]
    assert c4
    for t in c4:
        assert t["anchor_value"] == float(ents[t["partner_entity_id"]]["value"])
        assert P.format_anchor(t["anchor_value"]) in t["turns"][0]


def test_contains_number_word_boundaries():
    assert contains_number("did it record 35 attempts", 35)
    assert not contains_number("the 2026 FIFA World Cup", 26)
    assert not contains_number("the 2026 FIFA World Cup", 20)
    assert contains_number("about 1,966 passes", 1966)
    assert not contains_number("about 1,966 passes", 966)


def test_trial_ids_unique_and_stable(cfg, ents):
    p = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False).iloc[3]
    a = pair_trials(cfg, "core", p, ents, 3, ["C1", "C2", "C3"])
    b = pair_trials(cfg, "core", p, ents, 3, ["C1", "C2", "C3"])
    assert [t["trial_id"] for t in a] == [t["trial_id"] for t in b]
    assert len({t["trial_id"] for t in a}) == len(a)
    assert len({t["seed"] for t in a}) == len(a)  # repetitions never share a seed


def test_templates_balanced(cfg, ents):
    p = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False).iloc[0]
    ts = pair_trials(cfg, "core", p, ents, 10, ["C3"])
    for cond in ("LT", "LA", "HT", "HA", "C3"):
        tpl = pd.Series([t["template_id"] for t in ts if t["condition"] == cond]).value_counts()
        assert tpl.get("P1") == tpl.get("P2")


def test_counterbalanced_controls(bank):
    for cond in ("C1", "C2", "C3"):
        orders = pd.Series([t["order"] for t in bank if t["condition"] == cond]).value_counts()
        assert orders["target_first"] == orders["target_second"]


def test_prompts_ask_for_a_number_and_say_not_to_refuse(bank):
    for t in bank:
        assert "Estimate: <number>" in t["turns"][-1]
        assert "instead of refusing" in t["turns"][-1]


def test_screen_phase_is_baselines_only(cfg):
    s = generate(cfg, "screen")
    assert {t["condition"] for t in s} == {"B"}
    assert all(t["partner_entity_id"] == "" for t in s)


def test_forced_choice_has_no_unsure():
    from anchoring_llms.bidirectional.trials import generate, load_config
    cfg = load_config("configs/bidirectional.yaml")
    assert cfg["conditions"]["forced_choice"] and cfg["design_version"] == "bidir-v2"
    trials = generate(cfg, "bank")
    turn1 = [t["turns"][0] for t in trials if t["condition"] in ("LT", "LA", "HT", "HA", "C4", "TRI")]
    assert turn1 and not any("UNSURE" in x for x in turn1)
    assert all("give your best guess" in x for x in turn1)
    v1 = load_config("configs/bidirectional_v1.yaml")
    old = [t["turns"][0] for t in generate(v1, "bank") if t["condition"] == "LT"]
    assert all("UNSURE" in x for x in old)


# ----------------------------------------------------------------------------- answer-word order (bidir-v3)

def test_swap_words():
    assert P.swap_options("MORE or FEWER") == "FEWER or MORE"
    assert P.swap_options("GREATER, SMALLER, or UNSURE") == "SMALLER, GREATER, or UNSURE"
    assert P.swap_question("Does a torch cost more or less than a laptop?") == \
        "Does a torch cost less or more than a laptop?"
    with pytest.raises(ValueError):
        P.swap_question("How tall is it?")


def test_v2_prompts_unchanged_by_the_option_order_code(bank):
    # The committed bank was written before option_order existed: v2 must still produce it exactly.
    import json
    from anchoring_llms.bidirectional.trials import load_trials
    old = load_trials("data/bidirectional/generated_trials/bank.jsonl")
    assert [json.dumps(t, sort_keys=True) for t in bank] == [json.dumps(t, sort_keys=True) for t in old]
    assert not any("options_reversed" in t for t in bank)


@pytest.mark.parametrize("phase", ["triplets", "core"])
def test_v3_offers_the_words_both_ways_round(cfg, phase):
    v3 = load_config("configs/bidirectional_v3.yaml")
    assert v3["design_version"] == "bidir-v3" and v3["conditions"]["option_order"] == "balanced"
    assert v3["paths"]["runs_dir"] != cfg["paths"]["runs_dir"]
    assert v3["paths"]["trials_dir"] != cfg["paths"]["trials_dir"]
    trials = generate(v3, phase)
    assert validate_trials(trials, v3) == []
    comp = [t for t in trials if t["condition"] in ("LT", "LA", "HT", "HA", "TRI")]
    # half of each cell's repetitions reversed, and template x word order fully crossed
    cells = pd.DataFrame(comp).groupby(["pair_id", "condition", "role", "order"])["options_reversed"].mean()
    assert (cells == 0.5).all()
    crossed = pd.DataFrame(comp).groupby(["template_id", "options_reversed"]).size()
    assert len(crossed) == 4 and crossed.max() == crossed.min()
    words = re.compile(r"\b(fewer or more|less or more|smaller or greater|lower or higher)\b")
    for t in comp:
        q, opts = t["turns"][0].split("\n\n")
        if t["options_reversed"]:
            assert words.search(q) and re.match(r"Answer with one word: (FEWER|LESS|SMALLER|LOWER) or ", opts)
        else:
            assert not words.search(q) and re.match(r"Answer with one word: (MORE|GREATER|HIGHER) or ", opts)
    # no other condition changes
    assert not any("options_reversed" in t for t in trials if t["condition"] not in ("LT", "LA", "HT", "HA", "TRI"))
