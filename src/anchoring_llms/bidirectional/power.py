"""Simulation-based power for the primary test (comparison vs co-mention, each direction).

For one direction, each pair gives one assimilation value: the mean of 2 x reps comparison
answers minus the mean of 2 x reps co-mention answers (log1p units). So

    value_pair = effect + u_pair + noise,  u_pair ~ N(0, tau),  noise ~ N(0, sigma * sqrt(2 / (2 reps)))

where sigma is the within-cell sd of log1p answers (from the baselines) and tau the spread of
the true effect between pairs. "Bidirectional" needs both directions' 95% intervals above 0.

The two directions are simulated together (2026-11-07): the low and the high effect of the same
pair are drawn with correlation `rho` (from the pilot), and "both" counts the simulations in
which both intervals clear zero. Squaring the one-direction power, as before, assumed the two
directions were independent. `--from-pilot` also runs a second, model-free version that
resamples the pilot's own pairs (each with its low and high value, centred and shifted by the
effect), which keeps their real spread, tails and dataset mix. Neither version models entities
that appear in several pairs, so both are somewhat optimistic.

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


def _clears(vals: np.ndarray) -> np.ndarray:
    """vals: (sims, n_pairs). True where the normal 95% interval of the mean is above 0."""
    n = vals.shape[1]
    return vals.mean(1) - 1.96 * vals.std(1, ddof=1) / np.sqrt(n) > 0


def power_joint(n_pairs: int, reps: int, effect: float, sigma: float, tau: float, rho: float,
                sims: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Both directions at once: (power low, power high, power both). The pair-level true effects of
    the low and the high entity are correlated (rho); answer noise is independent."""
    rng = np.random.default_rng(seed)
    se_cell = sigma * np.sqrt(2 / (2 * reps))
    cov = tau ** 2 * np.array([[1.0, rho], [rho, 1.0]])
    u = rng.multivariate_normal([0.0, 0.0], cov, size=(sims, n_pairs))
    low = effect + u[..., 0] + rng.normal(0, se_cell, (sims, n_pairs))
    high = effect + u[..., 1] + rng.normal(0, se_cell, (sims, n_pairs))
    a, b = _clears(low), _clears(high)
    return float(a.mean()), float(b.mean()), float((a & b).mean())


def power_resample(wide: pd.DataFrame, n_pairs: int, effect: float, sims: int = 2000,
                   seed: int = 0) -> tuple[float, float, float]:
    """Model-free: draw pilot pairs with replacement (low and high value together), centred on 0 and
    shifted by `effect`. Uses the pilot's own number of repetitions."""
    rng = np.random.default_rng(seed)
    x = wide[["low", "high"]].to_numpy()
    x = x - x.mean(0) + effect
    idx = rng.integers(0, len(x), size=(sims, n_pairs))
    a, b = _clears(x[idx, 0]), _clears(x[idx, 1])
    return float(a.mean()), float(b.mean()), float((a & b).mean())


def table(effects, pairs, reps, sigma, tau, sims=2000, rho: float = 0.0,
          wide: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = []
    for e in effects:
        for n in pairs:
            for r in reps:
                seed = int(1000 * e) + n + r
                p = power_one(n, r, e, sigma, tau, sims, seed=seed)
                pl, ph, pb = power_joint(n, r, e, sigma, tau, rho, sims, seed=seed)
                row = dict(effect=e, pairs=n, repetitions=r, power_one_direction=p,
                           power_low=pl, power_high=ph, power_bidirectional=pb,
                           power_bidirectional_if_independent=p * p, sigma=sigma, tau=tau, rho=rho)
                if wide is not None and len(wide) >= 5:
                    _, _, row["power_bidirectional_resampled"] = power_resample(wide, n, e, sims, seed=seed)
                rows.append(row)
    return pd.DataFrame(rows)


def pilot_wide(pe: pd.DataFrame, col: str = "assim_comparison_vs_C1") -> pd.DataFrame:
    """One row per pair with its low and its high value (pairs with both only)."""
    w = pe.pivot_table(index="pair_id", columns="role", values=col)
    return w.dropna(subset=[c for c in ("low", "high") if c in w]) if {"low", "high"} <= set(w.columns) else pd.DataFrame()


def from_pilot(path: Path) -> tuple[float, float, float, pd.DataFrame]:
    pe = pd.read_csv(path)
    if "split" in pe:
        pe = pe[pe["split"].isin(["pilot", "confirmatory", ""]) | pe["split"].isna()]
    sigma = float(pe["sd_B"].median())
    tau = float(pe.groupby("role")["assim_comparison_vs_C1"].std().mean())
    wide = pilot_wide(pe)
    rho = float(wide["low"].corr(wide["high"])) if len(wide) >= 5 else 0.0
    return sigma, tau, rho, wide


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-pilot", default=None)
    ap.add_argument("--sigma", type=float, default=0.25)
    ap.add_argument("--tau", type=float, default=0.10)
    ap.add_argument("--rho", type=float, default=0.0, help="correlation of a pair's low and high effects")
    ap.add_argument("--out", default="results/bidirectional/power.csv")
    a = ap.parse_args(argv)
    if a.from_pilot:
        sigma, tau, rho, wide = from_pilot(Path(a.from_pilot))
    else:
        sigma, tau, rho, wide = a.sigma, a.tau, a.rho, None
    t = table([0.02, 0.05, 0.10], [20, 40, 60, 80, 120, 160, 200], [5, 10, 20], sigma, tau, rho=rho, wide=wide)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out, index=False)
    piv = t[t["repetitions"] == 10].pivot(index="pairs", columns="effect", values="power_bidirectional")
    print(f"sigma={sigma:.3f}, tau={tau:.3f}, rho={rho:.2f}. Power to find BOTH directions, simulated "
          f"together (10 repetitions):")
    print(piv.to_string(float_format=lambda v: f"{v:.2f}"))
    ok = t[(t["repetitions"] == 10) & (t["effect"] == 0.05) & (t["power_bidirectional"] >= 0.8)]
    print("Pairs needed for 80% at effect 0.05:", int(ok["pairs"].min()) if len(ok) else "more than 200")
    if "power_bidirectional_resampled" in t:
        rs = t[t["repetitions"] == 10].pivot(index="pairs", columns="effect", values="power_bidirectional_resampled")
        print("Resampling the pilot's own pairs instead:")
        print(rs.to_string(float_format=lambda v: f"{v:.2f}"))
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
