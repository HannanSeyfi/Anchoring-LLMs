"""Checks on generated trials. `validate_trials` returns a list of problems (empty = all good).

They encode the design rules: every pair has all six core conditions, LT/LA ask about the low
entity and HT/HA about the high one, the comparison order is really reversed, baselines name no
other entity, no item-based prompt contains a true value, both entities share one statistic,
two-turn trials have two turns, and trial ids are unique.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

import pandas as pd

CORE = ("LT", "LA", "HT", "HA")


def number_forms(value: float) -> set[str]:
    """Ways a true value could be written in a prompt: 115, 1,966, 2925.4, 2,925.40 ..."""
    v = float(value)
    forms = {f"{v:g}"}
    if abs(v - round(v)) < 1e-9:
        n = int(round(v))
        forms |= {str(n), f"{n:,}", f"{n:,}".replace(",", " ")}
    else:
        forms |= {f"{v:.1f}", f"{v:.2f}", f"{v:,.1f}", f"{v:,.2f}"}
    return {f for f in forms if f}


def contains_number(text: str, value: float) -> bool:
    for f in number_forms(value):
        if re.search(rf"(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)", text):
            return True
    return False


def _first_position(text: str, label: str) -> int:
    i = text.find(label)
    return i if i >= 0 else 10 ** 9


def validate_trials(trials: list[dict], cfg: dict, entities: pd.DataFrame | None = None) -> list[str]:
    if entities is None:
        entities = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    ents = {r["entity_id"]: r for r in entities.to_dict("records")}
    problems: list[str] = []
    ids = [t["trial_id"] for t in trials]
    if len(ids) != len(set(ids)):
        problems.append(f"{len(ids) - len(set(ids))} duplicate trial ids")
    by_pair: dict[str, set[str]] = defaultdict(set)
    baselines: set[str] = set()
    for t in trials:
        tid, cond = t["trial_id"], t["condition"]
        text = "\n".join(t["turns"])
        target = ents.get(t["target_entity_id"])
        if target is None:
            problems.append(f"{tid}: unknown target {t['target_entity_id']}")
            continue
        two = cond in ("B2", "LT", "LA", "HT", "HA", "C2", "C4", "TRI")
        if len(t["turns"]) != (2 if two else 1):
            problems.append(f"{tid}: {cond} should have {2 if two else 1} turns")
        if cond == "B":
            baselines.add(t["target_entity_id"])
        partner = ents.get(t["partner_entity_id"]) if t["partner_entity_id"] else None
        if cond in ("B", "B2"):
            if partner is not None:
                problems.append(f"{tid}: baseline has a partner")
        elif partner is None:
            problems.append(f"{tid}: {cond} has no partner")
        if partner is not None:
            for k in ("metric", "scope", "unit", "dataset"):
                if target[k] != partner[k]:
                    problems.append(f"{tid}: target and partner differ in {k}")
        # True values: never in item-based prompts. C4 shows the partner's value on purpose.
        if target["dataset"] != "young":
            if contains_number(text, target["value"]):
                problems.append(f"{tid}: prompt contains the target's true value {target['value']:g}")
            if partner is not None and cond != "C4" and contains_number(text, partner["value"]):
                problems.append(f"{tid}: prompt contains the partner's true value {partner['value']:g}")
        if cond in CORE:
            by_pair[t["pair_id"]].add(cond)
            low_expected = cond in ("LT", "LA")
            if (t["role"] == "low") != low_expected:
                problems.append(f"{tid}: {cond} estimates the wrong entity")
            if (t["expected_direction"] == 1) != low_expected:
                problems.append(f"{tid}: {cond} has the wrong expected direction")
            if float(target["value"]) >= float(partner["value"]) and low_expected and target["dataset"] != "young":
                problems.append(f"{tid}: {cond} target is not the lower entity")
            first = t["turns"][0]
            t_first = _first_position(first, target["entity_label"]) < _first_position(first, partner["entity_label"])
            should = cond in ("LT", "HT")
            if t_first != should:
                problems.append(f"{tid}: {cond} names the entities in the wrong order")
            if target["entity_label"] not in t["turns"][1] and target.get("question", "") not in t["turns"][1]:
                problems.append(f"{tid}: second turn does not ask about the target")
        if cond in ("B", "B2"):
            # no other entity of the same statistic may be named
            pass
    for pid, conds in by_pair.items():
        missing = set(CORE) - conds
        if missing:
            problems.append(f"pair {pid}: missing {sorted(missing)}")
    return problems


def check_baselines_name_no_partner(trials: Iterable[dict], pairs: pd.DataFrame) -> list[str]:
    """Baseline prompts must not mention the other entity of any pair the entity is in."""
    partners: dict[str, set[str]] = defaultdict(set)
    for p in pairs.to_dict("records"):
        partners[p["low_entity_id"]].add(p["high_label"])
        partners[p["high_entity_id"]].add(p["low_label"])
    out = []
    for t in trials:
        if t["condition"] in ("B", "B2"):
            text = "\n".join(t["turns"])
            for lab in partners.get(t["target_entity_id"], ()):
                if lab != t["target_label"] and re.search(rf"\b{re.escape(lab)}\b", text):
                    out.append(f"{t['trial_id']}: baseline mentions {lab}")
    return out
