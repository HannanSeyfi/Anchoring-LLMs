"""Context isolation, the runner, screening/freezing and the analysis on simulated data.

The simulated model (anchoring_llms.bidirectional.simulate) is NOT data: these tests only check
that the code finds the pattern that was put in.
"""

import copy
import json

import pandas as pd
import pytest

from anchoring_llms.backends import Completion, chat_prompt, OpenAIChatBackend, Request
from anchoring_llms.bidirectional.analysis import analyse, classify, pair_effects, summarise, trial_table
from anchoring_llms.bidirectional.run import load_records, run, run_batch
from anchoring_llms.bidirectional.screen import freeze
from anchoring_llms.bidirectional.simulate import SimBackend
from anchoring_llms.bidirectional.trials import generate, load_config


class EchoBackend:
    """Records every prompt; replies with a marker that names the trial."""
    name = "echo"

    def __init__(self):
        self.requests = []

    def generate(self, requests):
        self.requests += requests
        return [[Completion("", f"REPLY[{r.cell_id}]\nEstimate: 7", 0, 3, False, "stop")] for r in requests]


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    c = load_config("configs/bidirectional.yaml")
    t = tmp_path_factory.mktemp("bidir")
    c["paths"].update(frozen_dir=str(t / "frozen"), screening_dir=str(t / "scr"), runs_dir=str(t / "runs"),
                      results_dir=str(t / "res"), trials_dir=str(t / "trials"))
    c["conditions"].update(repetitions=4, baseline_repetitions=6)
    c["screening"]["samples"] = 6
    c["analysis"]["bootstrap"] = 300
    return c


def test_each_trial_has_its_own_history(cfg):
    trials = [t for t in generate(cfg, "bank") if t["condition"] in ("LT", "HA", "B", "C1")][:40]
    be = EchoBackend()
    recs = run_batch(be, trials, 0, {})
    by_cell = {r.cell_id: r for r in be.requests}
    for t, r in zip(trials, recs):
        first = by_cell[f"{t['trial_id']}#1"].prompt
        assert first[0]["role"] == "system" and len(first) == 2 and first[1]["content"] == t["turns"][0]
        if t["n_turns"] == 2:
            second = by_cell[f"{t['trial_id']}#2"].prompt
            # turn 2 = system, turn 1, the model's own turn-1 reply (unchanged), turn 2
            assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
            assert second[2]["content"] == f"REPLY[{t['trial_id']}#1]\nEstimate: 7"
            assert second[3]["content"] == t["turns"][1]
            assert r["history_2"] == second
        # nothing from any other trial is in the context
        for req in (by_cell.get(f"{t['trial_id']}#1"), by_cell.get(f"{t['trial_id']}#2")):
            if req is None:
                continue
            text = json.dumps(req.prompt)
            others = [o["trial_id"] for o in trials if o["trial_id"] != t["trial_id"]]
            assert not any(o in text for o in others)


def test_raw_replies_kept_and_resume(cfg, tmp_path):
    c = copy.deepcopy(cfg)
    c["paths"]["runs_dir"] = str(tmp_path / "runs")
    trials = [t for t in generate(c, "bank")][:30]
    folder = run(c, "core", "x", "simulated", trials=trials)
    recs = load_records(folder)
    assert len(recs) == 30 and all("reply_1" in r and r["simulated"] for r in recs)
    run(c, "core", "x", "simulated", trials=trials)  # second run: nothing new
    assert len(load_records(folder)) == 30


def test_chat_prompt_accepts_conversations():
    class Tok:
        def apply_chat_template(self, msgs, tokenize, add_generation_prompt, enable_thinking):
            return "".join(f"<{m['role']}>{m['content']}" for m in msgs) + "<assistant><think>"
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "MORE"}, {"role": "user", "content": "b"}]
    assert chat_prompt(Tok(), msgs) == "<user>a<assistant>MORE<user>b<assistant><think>\n"
    assert chat_prompt(Tok(), "a") == "<user>a<assistant><think>\n"


def test_openai_chat_backend_sends_messages(tmp_path):
    sent = []
    def post(payload):
        sent.append(payload)
        return {"choices": [{"message": {"content": "Estimate: 12"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "estimated_cost": 0.0001}}
    be = OpenAIChatBackend(base_url="https://example.invalid/v1", hf_id="x", api_model="m", api_key=None,
                           price_in=0.1, price_out=0.1, max_spend_usd=1, spend_path=tmp_path / "s.json", post=post)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
    out = be.generate([Request("c", msgs, 0, 1, 1)])
    assert out[0][0].answer == "Estimate: 12" and sent[0]["messages"] == msgs
    with pytest.raises(ValueError):
        be.generate([Request("c", msgs, 512, 1, 1)])


def _simulate(cfg, tmp_path, pattern, **sim):
    c = copy.deepcopy(cfg)
    c["simulation"] = sim
    for k in ("frozen_dir", "screening_dir", "runs_dir", "results_dir"):
        c["paths"][k] = str(tmp_path / pattern / k)
    scr = generate(c, "screen")
    folder = run(c, "screen", "x", "simulated", trials=scr)
    freeze(c, "simulated", records=load_records(folder), force=True)
    core = [t for t in generate(c, "core") if t["dataset"] in ("wc2026", "olympics2026") or t["pair_id"] == ""]
    folder = run(c, "core", "x", "simulated", trials=core, pattern=pattern)
    df = trial_table(load_records(folder))
    pe = pair_effects(df)
    s = summarise(pe[pe["split"] == "pilot"], c).set_index("contrast")
    return s, c


@pytest.mark.parametrize("pattern,expected", [
    ("bidirectional", "bidirectional assimilation"), ("contrast", "contrast (moves away)")])
def test_analysis_finds_the_simulated_pattern(cfg, tmp_path, pattern, expected):
    s, _ = _simulate(cfg, tmp_path, pattern)  # with answer noise and refusals
    assert s.loc["comparison_vs_C1", "pattern"] == expected


@pytest.mark.parametrize("pattern,expected", [
    ("low_only", "low entity only"), ("high_only", "high entity only")])
def test_one_way_patterns_keep_the_roles_apart(cfg, tmp_path, pattern, expected):
    # Without answer noise a direction with no pull gives exactly no shift, so this checks that the
    # low and high entities and the signs are never mixed up.
    s, _ = _simulate(cfg, tmp_path, pattern, noise=0.0, refusal_rate=0.0)
    assert s.loc["comparison_vs_C1", "pattern"] == expected


def test_no_effect_is_not_called_an_effect(cfg, tmp_path):
    s, _ = _simulate(cfg, tmp_path, "none", noise=0.0, refusal_rate=0.0, no_commitment=0.0)
    assert s.loc["comparison_vs_C1", "pattern"] in ("equivalent to no effect", "no reliable effect")
    assert s.loc["C1_vs_B", "pattern"] in ("equivalent to no effect", "no reliable effect")


def test_full_analysis_writes_report(cfg, tmp_path):
    s, c = _simulate(cfg, tmp_path, "bidirectional")
    res = analyse(c, "simulated", smoke=True)
    out = tmp_path / "bidirectional" / "results_dir"
    report = (out.parent / "results_dir_smoke" / "simulated" / "off" / "report.md").read_text()
    assert "SIMULATED DATA" in report
    assert len(res["overall"]) > 0


def test_freeze_refuses_to_overwrite(cfg, tmp_path):
    c = copy.deepcopy(cfg)
    for k in ("frozen_dir", "screening_dir", "runs_dir"):
        c["paths"][k] = str(tmp_path / k)
    scr = generate(c, "screen")[:600]
    folder = run(c, "screen", "x", "simulated", trials=scr)
    freeze(c, "simulated", records=load_records(folder), force=True)
    with pytest.raises(SystemExit):
        freeze(c, "simulated", records=load_records(folder))


def test_classify_rules():
    assert classify((0.1, 0.05, 0.2), (0.1, 0.02, 0.2), 0.05) == "bidirectional assimilation"
    assert classify((0.1, 0.05, 0.2), (0.0, -0.1, 0.1), 0.05) == "low entity only"
    assert classify((0.0, -0.01, 0.01), (0.0, -0.02, 0.02), 0.05) == "equivalent to no effect"
    assert classify((0.0, -0.2, 0.2), (0.0, -0.2, 0.2), 0.05) == "no reliable effect"
    assert classify((-0.1, -0.2, -0.05), (-0.1, -0.2, -0.05), 0.05) == "contrast (moves away)"


def test_log1p_handles_zero_and_invalid():
    df = trial_table([{"parse_status": "ok", "estimate": 0.0, "condition": "B"},
                      {"parse_status": "refusal", "estimate": None, "condition": "B"},
                      {"parse_status": "ok", "estimate": -5.0, "condition": "B"}])
    assert df["z"].iloc[0] == 0.0
    assert df["z"].isna().iloc[1] and df["z"].isna().iloc[2]
    assert list(df["valid"]) == [True, False, False]
