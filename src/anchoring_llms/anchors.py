"""Placing anchors relative to each model's own plausible range.

The plausible range is the 5th-95th percentile of a model's unanchored
estimates for an item. Anchors are placed just outside it ("near") or well
outside it ("far"), below it ("low") or above it ("high"), and written as a
round or a precise number (Janiszewski & Uy, 2008).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Iterable, Optional

import numpy as np


@dataclass
class PlausibleRange:
    lo: float
    hi: float
    median: float
    n: int
    log_scale: bool
    width: float  # in log10 units if log_scale, else in raw units

    def to_dict(self) -> dict:
        return asdict(self)


def plausible_range(estimates: Iterable[float], quantiles=(0.05, 0.95),
                    min_log_width: float = 0.15) -> Optional[PlausibleRange]:
    values = np.array([v for v in estimates if v is not None and math.isfinite(v)], dtype=float)
    if len(values) < 5:
        return None
    lo, hi = np.quantile(values, quantiles)
    median = float(np.median(values))
    log_scale = bool(np.all(values > 0))
    if log_scale:
        width = max(math.log10(hi) - math.log10(lo), min_log_width)
    else:
        width = max(hi - lo, abs(median) * 0.1, 1e-9)
    return PlausibleRange(float(lo), float(hi), median, int(len(values)), log_scale, float(width))


def round_sig(x: float, sig: int) -> float:
    if x == 0:
        return 0.0
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


def _step(x: float, sig: int) -> float:
    return 10 ** (math.floor(math.log10(abs(x))) - (sig - 1))


def _jitter(key: str, lo: float, hi: float) -> float:
    """Deterministic pseudo-random number in [lo, hi) from a key."""
    h = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return lo + (hi - lo) * h


def raw_anchor(rng: PlausibleRange, direction: str, distance: float) -> float:
    """Anchor value before rounding: `distance` range-widths beyond the range edge."""
    if rng.log_scale:
        if direction == "high":
            return 10 ** (math.log10(rng.hi) + distance * rng.width)
        return 10 ** (math.log10(rng.lo) - distance * rng.width)
    if direction == "high":
        return rng.hi + distance * rng.width
    return rng.lo - distance * rng.width


def round_anchor(value: float, rng: PlausibleRange, direction: str) -> float:
    """Round to 2 significant figures, then push outward until outside the range."""
    r = round_sig(value, 2)
    step = _step(r if r != 0 else value, 2)
    if direction == "high":
        while r <= rng.hi:
            r = round_sig(r + step, 2)
    else:
        while r >= rng.lo:
            r = round_sig(r - step, 2)
            if rng.log_scale and r <= 0:
                r = round_sig(value, 1)
                break
    return float(r)


def precise_anchor(round_value: float, direction: str, integer: bool, key: str) -> float:
    """A precise-looking number 0.4-2% further out than the round anchor."""
    u = _jitter(key, 0.004, 0.02)
    factor = 1 + u if direction == "high" else 1 - u
    p = round_value * factor if round_value > 0 else round_value + (u if direction == "high" else -u) * abs(round_value or 1)
    if integer:
        out = 1 if direction == "high" else -1
        p = int(round(p))
        if p == int(round_value):
            p += out
        if p % 10 == 0:
            p += out
        return float(p)
    p = round_sig(p, 4)
    step = _step(p, 4)
    digits = f"{abs(p) / step:.0f}"
    if digits.endswith("0"):
        p = p + step if direction == "high" else p - step
        p = round_sig(p, 4)
    return float(p)


def make_anchor(rng: PlausibleRange, direction: str, distance: float, precision: str,
                integer: bool, key: str) -> Optional[float]:
    """The anchor value, or None when no usable anchor exists.

    That happens when a model's answers are so spread out that a low anchor would have to
    be zero or negative for a positive quantity (e.g. a count whose range starts near 1).
    """
    r = round_anchor(raw_anchor(rng, direction, distance), rng, direction)
    if integer:
        r = float(int(round(r)))
    a = r if precision == "round" else precise_anchor(r, direction, integer, key)
    if rng.log_scale and a <= 0:
        return None
    if (direction == "low" and a >= rng.lo) or (direction == "high" and a <= rng.hi):
        return None
    return a
