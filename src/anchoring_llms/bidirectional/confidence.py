"""Confidence from candidate-answer probabilities (open-weight models, Colab GPU).

Following Owusu & Feldman (2026, ACL short): for each question, a fixed set of candidate
answers is scored by the model; each candidate's score is its length-normalised
log-likelihood (mean log-probability of its tokens), and a softmax over the candidates gives a
distribution. Certainty = the largest probability; we also keep the normalised entropy and the
expected log value. The same candidates are scored after a co-mention (C1), a comparison shown
but not answered (C3), and the full two-turn comparison (LT/LA/HT/HA, with the model's own greedy
turn-1 reply), so the shift of the distribution (total variation distance, and the move of the
expected value towards the other entity) can be related to certainty.

Candidate grid. For each statistic (dataset, domain, metric, scope): 12 values evenly spaced on
a log scale from half the smallest to 1.5 times the largest true value of *all* entities of that
statistic, rounded to 2 significant figures. The grid is the same for every entity of the
statistic and does not depend on any single entity's value. These normalised probabilities are
not the model's full belief over all numbers; they are a comparison on a fixed set.

The answer is scored as the text "Estimate: <value>" right after the closed thinking block,
which is the format every prompt asks for.

    python -m anchoring_llms.bidirectional.confidence --model qwen3-4b      # on a GPU
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from . import prompts as P
from .trials import load_config

N_CANDIDATES = 12


def round_sig(x: float, sig: int = 2) -> float:
    if x <= 0:
        return 0.0
    return float(round(x, sig - 1 - int(math.floor(math.log10(abs(x))))))


def candidate_grid(values: Sequence[float], n: int = N_CANDIDATES, integer: bool = True) -> list[float]:
    v = [float(x) for x in values if float(x) > 0]
    lo, hi = max(min(v) * 0.5, 1.0 if integer else 1e-3), max(v) * 1.5
    grid = [round_sig(x) for x in np.exp(np.linspace(math.log(lo), math.log(hi), n))]
    if integer:
        grid = [float(max(1, int(round(g)))) for g in grid]
    out = []
    for g in grid:
        if g not in out:
            out.append(g)
    return out


def grids(entities: pd.DataFrame) -> dict[tuple, list[float]]:
    out = {}
    for key, g in entities.groupby(["dataset", "domain", "metric", "scope"]):
        integer = str(g["integer"].iloc[0]) == "True"
        if key[0] == "young":
            out[key] = candidate_grid([1, 10000], integer=False)
        else:
            out[key] = candidate_grid(g["value"].astype(float), integer=integer)
    return out


def softmax(scores: Sequence[float]) -> np.ndarray:
    s = np.asarray(scores, float)
    e = np.exp(s - s.max())
    return e / e.sum()


def summary(probs: np.ndarray, grid: Sequence[float]) -> dict:
    p = np.asarray(probs, float)
    ent = float(-(p * np.log(np.clip(p, 1e-300, None))).sum())
    return dict(certainty=float(p.max()), entropy_norm=ent / math.log(len(p)) if len(p) > 1 else 0.0,
                expected_log1p=float((p * np.log1p(np.asarray(grid, float))).sum()),
                mode=float(grid[int(p.argmax())]))


def tvd(p: Sequence[float], q: Sequence[float]) -> float:
    return float(0.5 * np.abs(np.asarray(p) - np.asarray(q)).sum())


def format_candidate(v: float) -> str:
    return f"Estimate: {P.format_anchor(v)}"


# ----------------------------------------------------------------------------- model side (torch)

class HFScorer:
    """Length-normalised log-likelihood of candidate continuations, with transformers."""

    def __init__(self, hf_id: str, dtype: str = "float16"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(hf_id)
        self.model = AutoModelForCausalLM.from_pretrained(hf_id, torch_dtype=getattr(torch, dtype), device_map="auto")
        self.model.eval()

    def prompt_text(self, msgs: list[dict]) -> str:
        return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)

    def reply(self, msgs: list[dict], max_new_tokens: int = 12) -> str:
        ids = self.tok(self.prompt_text(msgs), return_tensors="pt", add_special_tokens=False).to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
        return self.tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    def scores(self, prefix: str, continuations: list[str]) -> list[float]:
        torch = self.torch
        pre = self.tok(prefix, add_special_tokens=False)["input_ids"]
        seqs = [pre + self.tok(c, add_special_tokens=False)["input_ids"] for c in continuations]
        L = max(map(len, seqs))
        pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0
        ids = torch.full((len(seqs), L), pad, dtype=torch.long)
        mask = torch.zeros((len(seqs), L), dtype=torch.long)
        for i, s in enumerate(seqs):
            ids[i, :len(s)] = torch.tensor(s)
            mask[i, :len(s)] = 1
        ids, mask = ids.to(self.model.device), mask.to(self.model.device)
        with torch.no_grad():
            logp = torch.log_softmax(self.model(input_ids=ids, attention_mask=mask).logits.float(), -1)
        out = []
        for i, s in enumerate(seqs):
            pos = range(len(pre), len(s))
            lp = [float(logp[i, j - 1, s[j]]) for j in pos]
            out.append(sum(lp) / max(1, len(lp)))
        return out


# ----------------------------------------------------------------------------- driver

def jobs(cfg: dict, entities: pd.DataFrame, frozen: pd.DataFrame) -> list[dict]:
    """Every prompt to score: the baseline of each entity, then C1, C3 and the comparison per pair."""
    ents = {r["entity_id"]: r for r in entities.to_dict("records")}
    out = []
    sysmsg = cfg["conditions"]["system_prompt"]
    ids = sorted(set(frozen["low_entity_id"]) | set(frozen["high_entity_id"]))
    for eid in ids:
        out.append(dict(condition="B", pair_id="", role="", order="", target=eid, partner="",
                        msgs=[{"role": "system", "content": sysmsg}, {"role": "user", "content": P.estimate_prompt(ents[eid])}]))
    for p in frozen.to_dict("records"):
        lo, hi = ents[p["low_entity_id"]], ents[p["high_entity_id"]]
        for t, o, role in ((lo, hi, "low"), (hi, lo, "high")):
            for t_first in (True, False):
                first, second = (t, o) if t_first else (o, t)
                order = "target_first" if t_first else "target_second"
                base = dict(pair_id=p["pair_id"], role=role, order=order, target=t["entity_id"], partner=o["entity_id"])
                out.append(dict(base, condition="C1", msgs=[{"role": "system", "content": sysmsg},
                                {"role": "user", "content": P.comention_prompt(t, first, second)}]))
                out.append(dict(base, condition="C3", msgs=[{"role": "system", "content": sysmsg},
                                {"role": "user", "content": P.no_commitment_prompt(t, o, t_first, "P1")}]))
                cond = {("low", True): "LT", ("low", False): "LA", ("high", True): "HT", ("high", False): "HA"}[(role, t_first)]
                out.append(dict(base, condition=cond, two_turn=True,
                                turn1=P.comparison_prompt(first, second, "P1"), turn2=P.estimate_prompt(t),
                                msgs=[{"role": "system", "content": sysmsg}]))
    return out


def score_all(scorer, cfg: dict, entities: pd.DataFrame, frozen: pd.DataFrame,
              progress: Callable[[str], None] = print) -> pd.DataFrame:
    g = grids(entities)
    ents = entities.set_index("entity_id")
    rows = []
    js = jobs(cfg, entities, frozen)
    for k, j in enumerate(js):
        e = ents.loc[j["target"]]
        grid = g[(e["dataset"], e["domain"], e["metric"], e["scope"])]
        msgs = list(j["msgs"])
        turn1_reply = ""
        if j.get("two_turn"):
            msgs = msgs + [{"role": "user", "content": j["turn1"]}]
            turn1_reply = scorer.reply(msgs)
            msgs = msgs + [{"role": "assistant", "content": turn1_reply}, {"role": "user", "content": j["turn2"]}]
        s = scorer.scores(scorer.prompt_text(msgs), [format_candidate(v) for v in grid])
        p = softmax(s)
        rows.append(dict(condition=j["condition"], pair_id=j["pair_id"], role=j["role"], order=j["order"],
                         entity_id=j["target"], partner_id=j["partner"], turn1_reply=turn1_reply,
                         grid=json.dumps(grid), scores=json.dumps([round(x, 5) for x in s]),
                         probs=json.dumps([round(float(x), 6) for x in p]), **summary(p, grid)))
        if k % 50 == 0:
            progress(f"  scored {k + 1}/{len(js)}")
    return pd.DataFrame(rows)


def shifts(scored: pd.DataFrame) -> pd.DataFrame:
    """Per pair, role and condition: TVD from the baseline and signed move of the expected value."""
    base = scored[scored["condition"] == "B"].set_index("entity_id")
    rows = []
    for r in scored[scored["condition"] != "B"].to_dict("records"):
        b = base.loc[r["entity_id"]]
        sign = 1 if r["role"] == "low" else -1
        rows.append(dict(pair_id=r["pair_id"], role=r["role"], order=r["order"], condition=r["condition"],
                         entity_id=r["entity_id"], baseline_certainty=b["certainty"],
                         baseline_entropy=b["entropy_norm"],
                         tvd=tvd(json.loads(r["probs"]), json.loads(b["probs"])),
                         assim_expected_log1p=sign * (r["expected_log1p"] - b["expected_log1p"])))
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--model", default="qwen3-4b")
    ap.add_argument("--split", default="pilot")
    ap.add_argument("--limit", type=int, default=None, help="score only the first N pairs (smoke test)")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    ents = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    ents["value"] = pd.to_numeric(ents["value"], errors="coerce")
    frozen = pd.read_csv(Path(cfg["paths"]["frozen_dir"]) / "pairs_frozen.csv", keep_default_na=False)
    frozen = frozen[frozen["split"] == a.split]
    if a.limit:
        frozen = frozen.head(a.limit)
    mcfg = cfg["models"][a.model]
    scorer = HFScorer(mcfg["hf_id"], mcfg.get("dtype", "float16"))
    scored = score_all(scorer, cfg, ents, frozen)
    out = Path(cfg["paths"]["results_dir"]) / "confidence" / a.model / ("smoke" if a.limit else a.split)
    out.mkdir(parents=True, exist_ok=True)
    scored.to_csv(out / "candidate_scores.csv", index=False)
    sh = shifts(scored)
    sh.to_csv(out / "shifts.csv", index=False)
    summ = sh.groupby(["condition", "role"]).agg(n=("tvd", "size"), tvd=("tvd", "mean"),
                                                 assim=("assim_expected_log1p", "mean")).reset_index()
    summ.to_csv(out / "summary.csv", index=False)
    corr = sh.groupby("condition").apply(lambda g: g["baseline_certainty"].corr(g["tvd"]), include_groups=False)
    print(summ.to_string(index=False))
    print("Correlation of baseline certainty with TVD, by condition:\n", corr.to_string())
    print(f"-> {out}")


if __name__ == "__main__":
    main()
