"""Run the pilot for one model.

Usage (from the repository root):
    python -m anchoring_llms.run --config configs/pilot.yaml --model qwen3-8b --phase all --sync
    python -m anchoring_llms.run --config configs/pilot.yaml --model qwen3-8b --backend dryrun --smoke

Phases run in order: baseline -> anchors -> study1 -> study2. Every phase
resumes where it stopped: cells already saved are skipped.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import gzip
import hashlib
import json
import os
import platform
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator

import yaml

from .anchors import make_anchor, plausible_range
from .backends import Request, make_backend
from .git_sync import GitSync
from .items import Item, load_items
from .parsing import parse_comparison, parse_estimate
from .prompts import anchored_prompt, format_number, unanchored_prompt

PHASES = ["baseline", "anchors", "study1", "study2"]


# ----------------------------------------------------------------------------- config

def load_config(path: str | Path, smoke: bool = False) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # YAML reads an unquoted `off` as False; level names must be strings.
    cfg["thinking_levels"] = {("off" if k is False else str(k)): int(v)
                              for k, v in cfg["thinking_levels"].items()}
    if smoke:
        cfg = copy.deepcopy(cfg)
        cfg["output_dir"] = cfg["output_dir"].rstrip("/") + "_smoke"
        cfg["thinking_levels"] = {"off": 0, "low": 128, "high": 256}
        cfg["baseline"]["samples_per_level"] = 3
        cfg["study1"]["samples"] = 2
        cfg["study2"]["samples"] = 2
        cfg["max_items"] = 2
    return cfg


def cell_seed(base: int, cell_id: str) -> int:
    return (base + int(hashlib.sha256(cell_id.encode()).hexdigest()[:8], 16)) % (2**31 - 1)


def git_commit(repo: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    return out.stdout.strip()


# ----------------------------------------------------------------------------- storage

def read_records(path: Path) -> list[dict]:
    """All records saved for one study: a folder with one gzip file per saved batch."""
    files = sorted(path.glob("*.jsonl.gz")) if path.is_dir() else ([path] if path.exists() else [])
    rows = []
    for file in files:
        with gzip.open(file, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def append_records(path: Path, rows: Iterable[dict]) -> Path:
    """Save a batch as a new file, so each GitHub push only adds small files."""
    path.mkdir(parents=True, exist_ok=True)
    index = len(list(path.glob("part-*.jsonl.gz")))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = path / f"part-{index:04d}-{stamp}.jsonl.gz"
    tmp = target.with_name(target.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, target)  # a crash mid-write leaves only a .tmp file, which is ignored
    return target


def chunks(seq: list, size: int) -> Iterator[list]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ----------------------------------------------------------------------------- cells

def _cell(cell_id: str, prompt: str, budget: int, n: int, seed: int, **fields) -> dict:
    return {"cell_id": cell_id, "prompt": prompt, "budget": budget, "n": n,
            "seed": cell_seed(seed, cell_id), **fields}


def baseline_cells(model: str, items: list[Item], cfg: dict) -> list[dict]:
    seed, n = cfg["sampling"]["seed"], cfg["baseline"]["samples_per_level"]
    cells = []
    for item in items:
        for level, budget in cfg["thinking_levels"].items():
            cid = f"baseline|{model}|{item.item_id}|{level}"
            cells.append(_cell(cid, unanchored_prompt(item), budget, n, seed, study="baseline",
                               item_id=item.item_id, thinking_level=level, truth=item.truth,
                               anchor=None))
    return cells


def compute_anchors(model: str, items: list[Item], baseline: list[dict], cfg: dict) -> dict:
    s1 = cfg["study1"]
    by_item = defaultdict(list)
    for r in baseline:
        if r["model"] == model and r.get("estimate") is not None:
            by_item[r["item_id"]].append(r["estimate"])
    out = {}
    for item in items:
        rng = plausible_range(by_item.get(item.item_id, []), tuple(s1["range_quantiles"]),
                              s1["min_log_width"])
        if rng is None:
            out[item.item_id] = {"excluded": "fewer than 5 parsable baseline answers"}
            continue
        anchors, skipped = {}, []
        for direction in s1["directions"]:
            for dist_name, dist in s1["distances"].items():
                for precision in s1["precisions"]:
                    key = f"{direction}|{dist_name}|{precision}"
                    value = make_anchor(rng, direction, dist, precision, item.integer,
                                        key=f"{model}|{item.item_id}|{key}")
                    if value is None:
                        skipped.append(key)
                    else:
                        anchors[key] = value
        out[item.item_id] = {"range": rng.to_dict(), "anchors": anchors, "skipped": skipped}
    return out


def study1_cells(model: str, items: list[Item], anchors: dict, cfg: dict) -> list[dict]:
    seed, n = cfg["sampling"]["seed"], cfg["study1"]["samples"]
    cells = []
    for item in items:
        entry = anchors.get(item.item_id, {})
        if "anchors" not in entry:
            continue
        for key, value in entry["anchors"].items():
            direction, distance, precision = key.split("|")
            for level, budget in cfg["thinking_levels"].items():
                cid = f"study1|{model}|{item.item_id}|{level}|{key}"
                cells.append(_cell(cid, anchored_prompt(item, value), budget, n, seed,
                                   study="study1", item_id=item.item_id, thinking_level=level,
                                   direction=direction, distance=distance, precision=precision,
                                   anchor=value, anchor_text=format_number(value, item.integer),
                                   truth=item.truth))
    return cells


def study2_cells(model: str, items: list[Item], cfg: dict) -> list[dict]:
    seed, n = cfg["sampling"]["seed"], cfg["study2"]["samples"]
    cells = []
    for item in items:
        for level, budget in cfg["thinking_levels"].items():
            for source in cfg["study2"]["sources"]:
                for instruction in cfg["study2"]["instructions"]:
                    if source == "self":
                        prompt, anchor = unanchored_prompt(item, instruction), None
                    else:
                        prompt, anchor = anchored_prompt(item, item.reference, instruction), item.reference
                    cid = f"study2|{model}|{item.item_id}|{level}|{source}|{instruction}"
                    cells.append(_cell(cid, prompt, budget, n, seed, study="study2",
                                       item_id=item.item_id, thinking_level=level, source=source,
                                       instruction=instruction, anchor=anchor,
                                       reference=item.reference, truth=item.truth))
    return cells


# ----------------------------------------------------------------------------- running

def run_cells(backend, cells: list[dict], path: Path, model: str, hf_id: str, batch_size: int,
              sync: GitSync, label: str) -> None:
    done = {r["cell_id"] for r in read_records(path)}
    todo = [c for c in cells if c["cell_id"] not in done]
    total = len(cells)
    print(f"[{label}] {total - len(todo)}/{total} cells already done; running {len(todo)}")
    start = time.time()
    finished = 0
    for batch in chunks(todo, batch_size):
        requests = [Request(c["cell_id"], c["prompt"], c["budget"], c["n"], c["seed"],
                            meta={"truth": c.get("truth"), "anchor": c.get("anchor")})
                    for c in batch]
        completions = backend.generate(requests)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        rows = []
        for cell, comps in zip(batch, completions):
            fields = {k: v for k, v in cell.items() if k not in ("n", "seed")}
            for idx, c in enumerate(comps):
                rows.append({
                    **fields, "model": model, "hf_id": hf_id, "sample": idx,
                    "thinking": c.thinking, "answer": c.answer,
                    "thinking_tokens": c.thinking_tokens, "answer_tokens": c.answer_tokens,
                    "thinking_truncated": c.thinking_truncated,
                    "answer_finish_reason": c.answer_finish_reason,
                    "estimate": parse_estimate(c.answer),
                    "comparison": parse_comparison(c.answer),
                    "backend": backend.name, "timestamp": now,
                })
        append_records(path, rows)
        finished += len(batch)
        elapsed = time.time() - start
        eta = elapsed / finished * (len(todo) - finished)
        print(f"[{label}] {total - len(todo) + finished}/{total} cells | "
              f"{elapsed / 60:.1f} min elapsed | ~{eta / 60:.1f} min left", flush=True)
        sync.maybe_sync(f"Pilot data: {model} {label} ({total - len(todo) + finished}/{total} cells)")


def gpu_name() -> str:
    try:
        import torch

        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except Exception:
        return "unknown"


def package_version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:
        return "not installed"


def write_log(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/pilot.yaml")
    ap.add_argument("--model", required=True, help="a key under `models` in the config")
    ap.add_argument("--phase", default="all", choices=["all", *PHASES])
    ap.add_argument("--backend", default="vllm", choices=["vllm", "dryrun"])
    ap.add_argument("--smoke", action="store_true", help="tiny run to check that everything works")
    ap.add_argument("--sync", action="store_true", help="commit and push results to GitHub")
    ap.add_argument("--repo", default=".", help="repository root")
    ap.add_argument("--output-dir", default=None, help="override the config's output_dir")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    cfg = load_config(repo / args.config, smoke=args.smoke)
    if args.model not in cfg["models"]:
        raise SystemExit(f"Unknown model {args.model!r}; choose from {list(cfg['models'])}")
    model_cfg = cfg["models"][args.model]
    if args.output_dir:
        cfg["output_dir"] = args.output_dir
    out = repo / cfg["output_dir"]
    raw = out / "raw" / args.model
    items1 = load_items(repo / cfg["items"]["study1"])
    items2 = load_items(repo / cfg["items"]["study2"])
    if cfg.get("max_items"):
        items1, items2 = items1[: cfg["max_items"]], items2[: cfg["max_items"]]

    sync = GitSync(repo, [out], enabled=args.sync, min_interval=cfg["sync"]["min_interval_seconds"])
    phases = PHASES if args.phase == "all" else [args.phase]
    needs_model = any(p != "anchors" for p in phases)
    backend = make_backend(args.backend, model_cfg, cfg) if needs_model else None
    hf_id = model_cfg["hf_id"] if args.backend == "vllm" else "dry-run"
    batch = cfg["engine"]["cells_per_batch"]

    log = {
        "model": args.model, "hf_id": hf_id, "backend": args.backend, "smoke": args.smoke,
        "phases": phases, "git_commit": git_commit(repo), "gpu": gpu_name(),
        "vllm": package_version("vllm"), "python": platform.python_version(),
        "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "config": cfg,
    }

    log_path = out / "runs" / f"{args.model}.jsonl"
    write_log(log_path, {**log, "event": "start"})

    for phase in phases:
        if phase == "baseline":
            run_cells(backend, baseline_cells(args.model, items1, cfg), raw / "baseline",
                      args.model, hf_id, batch, sync, "baseline")
        elif phase == "anchors":
            baseline = read_records(raw / "baseline")
            if not baseline:
                raise SystemExit("Run the baseline phase first.")
            path = out / "anchors" / f"{args.model}.json"
            if path.exists():  # anchors are fixed once placed, so a resumed run uses the same ones
                print(f"[anchors] using the saved anchors in {path} (delete the file to recompute)")
                continue
            anchors = compute_anchors(args.model, items1, baseline, cfg)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(anchors, indent=2))
            kept = sum("anchors" in v for v in anchors.values())
            skipped = sum(len(v.get("skipped", [])) for v in anchors.values())
            print(f"[anchors] {kept}/{len(anchors)} items have anchors; {skipped} anchors could not "
                  f"be placed -> {path}")
        elif phase == "study1":
            path = out / "anchors" / f"{args.model}.json"
            if not path.exists():
                raise SystemExit("Run the anchors phase first.")
            anchors = json.loads(path.read_text())
            run_cells(backend, study1_cells(args.model, items1, anchors, cfg), raw / "study1",
                      args.model, hf_id, batch, sync, "study1")
        elif phase == "study2":
            run_cells(backend, study2_cells(args.model, items2, cfg), raw / "study2",
                      args.model, hf_id, batch, sync, "study2")
        sync.maybe_sync(f"Pilot data: {args.model} finished {phase}", force=True)

    log["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    write_log(log_path, {**log, "event": "finish"})
    sync.maybe_sync(f"Pilot run log: {args.model}", force=True)
    print("Done.")


if __name__ == "__main__":
    main()
