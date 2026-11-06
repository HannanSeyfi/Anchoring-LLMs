"""Reading replies: estimates, refusals, flags, turn-1 answers."""

from anchoring_llms.bidirectional.responses import (comparison_correct, parse_comparison_word, read_estimate,
                                                    read_turn1)


def test_estimates():
    assert read_estimate("Estimate: 42")["estimate"] == 42
    assert read_estimate("I think about 40.\nEstimate: 1,966")["estimate"] == 1966
    assert read_estimate("**Estimate:** 2,925.4")["estimate"] == 2925.4
    assert read_estimate("Estimate: -3")["flag_negative"]
    r = read_estimate("Estimate: 30-40")
    assert r["estimate"] == 30 and r["flag_range"]
    assert read_estimate("Estimate: 35%")["estimate"] == 35


def test_no_estimate_line_is_not_zero():
    r = read_estimate("Probably around 40 attempts.")
    assert r["estimate"] is None and r["parse_status"] == "invalid"


def test_refusal():
    r = read_estimate("I'm sorry, but the 2026 World Cup has not happened yet as of my knowledge cutoff.")
    assert r["estimate"] is None and r["refusal"] and r["parse_status"] == "refusal"
    # a guess despite saying it is unsure is an answer, flagged as uncertain
    r = read_estimate("I don't know exactly, but my guess:\nEstimate: 45")
    assert r["estimate"] == 45 and not r["refusal"] and r["flag_uncertain"]


def test_cut_off():
    assert read_estimate("Let me compute 12 + 15 + ", finish_reason="length")["parse_status"] == "cut_off"


def test_turn1_words():
    assert parse_comparison_word("MORE") == "more"
    assert parse_comparison_word("**FEWER**") == "fewer"
    assert parse_comparison_word("Lower.") == "fewer"
    assert parse_comparison_word("GREATER") == "more"
    assert parse_comparison_word("UNSURE") == "unsure"
    assert parse_comparison_word("") is None


def test_contamination_flag():
    assert read_turn1("FEWER - France had about 48 attempts", "LT")["contaminated"]
    assert not read_turn1("FEWER", "LT")["contaminated"]
    assert not read_turn1("MORE, at the 2026 World Cup", "LT")["contaminated"]  # years are not statistics


def test_comparison_correct():
    # LT: low named first -> correct answer "fewer"; LA: high first -> "more"
    assert comparison_correct("LT", "target_first", "low", "fewer")
    assert comparison_correct("LA", "target_second", "low", "more")
    assert comparison_correct("HT", "target_first", "high", "more")
    assert comparison_correct("HA", "target_second", "high", "fewer")
    assert comparison_correct("LT", "target_first", "low", "unsure") is None
    assert comparison_correct("C4", "", "low", "fewer")
