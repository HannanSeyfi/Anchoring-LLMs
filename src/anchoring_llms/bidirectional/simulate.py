"""A simulated model, for testing the pipeline and the analysis. Its output is NOT data.

`SimBackend` answers like a model with a fixed (wrong) belief about each entity. After a
comparison its estimate moves towards the other entity by a set share of the log distance, so
tests can check that the analysis finds exactly the pattern that was put in: both directions,
low only, high only, none, or contrast (moving away).

Every simulated record is marked `simulated: true` by the runner and is written only to
`*_smoke` / test folders.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field

from ..backends import Completion, Request

PATTERNS = {
    "bidirectional": dict(low=0.30, high=0.30),
    "low_only": dict(low=0.30, high=0.0),
    "high_only": dict(low=0.0, high=0.30),
    "none": dict(low=0.0, high=0.0),
    "contrast": dict(low=-0.25, high=-0.25),
}


def _h(*parts) -> float:
    return int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) / 2 ** 32


@dataclass
class SimBackend:
    pattern: str = "bidirectional"
    noise: float = 0.15          # sd of log answers
    bias_sd: float = 0.35        # sd of each entity's fixed belief error (log scale)
    comention: float = 0.0       # pull in C1
    no_commitment: float = 0.10  # pull in C3
    numeric: float = 0.45        # pull in C4
    refusal_rate: float = 0.02
    first_word_reflex: float = 0.0  # share of comparisons answered with whichever word is offered first
    seed: int = 0
    name: str = "simulated"
    hf_id: str = "simulated"
    calls: list = field(default_factory=list)

    def belief(self, entity_id: str, truth: float) -> float:
        z = random.Random(f"{self.seed}|belief|{entity_id}").gauss(0, self.bias_sd)
        return max(truth, 0.5) * math.exp(z)

    def generate(self, requests: list[Request]) -> list[list[Completion]]:
        out = []
        for r in requests:
            self.calls.append(r)
            m = r.meta
            rnd = random.Random(f"{self.seed}|{r.cell_id}|{r.seed}")
            comps = []
            for _ in range(r.n):
                if m.get("turn") == 1 and m.get("n_turns") == 2:
                    comps.append(Completion("", self._turn1(m, rnd), 0, 3, False, "stop"))
                    continue
                if rnd.random() < self.refusal_rate:
                    comps.append(Completion("", "I'm sorry, I don't have data on that event.", 0, 10, False, "stop"))
                    continue
                b = self.belief(m["target_entity_id"], m["truth_target"])
                pull = self._pull(m)
                if pull and m.get("truth_partner") is not None:
                    p = (m["anchor_value"] if m["condition"] == "C4" else
                         self.belief(m["partner_entity_id"], m["truth_partner"]))
                    b = b * (max(p, 0.5) / b) ** pull
                est = b * math.exp(rnd.gauss(0, self.noise))
                comps.append(Completion("", f"My best guess.\nEstimate: {max(0, round(est))}", 0, 8, False, "stop"))
            out.append(comps)
        return out

    def _pull(self, m: dict) -> float:
        c = m["condition"]
        if c in ("LT", "LA", "HT", "HA", "TRI"):
            role = m["role"]
            lowish = role in ("low", "low_vs_mid", "mid_vs_high")
            return PATTERNS[self.pattern]["low" if lowish else "high"]
        return {"C1": self.comention, "C3": self.no_commitment, "C4": self.numeric}.get(c, 0.0)

    def _turn1(self, m: dict, rnd: random.Random | None = None) -> str:
        c = m["condition"]
        if c in ("LT", "LA", "HT", "HA", "TRI") and self.first_word_reflex and rnd is not None \
                and rnd.random() < self.first_word_reflex:
            return "FEWER" if m.get("options_reversed") else "MORE"
        if c == "B2":
            return "YES"
        if c == "C2":
            return "MORE" if _h(m["target_entity_id"], m["partner_entity_id"]) > 0.5 else "FEWER"
        if c == "C4":
            b = self.belief(m["target_entity_id"], m["truth_target"])
            return "HIGHER" if b > m["anchor_value"] else "LOWER"
        bt = self.belief(m["target_entity_id"], m["truth_target"])
        bp = self.belief(m["partner_entity_id"], m["truth_partner"])
        first_is_target = m["order"] == "target_first"
        first_higher = (bt > bp) == first_is_target
        return "MORE" if first_higher else "FEWER"
