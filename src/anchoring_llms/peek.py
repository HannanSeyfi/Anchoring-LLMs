"""A quick look at collected data, printed as plain text (used at the end of a Colab run).

Usage:
    python -m anchoring_llms.peek --data data/pilot [--model qwen3-8b]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from .run import read_records

STUDIES = ("baseline", "study1", "study2")


def peek(data_dir: str | Path, model: str | None = None) -> None:
    raw = Path(data_dir, "raw")
    models = [model] if model else sorted(p.name for p in raw.glob("*") if p.is_dir())
    if not models:
        print(f"No data in {raw} yet.")
        return
    for m in models:
        print(f"=== {m} ===")
        example = None
        for study in STUDIES:
            rows = read_records(raw / m / study)
            if not rows:
                print(f"{study:9s} no data yet")
                continue
            by_level = defaultdict(list)
            for r in rows:
                by_level[r["thinking_level"]].append(r)
            parts = []
            for level, rs in by_level.items():
                parsed = sum(r["estimate"] is not None for r in rs) / len(rs)
                tokens = sum(r["thinking_tokens"] for r in rs) / len(rs)
                cut = sum(bool(r["thinking_truncated"]) for r in rs) / len(rs)
                parts.append(f"{level}: parsed {parsed:.0%}, thinking {tokens:.0f} tok, cut off {cut:.0%}")
            print(f"{study:9s} {len(rows):5d} answers | " + " | ".join(parts))
            if study == "study1" and example is None:
                example = next((r for r in rows if r["thinking"]), None)
        if example:
            print(f"\nExample ({example['item_id']}, {example['thinking_level']} reasoning, "
                  f"anchor {example['anchor_text']}):")
            print("THINKING:", example["thinking"][:1200] + (" ..." if len(example["thinking"]) > 1200 else ""))
            print("ANSWER:", example["answer"][:600])
        print()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/pilot")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    peek(args.data, args.model)


if __name__ == "__main__":
    main()
