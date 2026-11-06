"""Simulation-based power for the primary test (comparison vs co-mention, each direction).

For one direction, each pair gives one assimilation value: the mean of 2 x reps comparison
answers minus the mean of 2 x reps co-mention answers (log1p units). So

    value_pair = effect + u_pair + noise,  u_pair ~ N(0, tau),  noise ~ N(0, sigma * sqrt(2 / (2 reps)))

where sigma is the within-cell sd of log1p answers (from the baselines) and tau the spread of
the true effect between pairs. "Bidirectional" needs both directions' 95% intervals above 0, so
the power for that is roughly the product of the two powers. Defaults are placeholders until the
pilot gives sigma and tau; `--from-pilot` reads them from a pilot's pair_effects.csv.

    python -m anchoring_llms.bidirectional.power
    python -m anchoring_llms.bidirectional.power --from-pilot results/bidirectional/qwen3-32b/off/tables/pair_effects.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def power_one(n_pairs: int, reps: int, effect: float, sigma: float, tau: float, sims: int = 2000,
              seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    se_cell = sigma * np.sqrt(2 / (2 * reps))
    vals = effect + rng.normal(0, tau, (sims, n_pairs)) + rng.normal(0, se_cell, (sims, n_pairs))
    m = vals.mean(1)
    s = vals.std(1, ddof=1) / np.sqrt(n_pairs)
    return float(np.mean(m - 1.96 * s > 0))


def table(effects, pairs, reps, sigma, tau, sims=2000) -> pd.DataFrame:
    rows = []
    for e in effects:
        for n in pairs:
            for r in reps:
                p = power_one(n, r, e, sigma, tau, sims, seed=int(1000 * e) + n + r)
                rows.append(dict(effect=e, pairs=n, repetitions=r, power_one_direction=p,
                                 power_bidirectional=p * p, sigma=sigma, tau=tau))
    return pd.DataFrame(rows)


def from_pilot(path: Path) -> tuple[float, float]:
    pe = pd.read_csv(path)
    sigma = float(pe["sd_B"].median())
    tau = float(pe.groupby("role")["assim_comparison_vs_C1"].std().mean())
    return sigma, tau


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-pilot", default=None)
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--tau", type=float, default=0.10)
    ap.add_argument("--out", default="results/bidirectional/power.csv")
    a = ap.parse_args(argv)
    sigma, tau = from_pilot(Path(a.from_pilot)) if a.from_pilot else (a.sigma, a.tau)
    t = table([0.02, 0.05, 0.10], [20, 40, 60, 80, 120, 160, 200], [5, 10, 20], sigma, tau)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)
    piv = t[t["repetitions"] == 10].pivot(index="pairs", columns="effect", values="power_bidirectional")
    print(f"sigma={sigma:.3f}, tau={tau:.3f}. Power to find BOTH directions (10 repetitions):")
    print(piv.to_string(float_format=lambda v: f"{v:.2f}"))
    ok = t[(t["repetitions"] == 10) & (t["effect"] == 0.05) & (t["power_bidirectional"] >= 0.8)]
    print("Pairs needed for 80% at effect 0.05:", int(ok["pairs"].min()) if len(ok) else "more than 200")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
