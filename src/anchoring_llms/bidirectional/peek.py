"""Quick look at saved answers: how many trials, how many with a number, and a few replies.

    python -m anchoring_llms.bidirectional.peek --phase screen --model qwen3-32b [--smoke]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .run import load_records
from .trials import load_config


def peek(cfg: dict, phase: str, model: str, level: str | None = None, smoke: bool = False, n: int = 3) -> pd.DataFrame:
    level = level or cfg["thinking_level"]
    folder = Path(cfg["paths"]["runs_dir"] + ("_smoke" if smoke else "")) / phase / model / level
    recs = load_records(folder)
    if not recs:
        print(f"No answers in {folder} yet.")
        return pd.DataFrame()
    df = pd.DataFrame(recs)
    print(f"{len(df)} answers in {folder}")
    print(df.groupby(["condition", "parse_status"]).size().unstack(fill_value=0).to_string())
    for r in df.sample(min(n, len(df)), random_state=0).to_dict("records"):
        print("\n---", r["trial_id"], "|", r["condition"], "|", r.get("target_label", ""))
        turns = r.get("turns") or []
        if len(turns) == 2:
            print("Q1:", turns[0])
            print("A1:", str(r.get("reply_1") or "")[-200:])
        print("Q:", turns[-1] if turns else "")
        print("A:", str(r.get("reply_2") or r.get("reply_1") or "")[-300:])
        print("Parsed:", r.get("estimate"), f"({r.get('parse_status')})")
    return df


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="configs/bidirectional.yaml")
    ap.add_argument("--phase", required=True)
    ap.add_argument("--model", default="qwen3-32b")
    ap.add_argument("--level", default=None)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args(argv)
    peek(load_config(a.config), a.phase, a.model, a.level, a.smoke)


if __name__ == "__main__":
    main()
