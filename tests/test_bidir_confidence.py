"""Candidate-probability confidence (pure parts; the model part needs a GPU)."""

import json

import numpy as np
import pandas as pd

from anchoring_llms.bidirectional import confidence as C
from anchoring_llms.bidirectional.trials import load_config


def test_grid_is_fixed_per_statistic():
    g = C.candidate_grid([20, 35, 60])
    assert len(g) >= 10 and g == sorted(g) and g[0] >= 10 and g[-1] <= 90
    assert all(float(x).is_integer() for x in g)


def test_softmax_and_summary():
    p = C.softmax([0.0, 0.0, 0.0, 0.0])
    assert np.allclose(p, 0.25)
    s = C.summary(p, [1, 2, 3, 4])
    assert abs(s["entropy_norm"] - 1) < 1e-9 and abs(s["certainty"] - 0.25) < 1e-9
    assert C.tvd([1, 0], [0, 1]) == 1.0


class FakeScorer:
    """Prefers candidates close to 30, more so without a partner named."""

    def prompt_text(self, msgs):
        return json.dumps(msgs)

    def reply(self, msgs):
        return "MORE"

    def scores(self, prefix, conts):
        vals = [float(c.split(": ")[1].replace(",", "")) for c in conts]
        sharp = 1.0 if "both" in prefix or "MORE" in prefix else 4.0
        return [-sharp * abs(np.log(v / 30)) for v in vals]


def test_score_all_and_shifts():
    cfg = load_config("configs/bidirectional.yaml")
    ents = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    ents["value"] = pd.to_numeric(ents["value"], errors="coerce")
    pairs = pd.read_csv(cfg["paths"]["verified_pairs"], keep_default_na=False)
    pairs = pairs[pairs["dataset"] == "wc2026"].head(2)
    scored = C.score_all(FakeScorer(), cfg, ents, pairs, progress=lambda s: None)
    assert set(scored["condition"]) == {"B", "C1", "C3", "LT", "LA", "HT", "HA"}
    sh = C.shifts(scored)
    assert (sh["tvd"] >= 0).all() and (sh["tvd"] <= 1).all()
    assert len(sh) == 2 * 2 * 2 * 3  # pairs x roles x orders x (C1, C3, comparison)
