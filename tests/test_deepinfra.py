"""The DeepInfra backend, with a fake tokenizer and a fake API (no network)."""

import json

import pytest

from anchoring_llms import backends, run
from anchoring_llms.backends import (FORCED_CLOSE, THINK_CLOSE, DeepInfraBackend, Request,
                                     SpendLimitReached)


class FakeTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
        return f"<|im_start|>user\n{messages[0]['content']}<|im_end|>\n<|im_start|>assistant\n"

    def encode(self, text, add_special_tokens=False):
        return text.split()


class FakeAPI:
    """Thinks for 100 tokens; stops by itself if the budget allows, else is cut off."""

    def __init__(self, leak_stop=False):
        self.calls = []
        self.leak_stop = leak_stop

    def __call__(self, payload):
        self.calls.append(payload)
        if "stop" in payload:  # thinking
            done = payload["max_tokens"] >= 100
            text = "I recall about 900." + ("\n</think>\n\nEstimate: 1" if self.leak_stop else "")
            choice = {"text": text, "finish_reason": "stop" if done else "length"}
            used = 100 if done else payload["max_tokens"]
        else:  # answer
            choice = {"text": "So my answer.\nEstimate: 900", "finish_reason": "stop"}
            used = 6
        return {"choices": [choice],
                "usage": {"prompt_tokens": 50, "completion_tokens": used, "estimated_cost": 0.001}}


def make(api, tmp_path, max_spend=10.0):
    return DeepInfraBackend(hf_id="x", api_model="Qwen/Qwen3-32B", api_key=None, price_in=0.08,
                            price_out=0.28, max_spend_usd=max_spend,
                            spend_path=tmp_path / "spend.json", workers=4,
                            tokenizer=FakeTokenizer(), post=api)


def test_budget_forcing_and_spend(tmp_path):
    api = FakeAPI()
    be = make(api, tmp_path)
    out = be.generate([Request("off", "Q?", 0, 2, 1), Request("low", "Q?", 512, 2, 1),
                       Request("tiny", "Q?", 50, 1, 1)])
    off, low, tiny = out
    # thinking off: one answer call per sample, after an empty thinking block
    assert [c.thinking_tokens for c in off] == [0, 0]
    assert off[0].answer.endswith("Estimate: 900") and off[0].thinking == ""
    # thinking on: the thinking call stops at </think>, then the answer follows a closed block
    assert low[0].thinking == "I recall about 900." and low[0].thinking_tokens == 100
    assert not low[0].thinking_truncated
    # budget too small: thinking is cut off and the model is told to answer
    assert tiny[0].thinking_truncated and tiny[0].thinking_tokens == 50
    answer_prompts = [c["prompt"] for c in api.calls if "stop" not in c]
    assert sum(p.endswith(FORCED_CLOSE) for p in answer_prompts) == 1
    assert sum(p.endswith("<think>\n" + THINK_CLOSE) for p in answer_prompts) == 2
    assert len(api.calls) == 2 + 2 * 2 + 2 * 1
    # cost is counted per call and saved
    assert be.spent == pytest.approx(0.008)
    assert json.loads((tmp_path / "spend.json").read_text())["spent_usd"] == pytest.approx(0.008)


def test_text_after_a_missed_stop_is_cut(tmp_path):
    be = make(FakeAPI(leak_stop=True), tmp_path)
    c = be.generate([Request("a", "Q?", 512, 1, 1)])[0][0]
    assert c.thinking == "I recall about 900." and c.thinking_tokens == 4


def test_spending_limit_stops_before_the_batch(tmp_path):
    (tmp_path / "spend.json").write_text(json.dumps({"spent_usd": 4.995}))
    api = FakeAPI()
    be = make(api, tmp_path, max_spend=5.0)
    assert be.spent == pytest.approx(4.995)  # carried over from an earlier session
    # worst case for this batch: 10 samples x (2048 + 512) output tokens = about $0.0072
    with pytest.raises(SpendLimitReached):
        be.generate([Request("a", "Q?", 2048, 10, 1)])
    assert api.calls == []


def test_runner_stops_cleanly_at_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(backends, "load_tokenizer", lambda hf_id: FakeTokenizer())
    monkeypatch.setattr(DeepInfraBackend, "_http_post", lambda self, payload: FakeAPI()(payload))
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")
    out = tmp_path / "data"
    args = ["--repo", str(run.Path(__file__).resolve().parents[1]), "--model", "qwen3-32b",
            "--smoke", "--output-dir", str(out)]
    run.main([*args, "--phase", "baseline"])  # the smoke baseline costs a few fake calls
    spent = json.loads((out / "runs" / "qwen3-32b.spend.json").read_text())["spent_usd"]
    assert spent > 0
    rows = run.read_records(out / "raw" / "qwen3-32b" / "baseline")
    assert rows and {r["backend"] for r in rows} == {"deepinfra"}
    with pytest.raises(SystemExit, match="limit"):
        run.main([*args, "--phase", "study2", "--max-spend", str(spent)])
