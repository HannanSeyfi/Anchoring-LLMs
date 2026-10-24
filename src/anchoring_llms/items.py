"""Loading estimation items from CSV."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Item:
    item_id: str
    question: str
    unit: str
    truth: Optional[float]
    integer: bool
    domain: str
    reference: Optional[float] = None  # Study 2: the value a solver naturally starts from


def _to_float(value: str) -> Optional[float]:
    value = (value or "").strip()
    return float(value) if value else None


def load_items(path: str | Path) -> list[Item]:
    items = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            items.append(
                Item(
                    item_id=row["item_id"].strip(),
                    question=row["question"].strip(),
                    unit=row["unit"].strip(),
                    truth=_to_float(row.get("truth", "")),
                    integer=row.get("integer", "false").strip().lower() == "true",
                    domain=row.get("domain", "").strip(),
                    reference=_to_float(row.get("reference", "")),
                )
            )
    ids = [it.item_id for it in items]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate item ids in {path}")
    return items
