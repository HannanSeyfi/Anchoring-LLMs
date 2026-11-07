"""Generate every trial (one fresh conversation each) for a phase.

Conditions (Young et al., 2026, Exp. 1 naming; "target" = the entity whose value is asked):

    B    one turn: estimate the entity (no other entity named)                      per entity
    B2   two turns: "Have you heard of X?", then estimate X (C5, length-matched)     per entity
    LT   compare low vs high (low named first), then estimate the low entity        per pair
    LA   compare high vs low (high named first), then estimate the low entity
    HT   compare high vs low (high named first), then estimate the high entity
    HA   compare low vs high (low named first), then estimate the high entity
    C1   one turn: both named ("X and Y both played ..."), then estimate             both orders
    C2   two turns: compare the letters of the two names, then estimate             both orders
    C3   one turn: the comparison is shown but must not be answered; estimate       both orders
    C4   two turns: "higher or lower than <partner's true value>?", then estimate    (numeric phase)
    TRI  two turns: compare the middle entity with the low or high one, then estimate one of them

Template P1 or P2 alternates over repetitions and orders, so both are used equally often.
Trial ids are a hash of everything that defines the trial, so they are the same on every machine
and a rerun skips trials already answered. No trial contains a true value (except C4's anchor).

    python -m anchoring_llms.bidirectional.trials --phase screen
    python -m anchoring_llms.bidirectional.trials --phase core      # needs frozen_dataset/
    python -m anchoring_llms.bidirectional.trials --phase bank      # every condition, every pair, once
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import yaml

from . import prompts as P

def _forced(cfg: Mapping) -> bool:
    """Design bidir-v2 and later: the turn-1 comparison has no UNSURE option."""
    return bool(cfg.get("conditions", {}).get("forced_choice", False))


def _reverse(cfg: Mapping, rep: int, reps: int) -> bool:
    """`conditions.option_order: balanced` (bidir-v3, bidir-kp2): the second half of the repetitions
    offers the answer words the other way round ("FEWER or MORE"). Templates still alternate within
    each half, so template and option order are crossed."""
    if cfg.get("conditions", {}).get("option_order") != "balanced":
        return False
    return 2 * rep >= reps


def _options_extra(cfg: Mapping, rev: bool) -> dict | None:
    if cfg.get("conditions", {}).get("option_order") != "balanced":
        return None
    return {"options_reversed": bool(rev)}


PHASES = ["screen", "core", "confirmatory", "numeric", "triplets", "bank"]
TWO_TURN = {"B2", "LT", "LA", "HT", "HA", "C2", "C4", "TRI"}


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["thinking_levels"] = {("off" if k is False else str(k)): int(v) for k, v in cfg["thinking_levels"].items()}
    if cfg.get("thinking_level") is False:
        cfg["thinking_level"] = "off"
    return cfg


def trial_id(*parts) -> str:
    key = "|".join(str(p) for p in parts)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def seed_of(tid: str, base: int) -> int:
    return (int(tid[:8], 16) + base) % (2 ** 31 - 1)


def _trial(cfg: dict, phase: str, condition: str, target: Mapping, partner: Mapping | None,
           turns: list[str], rep: int, *, pair_id: str = "", role: str = "", order: str = "",
           template: str = "", expected: int = 0, anchor_value=None, split: str = "",
           extra: dict | None = None) -> dict:
    tid = trial_id(cfg["design_version"], phase, condition,
                   target["entity_id"], partner["entity_id"] if partner is not None else "", order,
                   template, rep, pair_id)
    t = dict(
        trial_id=f"{condition}-{tid}", design_version=cfg["design_version"], phase=phase,
        condition=condition, n_turns=len(turns), pair_id=pair_id, split=split,
        dataset=target["dataset"], domain=target["domain"], metric=target["metric"],
        scope=target["scope"], unit=target["unit"], role=role,
        target_entity_id=target["entity_id"], target_label=target["entity_label"],
        partner_entity_id=partner["entity_id"] if partner is not None else "",
        partner_label=partner["entity_label"] if partner is not None else "",
        order=order, template_id=template, expected_direction=expected,
        anchor_value=anchor_value, repetition=rep, seed=seed_of(tid, cfg["sampling"]["seed"]),
        system=cfg["conditions"]["system_prompt"], turns=turns)
    if extra:
        t.update(extra)
    return t


def entity_trials(cfg: dict, phase: str, ents: Mapping[str, Mapping], ids: Iterable[str],
                  reps_b: int, reps_b2: int) -> list[dict]:
    out = []
    for eid in sorted(set(ids)):
        e = ents[eid]
        for r in range(reps_b):
            out.append(_trial(cfg, phase, "B", e, None, [P.estimate_prompt(e)], r))
        for r in range(reps_b2):
            out.append(_trial(cfg, phase, "B2", e, None, [P.neutral_turn(e), P.estimate_prompt(e)], r))
    return out


def pair_trials(cfg: dict, phase: str, pair: Mapping, ents: Mapping[str, Mapping], reps: int,
                controls: Iterable[str], split: str = "") -> list[dict]:
    lo, hi = ents[pair["low_entity_id"]], ents[pair["high_entity_id"]]
    pid = pair["pair_id"]
    out = []
    for r in range(reps):
        # Core: (condition, target, partner, who is named first, expected shift of the target)
        for k, (cond, t, o, t_first, exp) in enumerate([
                ("LT", lo, hi, True, +1), ("LA", lo, hi, False, +1),
                ("HT", hi, lo, True, -1), ("HA", hi, lo, False, -1)]):
            first, second = (t, o) if t_first else (o, t)
            # LT and HA ask the very same comparison (low named first), as do LA and HT
            tpl = P.TEMPLATES[(r + (0 if first is lo else 1)) % 2]
            rev = _reverse(cfg, r, reps)
            turns = [P.comparison_prompt(first, second, tpl, _forced(cfg), rev), P.estimate_prompt(t)]
            out.append(_trial(cfg, phase, cond, t, o, turns, r, pair_id=pid,
                              role="low" if t is lo else "high",
                              order="target_first" if t_first else "target_second",
                              template=tpl, expected=exp, split=split, extra=_options_extra(cfg, rev)))
        for t, o, exp in ((lo, hi, +1), (hi, lo, -1)):
            role = "low" if t is lo else "high"
            for t_first in (True, False):
                order = "target_first" if t_first else "target_second"
                first, second = (t, o) if t_first else (o, t)
                tpl = P.TEMPLATES[(r + (0 if first is lo else 1)) % 2]
                if "C1" in controls:
                    out.append(_trial(cfg, phase, "C1", t, o, [P.comention_prompt(t, first, second)], r,
                                      pair_id=pid, role=role, order=order, expected=exp, split=split))
                if "C2" in controls:
                    out.append(_trial(cfg, phase, "C2", t, o, [P.letters_turn(first, second), P.estimate_prompt(t)],
                                      r, pair_id=pid, role=role, order=order, expected=exp, split=split))
                if "C3" in controls:
                    out.append(_trial(cfg, phase, "C3", t, o, [P.no_commitment_prompt(t, o, t_first, tpl)], r,
                                      pair_id=pid, role=role, order=order, template=tpl, expected=exp,
                                      split=split))
    return out


def numeric_trials(cfg: dict, pair: Mapping, ents: Mapping[str, Mapping], reps: int, split: str) -> list[dict]:
    lo, hi = ents[pair["low_entity_id"]], ents[pair["high_entity_id"]]
    out = []
    for r in range(reps):
        for t, o, exp in ((lo, hi, +1), (hi, lo, -1)):
            anchor = float(o["value"])
            turns = [P.numeric_turn(t, P.format_anchor(anchor), _forced(cfg)), P.estimate_prompt(t)]
            out.append(_trial(cfg, "numeric", "C4", t, o, turns, r, pair_id=pair["pair_id"],
                              role="low" if t is lo else "high", expected=exp, anchor_value=anchor,
                              split=split, extra={"anchor_source": "partner_true_value"}))
    return out


def triplet_trials(cfg: dict, tri: Mapping, ents: Mapping[str, Mapping], reps: int) -> list[dict]:
    lo, mid, hi = (ents[tri[k]] for k in ("low_entity_id", "mid_entity_id", "high_entity_id"))
    out = []
    for r in range(reps):
        for t, o, role, exp in ((mid, lo, "mid_vs_low", -1), (mid, hi, "mid_vs_high", +1),
                                (lo, mid, "low_vs_mid", +1), (hi, mid, "high_vs_mid", -1)):
            for t_first in (True, False):
                first, second = (t, o) if t_first else (o, t)
                tpl = P.TEMPLATES[(r + (0 if float(first["value"]) < float(second["value"]) else 1)) % 2]
                rev = _reverse(cfg, r, reps)
                turns = [P.comparison_prompt(first, second, tpl, _forced(cfg), rev), P.estimate_prompt(t)]
                out.append(_trial(cfg, "triplets", "TRI", t, o, turns, r, pair_id=tri["triplet_id"],
                                  role=role, order="target_first" if t_first else "target_second",
                                  template=tpl, expected=exp, extra=_options_extra(cfg, rev)))
    return out


def frozen_path(cfg: dict) -> Path:
    return Path(cfg["paths"]["frozen_dir"]) / "pairs_frozen.csv"


def _unknown_only(cfg: dict, trials: list[dict], pairs: pd.DataFrame) -> list[dict]:
    """bidir-kp2 (`conditions.targets: unknown_only`): drop pair trials whose target is the famous item.

    Baselines (B, B2) are kept for every entity."""
    if cfg["conditions"].get("targets") != "unknown_only" or "known_entity_id" not in pairs:
        return trials
    known = dict(zip(pairs["pair_id"], pairs["known_entity_id"]))
    return [t for t in trials if not (t.get("pair_id") and known.get(t["pair_id"]) == t["target_entity_id"])]


def generate(cfg: dict, phase: str) -> list[dict]:
    paths = cfg["paths"]
    ents_df = pd.read_csv(paths["entities"], keep_default_na=False)
    ents = {r["entity_id"]: r for r in ents_df.to_dict("records")}
    cond = cfg["conditions"]
    controls = cond["controls"]
    if phase in ("screen", "bank"):
        pairs = pd.read_csv(paths["verified_pairs"], keep_default_na=False)
        tri = pd.read_csv(paths["triplets"], keep_default_na=False)
        ids = list(pairs["low_entity_id"]) + list(pairs["high_entity_id"])
        for k in ("low_entity_id", "mid_entity_id", "high_entity_id"):
            ids += list(tri[k])
        if phase == "screen":
            return entity_trials(cfg, "screen", ents, ids, cfg["screening"]["samples"], 0)
        out = entity_trials(cfg, "bank", ents, ids, 1, 1)
        for p in pairs.to_dict("records"):
            out += pair_trials(cfg, "bank", p, ents, 1, controls)
            if p["dataset"] != "young":
                out += numeric_trials(cfg, p, ents, 1, "")
        for t in tri.to_dict("records"):
            out += triplet_trials(cfg, t, ents, 1)
        for t in out:
            t["phase"] = "bank"
        return _unknown_only(cfg, out, pairs)
    fp = frozen_path(cfg)
    if not fp.exists():
        raise SystemExit(f"{fp} does not exist yet. Run the screening and "
                         "`python -m anchoring_llms.bidirectional.screen` first.")
    frozen = pd.read_csv(fp, keep_default_na=False)
    if phase == "triplets":
        tri = pd.read_csv(Path(paths["frozen_dir"]) / "triplets_frozen.csv", keep_default_na=False)
        reps = cfg["triplet_conditions"]["repetitions"]
        ids = [i for k in ("low_entity_id", "mid_entity_id", "high_entity_id") for i in tri[k]]
        out = entity_trials(cfg, "triplets", ents, ids, cfg["conditions"]["baseline_repetitions"], 0)
        for t in tri.to_dict("records"):
            out += triplet_trials(cfg, t, ents, reps)
        return out
    splits = {"core": ("pilot", "robustness"), "numeric": ("pilot",), "confirmatory": ("confirmatory",)}[phase]
    sel = frozen[frozen["split"].isin(splits)]
    if phase == "numeric":
        out = []
        for p in sel.to_dict("records"):
            if p["dataset"] != "young":       # no true value to use as an anchor
                out += numeric_trials(cfg, p, ents, cfg["numeric"]["repetitions"], p["split"])
        return _unknown_only(cfg, out, sel)
    ids = list(sel["low_entity_id"]) + list(sel["high_entity_id"])
    out = entity_trials(cfg, phase, ents, ids, cond["baseline_repetitions"], cond["repetitions"])
    for p in sel.to_dict("records"):
        out += pair_trials(cfg, phase, p, ents, cond["repetitions"], controls, p["split"])
    return _unknown_only(cfg, out, sel)


def write_trials(trials: list[dict], out_dir: Path, phase: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{phase}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for t in trials:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    flat = pd.DataFrame([{**{k: v for k, v in t.items() if k != "turns"},
                          "turn_1": t["turns"][0], "turn_2": t["turns"][1] if len(t["turns"]) > 1 else ""}
                         for t in trials])
    flat.to_csv(out_dir / f"{phase}.csv", index=False)
    return path


def load_trials(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--phase", required=True, choices=PHASES)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    trials = generate(cfg, a.phase)
    from .validate import validate_trials
    problems = validate_trials(trials, cfg)
    if problems:
        raise SystemExit("Trial checks failed:\n" + "\n".join(problems[:20]))
    path = write_trials(trials, Path(cfg["paths"]["trials_dir"]), a.phase)
    counts = pd.Series([t["condition"] for t in trials]).value_counts()
    calls = sum(t["n_turns"] for t in trials)
    print(f"{len(trials)} trials ({calls} model calls) -> {path}")
    print(counts.to_string())


if __name__ == "__main__":
    main()
