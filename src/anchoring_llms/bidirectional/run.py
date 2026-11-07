"""Run one phase of the bidirectional study on one model.

    python -m anchoring_llms.bidirectional.run --phase screen --model qwen3-32b --sync
    python -m anchoring_llms.bidirectional.run --phase core --model qwen3-32b --max-spend 5 --sync
    python -m anchoring_llms.bidirectional.run --phase core --model qwen3-32b --smoke   # 2 pairs, 2 repetitions
    python -m anchoring_llms.bidirectional.run --phase core --backend simulated          # no model: pipeline test

Every trial is its own fresh conversation. A two-turn trial sends turn 1, keeps the model's
reply exactly as given (never corrected), and sends turn 2 with that reply in the history.
Nothing from any other trial is ever in the context. Replies are saved raw, before parsing, to
runs/<phase>/<model>/<level>/part-*.jsonl.gz, after every batch; a rerun skips saved trials.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import pandas as pd

from ..backends import Request, SpendLimitReached, make_backend
from ..git_sync import GitSync
from .responses import comparison_correct, read_estimate, read_turn1
from .simulate import SimBackend
from .trials import load_config, load_trials


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""


def out_dir(cfg: dict, phase: str, model: str, level: str, smoke: bool) -> Path:
    base = Path(cfg["paths"]["runs_dir"] + ("_smoke" if smoke else ""))
    return base / phase / model / level


def done_ids(folder: Path) -> set[str]:
    ids = set()
    for f in sorted(folder.glob("part-*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    ids.add(json.loads(line)["trial_id"])
    return ids


def load_records(folder: Path) -> list[dict]:
    recs = []
    for f in sorted(Path(folder).glob("part-*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            recs += [json.loads(line) for line in fh if line.strip()]
    return recs


def smoke_subset(trials: list[dict], n_pairs: int = 2, reps: int = 2) -> list[dict]:
    pairs = []
    for t in trials:
        if t["pair_id"] and t["pair_id"] not in pairs:
            pairs.append(t["pair_id"])
    keep_pairs = set(pairs[:n_pairs])
    ents = {t["target_entity_id"] for t in trials if t["pair_id"] in keep_pairs}
    if not keep_pairs:  # screening: entity trials only
        ents = set(sorted({t["target_entity_id"] for t in trials})[:4])
    return [t for t in trials if t["repetition"] < reps and
            (t["pair_id"] in keep_pairs or (not t["pair_id"] and t["target_entity_id"] in ents))]


def messages(system: str, turns: list[str], replies: list[str]) -> list[dict]:
    msgs = [{"role": "system", "content": system}] if system else []
    for i, u in enumerate(turns):
        msgs.append({"role": "user", "content": u})
        if i < len(replies):
            msgs.append({"role": "assistant", "content": replies[i]})
    return msgs


def run_batch(backend, trials: list[dict], budget: int, truths: dict) -> list[dict]:
    """Turn 1 for every trial, then turn 2 for the two-turn trials, each with its own history."""
    def meta(t, turn):
        m = {k: t[k] for k in ("condition", "role", "order", "target_entity_id", "partner_entity_id", "n_turns")}
        m.update(turn=turn, anchor_value=t.get("anchor_value"), options_reversed=bool(t.get("options_reversed", False)),
                 truth_target=truths.get(t["target_entity_id"]),
                 truth_partner=truths.get(t["partner_entity_id"]))
        return m

    t0 = time.time()
    first = [Request(cell_id=f"{t['trial_id']}#1", prompt=messages(t["system"], t["turns"][:1], []),
                     budget=budget, n=1, seed=t["seed"], meta=meta(t, 1)) for t in trials]
    c1 = [c[0] for c in backend.generate(first)]
    two = [i for i, t in enumerate(trials) if t["n_turns"] == 2]
    second = [Request(cell_id=f"{trials[i]['trial_id']}#2",
                      prompt=messages(trials[i]["system"], trials[i]["turns"], [c1[i].answer]),
                      budget=budget, n=1, seed=trials[i]["seed"] + 1, meta=meta(trials[i], 2)) for i in two]
    c2 = dict(zip(two, (c[0] for c in backend.generate(second)))) if second else {}
    latency = (time.time() - t0) / max(1, len(trials))
    recs = []
    for i, t in enumerate(trials):
        a = c1[i]
        b = c2.get(i)
        final = b if b is not None else a
        r = {k: v for k, v in t.items()}
        r.update(
            reply_1=a.answer, thinking_1=a.thinking, thinking_tokens_1=a.thinking_tokens,
            answer_tokens_1=a.answer_tokens, finish_1=a.answer_finish_reason,
            reply_2=b.answer if b else None, thinking_2=b.thinking if b else None,
            thinking_tokens_2=b.thinking_tokens if b else None, answer_tokens_2=b.answer_tokens if b else None,
            finish_2=b.answer_finish_reason if b else None,
            history_2=(messages(t["system"], t["turns"], [a.answer]) if b else None),
            latency_s=round(latency, 3), timestamp=now())
        r.update(read_estimate(final.answer, final.answer_finish_reason, t["unit"]))
        if b is not None:
            r.update(read_turn1(a.answer, t["condition"], a.answer_finish_reason))
            r["turn1_correct"] = comparison_correct(t["condition"], t["order"], t["role"], r["turn1_answer"])
        recs.append(r)
    return recs


def save_part(folder: Path, recs: list[dict]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    n = len(list(folder.glob("part-*.jsonl.gz")))
    path = folder / f"part-{n:04d}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def run(cfg: dict, phase: str, model: str, backend_kind: str | None = None, level: str | None = None,
        smoke: bool = False, sync: bool = False, max_spend: float | None = None, workers: int | None = None,
        pattern: str = "bidirectional", trials: list[dict] | None = None, limit: int | None = None) -> Path:
    level = level or cfg["thinking_level"]
    budget = cfg["thinking_levels"][level]
    if max_spend is not None:
        cfg["api"]["max_spend_usd"] = max_spend
    if workers is not None:
        cfg["api"]["workers"] = workers
    if trials is None:
        tpath = Path(cfg["paths"]["trials_dir"]) / f"{phase}.jsonl"
        if not tpath.exists():
            raise SystemExit(f"{tpath} not found: run `python -m anchoring_llms.bidirectional.trials --phase {phase}` first.")
        trials = load_trials(tpath)
    if smoke:
        trials = smoke_subset(trials)
    if limit:
        trials = trials[:limit]
    simulated = backend_kind == "simulated"
    name = "simulated" if simulated else model
    folder = out_dir(cfg, phase, name, level, smoke or simulated)
    done = done_ids(folder)
    todo = [t for t in trials if t["trial_id"] not in done]
    print(f"{phase} / {name} / thinking {level}: {len(trials)} trials, {len(done)} already saved, {len(todo)} to run.")
    if not todo:
        return folder
    ents = pd.read_csv(cfg["paths"]["entities"], keep_default_na=False)
    truths = dict(zip(ents["entity_id"], ents["value"].astype(float))) if simulated else {}
    if simulated:
        backend = SimBackend(pattern=pattern, seed=cfg["sampling"]["seed"], **cfg.get("simulation", {}))
        mcfg = {"hf_id": "simulated", "backend": "simulated"}
    else:
        mcfg = cfg["models"][model]
        kind = backend_kind or mcfg.get("backend", "vllm")
        spend = folder.parent.parent / f"{model}.spend.json"
        backend = make_backend(kind, mcfg, cfg, spend_path=spend)
    info = dict(model=name, hf_id=mcfg.get("hf_id"), api_model=mcfg.get("api_model"),
                backend=getattr(backend, "name", "?"), provider=mcfg.get("provider"),
                model_release=str(mcfg.get("release", "")), model_cutoff=mcfg.get("cutoff"),
                thinking_level=level, thinking_budget=budget, temperature=cfg["sampling"]["temperature"],
                top_p=cfg["sampling"]["top_p"], answer_max_tokens=cfg["sampling"]["answer_max_tokens"],
                tools="none", retrieval="none", simulated=simulated, code_commit=git_commit(),
                python=platform.python_version())
    syncer = GitSync(".", [str(folder.parent.parent)], enabled=sync,
                     min_interval=cfg["sync"]["min_interval_seconds"])
    size = cfg["run"]["trials_per_batch"]
    n_done = 0
    try:
        for i in range(0, len(todo), size):
            batch = todo[i:i + size]
            recs = run_batch(backend, batch, budget, truths)
            for r in recs:
                r.update(info)
            save_part(folder, recs)
            n_done += len(recs)
            ok = sum(r["parse_status"] == "ok" for r in recs)
            spent = getattr(backend, "spent", None)
            print(f"  saved {n_done}/{len(todo)} ({ok}/{len(recs)} with a number)"
                  + (f", ${spent:.2f} spent" if spent is not None else ""), flush=True)
            syncer.maybe_sync(f"Bidirectional {phase}: {name} {n_done}/{len(todo)}")
    except SpendLimitReached as e:
        print(e)
    finally:
        manifest = Path(cfg["paths"]["runs_dir"] + ("_smoke" if (smoke or simulated) else "")) / "manifest.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest, "a", encoding="utf-8") as f:
            f.write(json.dumps({**info, "phase": phase, "trials_in_phase": len(trials), "saved_now": n_done,
                                "saved_total": len(done) + n_done, "finished": now()}) + "\n")
        syncer.maybe_sync(f"Bidirectional {phase}: {name} done ({len(done) + n_done}/{len(trials)})", force=True)
    return folder


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--phase", required=True, choices=["screen", "core", "confirmatory", "numeric", "triplets"])
    ap.add_argument("--model", default="qwen3-32b")
    ap.add_argument("--backend", default=None, help="deepinfra, openai_chat, vllm or simulated (default: from the config)")
    ap.add_argument("--level", default=None, help="thinking level (default: thinking_level in the config)")
    ap.add_argument("--smoke", action="store_true", help="2 pairs, 2 repetitions, saved to runs_smoke/")
    ap.add_argument("--sync", action="store_true", help="commit and push to GitHub as it goes")
    ap.add_argument("--max-spend", type=float, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--pattern", default="bidirectional", help="simulated backend only")
    ap.add_argument("--limit", type=int, default=None, help="run only the first N trials")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    run(cfg, a.phase, a.model, a.backend, a.level, a.smoke, a.sync, a.max_spend, a.workers, a.pattern, limit=a.limit)


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
