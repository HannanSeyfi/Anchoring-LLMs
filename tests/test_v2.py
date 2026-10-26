"""Question set v2: screening, picking questions, and the pipeline changes that came with it."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from anchoring_llms import analysis, run, screen, select_items
from anchoring_llms.anchors import make_anchor, plausible_range
from anchoring_llms.backends import WAIT, Request
from anchoring_llms.items import load_items
from anchoring_llms.parsing import parse_estimate

from test_deepinfra import FakeAPI, make

REPO = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------- candidate files

@pytest.mark.parametrize("study", ["study1", "study2"])
def test_candidate_files_are_complete(study):
    cfg = run.load_config(REPO / "configs/pilot_v2.yaml")
    items = screen.load_candidates(REPO, cfg, study)  # also checks that ids are unique across files
    assert len(items) >= 60
    assert all(it.truth is not None and it.truth > 0 and it.domain for it in items)
    if study == "study2":
        assert all(it.reference is not None and it.reference != it.truth for it in items)
    for path in screen.candidate_files(cfg, study):
        notes = pd.read_csv(REPO / path)
        assert notes["truth_note"].notna().all() and notes["source"].notna().all()


def test_later_study2_batches_leave_room_to_adjust():
    for name in ("candidates_study2_neo.csv", "candidates_study2_events.csv"):
        df = pd.read_csv(REPO / "data/items_v2" / name)
        assert ((df["truth"] - df["reference"]).abs() / df["reference"] >= 0.15).all(), name
    events = pd.read_csv(REPO / "data/items_v2/candidates_study2_events.csv")
    assert events["question"].str.endswith("after your training data ends, so you will need to estimate.").all()


# ----------------------------------------------------------------------------- pipeline changes

def test_cut_off_replies_do_not_guess_a_number():
    cut = "The lake is 30 km long and 2 km wide, so 30 * 2 = 60"
    assert parse_estimate(cut) == 60                    # old behaviour: the last number
    assert parse_estimate(cut, fallback=False) is None  # v2: counted as no answer
    assert parse_estimate("Estimate: 1,234", fallback=False) == 1234


def test_min_factor_keeps_anchors_away_from_a_confident_model():
    rng = plausible_range([100, 100, 101, 100, 99, 100, 100], (0.1, 0.9), 0.0)
    near_plain = make_anchor(rng, "high", 0.25, "round", False, key="k")
    near = make_anchor(rng, "high", 0.25, "round", False, key="k", min_factor=1.5)
    far_low = make_anchor(rng, "low", 1.0, "round", False, key="k", min_factor=5)
    assert near_plain < 150 <= near
    assert far_low <= 20


def test_wait_extends_short_thinking(tmp_path):
    api = FakeAPI()  # thinks for 100 tokens each time
    be = make(api, tmp_path)
    plain, longer, capped = be.generate([Request("a", "Q?", 512, 1, 1),
                                         Request("b", "Q?", 512, 1, 1, min_thinking=300),
                                         Request("c", "Q?", 512, 1, 1, min_thinking=5000)])
    assert plain[0].waits == 0 and plain[0].thinking_tokens == 100
    assert longer[0].waits == 2 and longer[0].thinking.count(WAIT.strip()) == 2
    assert longer[0].thinking_tokens >= 300
    assert capped[0].waits == 3  # never more than MAX_WAITS
    assert longer[0].answer.endswith("Estimate: 900")


def test_wait_extends_short_thinking_on_vllm():
    from types import SimpleNamespace

    from anchoring_llms.backends import VLLMBackend

    from test_deepinfra import FakeTokenizer

    class FakeLLM:  # every continuation thinks for 100 more tokens, or up to the limit
        def generate(self, prompts, params, use_tqdm=False):
            outs = []
            for p in params:
                n = min(100, p["max_tokens"])
                outs.append(SimpleNamespace(outputs=[SimpleNamespace(
                    text=" more" * n, token_ids=[0] * n, finish_reason="stop" if n == 100 else "length")]))
            return outs

    be = VLLMBackend.__new__(VLLMBackend)  # no GPU: skip loading a model
    be.tokenizer, be.llm = FakeTokenizer(), FakeLLM()
    be._params = lambda n, max_tokens, seed, stop=None: {"max_tokens": max_tokens}
    requests = [Request("a", "Q?", 512, 1, 1, min_thinking=300), Request("b", "Q?", 512, 1, 1)]
    thinking = {0: [("start", 100, False, 0)], 1: [("start", 100, False, 0)]}
    be._extend_thinking(requests, ["P", "P"], thinking)
    text, tokens, truncated, waits = thinking[0][0]
    assert waits == 2 and tokens == 302 and not truncated and text.count("Wait,") == 2
    assert thinking[1][0] == ("start", 100, False, 0)  # no minimum set: unchanged


def test_study2_summary_uses_the_median_over_questions():
    df = pd.DataFrame({"model": "m", "thinking_level": "off", "item_id": list("ABCDE"),
                       "adjustment": [0.4, 0.5, 0.6, 0.5, 40.0]})
    mean = analysis.summarise_over_items(df, "adjustment", ["model"])["mean"].iloc[0]
    median = analysis.summarise_over_items(df, "adjustment", ["model"], stat="median")["mean"].iloc[0]
    assert mean > 8 and median == pytest.approx(0.5)


# ----------------------------------------------------------------------------- picking questions

def _summary(rows):
    base = {"answers": 40, "parsed_min": 1.0, "known_max": 0.0, "spread_min": 0.3, "spread_mean": 0.3,
            "error_max": 0.1}
    return pd.DataFrame([{**base, **r} for r in rows])


def _items(ids_domains):
    from anchoring_llms.items import Item
    return {i: Item(i, f"Question {i}?", "m", 100.0, False, d) for i, d in ids_domains}


def test_pick_applies_the_rules_and_the_domain_limit():
    sc = run.load_config(REPO / "configs/pilot_v2.yaml")["screening"]
    sc = {**sc, "study1": {**sc["study1"], "n_items": 3, "max_per_domain": 2}}
    items = _items([("A", "lakes"), ("B", "lakes"), ("C", "lakes"), ("D", "islands"), ("E", "islands")])
    summary = _summary([
        {"model": "qwen3-32b", "item_id": "A", "spread_mean": 0.9, "spread_min": 0.8},
        {"model": "qwen3-32b", "item_id": "B", "spread_mean": 0.8, "spread_min": 0.7},
        {"model": "qwen3-32b", "item_id": "C", "spread_mean": 0.7, "spread_min": 0.6},  # domain limit
        {"model": "qwen3-32b", "item_id": "D", "known_max": 0.9},                      # known
        {"model": "qwen3-32b", "item_id": "E", "spread_min": 0.02, "spread_mean": 0.05},  # too similar
        {"model": "small", "item_id": "A", "parsed_min": 0.5, "parsed_low": 0.5},     # small model fails
        {"model": "small", "item_id": "C", "parsed_min": 0.4, "parsed_low": 1.0},     # refuses only with thinking off
        {"model": "small", "item_id": "B"},
    ])
    df = select_items.pick(summary, items, "study1", sc).set_index("item_id")
    assert df.loc["B", "status"] == "picked"
    assert df.loc["C", "status"] == "picked"  # A fails, so C is within the limit of 2 lakes
    assert "known" in df.loc["D", "reasons"] and "too similar" in df.loc["E", "reasons"]
    assert "small: only 50%" in df.loc["A", "reasons"]
    # only two questions pass, so the third place is filled with one that fails a single rule
    assert (df["status"] == "picked to fill a gap").sum() == 1
    assert df["status"].str.startswith("picked").sum() == 3


def test_pick_study2_wants_room_to_adjust():
    sc = run.load_config(REPO / "configs/pilot_v2.yaml")["screening"]
    sc = {**sc, "study2": {**sc["study2"], "n_items": 2, "min_thinking_gain": None}}  # the first rule set
    items = _items([("A", "orbits"), ("B", "orbits"), ("C", "gravity")])
    summary = _summary([
        {"model": "qwen3-32b", "item_id": "A", "adjustment_off": 0.3},
        {"model": "qwen3-32b", "item_id": "B", "adjustment_off": 0.97},  # already knows the answer
        {"model": "qwen3-32b", "item_id": "C", "adjustment_off": 0.6},
    ])
    df = select_items.pick(summary, items, "study2", sc).set_index("item_id")
    assert list(df.index[:2]) == ["A", "C"]  # least adjustment first
    assert df.loc["B", "status"] == "did not pass" and "close to the true value" in df.loc["B", "reasons"]


def test_pick_study2_wants_thinking_to_move_the_answer():
    sc = run.load_config(REPO / "configs/pilot_v2.yaml")["screening"]
    sc = {**sc, "study2": {**sc["study2"], "n_items": 2, "min_thinking_gain": 0.2}}
    items = _items([("A", "orbits"), ("B", "orbits"), ("C", "films"), ("D", "films")])
    summary = _summary([
        {"model": "qwen3-32b", "item_id": "A", "adjustment_off": 0.02, "adjustment_low": 0.91},  # Itokawa-like
        {"model": "qwen3-32b", "item_id": "B", "adjustment_off": 0.0, "adjustment_low": 0.0},    # knows nothing
        {"model": "qwen3-32b", "item_id": "C", "adjustment_off": 0.3, "adjustment_low": 3.0},    # overshoots
        {"model": "qwen3-32b", "item_id": "D", "adjustment_off": 0.5, "adjustment_low": 0.8},
    ])
    df = select_items.pick(summary, items, "study2", sc).set_index("item_id")
    assert list(df.index[:2]) == ["A", "D"]  # largest gain first
    assert df.loc["A", "score"] == pytest.approx(0.89)
    for i in ("B", "C"):
        assert df.loc[i, "status"] == "did not pass" and "closer to the true value" in df.loc[i, "reasons"]


# ----------------------------------------------------------------------------- end to end

def test_screen_select_and_run_v2(tmp_path):
    """Screen with the simulated model, pick questions, run the v2 pilot on them, analyse."""
    cfg = yaml.safe_load((REPO / "configs/pilot_v2.yaml").read_text())
    cfg["screening"]["output_dir"] = str(tmp_path / "screen")
    cfg["screening"]["results_dir"] = str(tmp_path / "results_screen")
    cfg["output_dir"] = str(tmp_path / "pilot")
    picked = tmp_path / "results_screen_smoke" / "items"  # smoke runs never touch data/items_v2
    cfg["items"] = {s: str(picked / f"{s}.csv") for s in ("study1", "study2")}
    config = tmp_path / "pilot_v2.yaml"
    config.write_text(yaml.safe_dump(cfg))
    common = ["--repo", str(REPO), "--config", str(config), "--backend", "dryrun", "--smoke"]

    with pytest.raises(SystemExit, match="screen the candidate"):  # no questions picked yet
        run.main([*common, "--model", "qwen3-32b"])

    screen.main([*common, "--model", "qwen3-32b"])
    screen.main([*common, "--model", "r1-distill-qwen-1.5b"])
    rows = run.read_records(tmp_path / "screen_smoke" / "raw" / "qwen3-32b" / "study1")
    # smoke: 2 questions x 2 levels x 2 answers
    assert len(rows) == 8 and {r["thinking_level"] for r in rows} == {"off", "low"}

    select_items.main(["--repo", str(REPO), "--config", str(config), "--smoke"])
    report = (tmp_path / "results_screen_smoke" / "screening.md").read_text()
    assert "Picked questions" in report and "Smoke test" in report
    for study in ("study1", "study2"):
        assert len(load_items(picked / f"{study}.csv")) == 2

    run.main([*common, "--model", "qwen3-32b"])
    res = analysis.analyse(tmp_path / "pilot_smoke", tmp_path / "results_pilot")
    assert not res["study2_adjustment"].empty
    assert "median over questions" in (tmp_path / "results_pilot" / "summary.md").read_text()


def test_study1_only_run(tmp_path):
    out = tmp_path / "data"
    args = ["--repo", str(REPO), "--model", "qwen3-8b", "--backend", "dryrun", "--smoke", "--output-dir", str(out)]
    run.main([*args, "--phase", "study1,baseline,anchors"])  # any order; run in dependency order
    raw = out / "raw" / "qwen3-8b"
    assert (raw / "study1").is_dir() and not (raw / "study2").exists()
    res = analysis.analyse(out, tmp_path / "results")  # the analysis copes with no Study 2 data
    assert res["study2_adjustment"].empty and not res["anchoring_index"].empty
    with pytest.raises(SystemExit, match="Unknown phase"):
        run.main([*args, "--phase", "study3"])
