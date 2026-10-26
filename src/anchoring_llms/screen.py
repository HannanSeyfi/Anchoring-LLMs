"""Screen candidate questions: find the ones a model does not know.

Every candidate question is asked without an anchor, several times per thinking
level (by default 20 times with thinking off and 20 with low thinking). Answers
are saved exactly like pilot answers, so a stopped run resumes where it stopped.
`anchoring_llms.select_items` then picks the final questions from these answers.

Usage (from the repository root):
    python -m anchoring_llms.screen --config configs/pilot_v2.yaml --model qwen3-32b --sync
    python -m anchoring_llms.screen --config configs/pilot_v2.yaml --model qwen3-8b --backend dryrun --smoke
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from .backends import SpendLimitReached, make_backend
from .git_sync import GitSync
from .items import Item, load_items
from .prompts import unanchored_prompt
from .run import _cell, git_commit, load_config, run_cells, run_options, write_log

STUDIES = ("study1", "study2")


def screen_dirs(cfg: dict, smoke: bool = False) -> tuple[str, str]:
    """Where screening answers and the screening report go (smoke tests use separate folders)."""
    sc = cfg["screening"]
    suffix = "_smoke" if smoke else ""
    return sc["output_dir"].rstrip("/") + suffix, sc["results_dir"].rstrip("/") + suffix


def screen_cells(model: str, items: list[Item], study: str, cfg: dict) -> list[dict]:
    sc, seed = cfg["screening"], cfg["sampling"]["seed"]
    cells = []
    for item in items:
        for level in sc["levels"]:
            cid = f"screen|{model}|{item.item_id}|{level}"
            cells.append(_cell(cid, unanchored_prompt(item), cfg["thinking_levels"][level], sc["samples"],
                               seed, study=f"screen_{study}", item_id=item.item_id, thinking_level=level,
                               truth=item.truth, reference=item.reference, anchor=None,
                               domain=item.domain))
    return cells


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/pilot_v2.yaml")
    ap.add_argument("--model", required=True, help="a key under `models` in the config")
    ap.add_argument("--study", default="both", choices=["both", *STUDIES])
    ap.add_argument("--backend", default=None, choices=["vllm", "deepinfra", "dryrun"],
                    help="default: the model's `backend` in the config, else vllm")
    ap.add_argument("--max-spend", type=float, default=None,
                    help="spending limit in US dollars for hosted models (default: api.max_spend_usd)")
    ap.add_argument("--smoke", action="store_true", help="tiny run to check that everything works")
    ap.add_argument("--sync", action="store_true", help="commit and push results to GitHub")
    ap.add_argument("--repo", default=".", help="repository root")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    cfg = load_config(repo / args.config, smoke=args.smoke)
    if "screening" not in cfg:
        raise SystemExit(f"{args.config} has no `screening` section; use configs/pilot_v2.yaml.")
    if args.model not in cfg["models"]:
        raise SystemExit(f"Unknown model {args.model!r}; choose from {list(cfg['models'])}")
    if args.max_spend is not None:
        cfg["api"]["max_spend_usd"] = args.max_spend
    model_cfg = cfg["models"][args.model]
    kind = args.backend or model_cfg.get("backend", "vllm")
    out = repo / screen_dirs(cfg, args.smoke)[0]
    studies = STUDIES if args.study == "both" else (args.study,)

    sync = GitSync(repo, [out], enabled=args.sync, min_interval=cfg["sync"]["min_interval_seconds"])
    backend = make_backend(kind, model_cfg, cfg, spend_path=out / "runs" / f"{args.model}.spend.json")
    hf_id = "dry-run" if kind == "dryrun" else model_cfg["hf_id"]
    title = "Screening data"
    opts = {**run_options(cfg), "title": title}
    log = {"model": args.model, "hf_id": hf_id, "backend": kind, "smoke": args.smoke, "studies": list(studies),
           "git_commit": git_commit(repo),
           "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "screening": cfg["screening"], "sampling": cfg["sampling"]}
    log_path = out / "runs" / f"{args.model}.jsonl"
    write_log(log_path, {**log, "event": "start"})

    try:
        for study in studies:
            items = load_items(repo / cfg["screening"]["candidates"][study])
            if cfg.get("max_items"):
                items = items[: cfg["max_items"]]
            run_cells(backend, screen_cells(args.model, items, study, cfg), out / "raw" / args.model / study,
                      args.model, hf_id, cfg["engine"]["cells_per_batch"], sync, f"screen {study}", **opts)
            sync.maybe_sync(f"{title}: {args.model} finished {study}", force=True)
    except SpendLimitReached as stop:
        write_log(log_path, {**log, "event": "spend_limit", "spent_usd": round(backend.spent, 4)})
        sync.maybe_sync(f"{title}: {args.model} stopped at the spending limit", force=True)
        raise SystemExit(f"\n{stop}") from None

    if hasattr(backend, "spent"):
        log["spent_usd"] = round(backend.spent, 4)
    log["finished"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    write_log(log_path, {**log, "event": "finish"})
    sync.maybe_sync(f"{title}: run log for {args.model}", force=True)
    print("Done. Next: python -m anchoring_llms.select_items --config", args.config,
          "--smoke" if args.smoke else "")


if __name__ == "__main__":
    main()
