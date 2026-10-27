"""
shrink.py — empirical Bayes rates, rank intervals, repeatability
================================================================

A player's EP per 90 is a rate measured with noise: over 1,000 minutes one
lucky 90th-minute winner moves it a lot, over 10,000 minutes it barely
moves. Empirical Bayes pulls each rate toward the average for the player's
position, by more when the minutes are few:

  x_i      observed EP per 90
  v_i      its sampling variance: 90² · φ / minutes_i, where φ is the
           per-minute variance of match EP around a player's own rate
           (pooled within position, quasi-Poisson)
  μ, τ²    the position's average rate and the spread of true rates,
           estimated by the DerSimonian–Laird method from players above
           the minutes floor
  θ_i      shrunk rate = μ + τ² / (τ² + v_i) · (x_i − μ)
  s_i²     its posterior variance τ² · v_i / (τ² + v_i)

Rank intervals: draw every eligible player's rate from N(θ_i, s_i²)
together, rank them in each draw, and keep the 2.5th and 97.5th percentile
rank. The draws treat players as independent: they carry the sampling noise
of each player's own matches, not the shared uncertainty of the goal prices.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def dispersion(per_match: pd.DataFrame) -> float:
    """φ from per-(player, match) rows with columns key, e (EP), m (minutes > 0)."""
    d = per_match[per_match["m"] > 0]
    g = d.groupby("key")
    rate = g["e"].transform("sum") / g["m"].transform("sum")
    resid = ((d["e"] - rate * d["m"]) ** 2 / d["m"]).sum()
    dof = (g.size() - 1).clip(lower=0).sum()
    return float(resid / dof)


def dl_prior(x: np.ndarray, v: np.ndarray) -> tuple[float, float]:
    """DerSimonian–Laird estimate of the mean and between-player variance of true rates."""
    w = 1.0 / v
    mu_fe = np.sum(w * x) / np.sum(w)
    q = np.sum(w * (x - mu_fe) ** 2)
    k = len(x)
    tau2 = max(0.0, (q - (k - 1)) / (np.sum(w) - np.sum(w ** 2) / np.sum(w)))
    ws = 1.0 / (v + tau2)
    return float(np.sum(ws * x) / np.sum(ws)), float(tau2)


def shrink(x: np.ndarray, v: np.ndarray, mu: np.ndarray, tau2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    b = tau2 / (tau2 + v)
    return mu + b * (x - mu), tau2 * v / (tau2 + v)


def eb_block(df: pd.DataFrame, phi: dict, *, group: str, floor: int) -> tuple[pd.DataFrame, dict]:
    """Shrink df['p90'] (minutes in df['minutes']) toward the mean of df[group].
    Priors come from rows with minutes >= floor; groups missing from `phi` use the pooled prior."""
    out = df.copy()
    out["v"] = np.nan
    priors = {}
    pooled_phi = phi["_all"]
    for g, idx in out.groupby(group).groups.items():
        out.loc[idx, "v"] = 90.0 ** 2 * phi.get(g, pooled_phi) / out.loc[idx, "minutes"]
    base = out[out["minutes"] >= floor]
    mu_all, tau_all = dl_prior(base["p90"].to_numpy(), base["v"].to_numpy())
    priors["_all"] = {"mu": mu_all, "tau2": tau_all, "n": int(len(base)), "phi": pooled_phi}
    for g, sub in base.groupby(group):
        if g in phi and len(sub) >= 30:
            mu, tau2 = dl_prior(sub["p90"].to_numpy(), sub["v"].to_numpy())
            priors[g] = {"mu": mu, "tau2": tau2, "n": int(len(sub)), "phi": phi[g]}
    mu = out[group].map(lambda g: priors.get(g, priors["_all"])["mu"]).to_numpy(float)
    tau2 = out[group].map(lambda g: priors.get(g, priors["_all"])["tau2"]).to_numpy(float)
    theta, s2 = shrink(out["p90"].to_numpy(float), out["v"].to_numpy(float), mu, tau2)
    out["theta"], out["theta_sd"] = theta, np.sqrt(s2)
    out["theta_lo"], out["theta_hi"] = theta - 1.96 * np.sqrt(s2), theta + 1.96 * np.sqrt(s2)
    out["pull"] = 1.0 - tau2 / (tau2 + out["v"].to_numpy(float))          # share of the gap to μ removed
    return out, priors


def rank_intervals(theta: np.ndarray, sd: np.ndarray, *, draws: int, seed: int, top: int = 10) -> dict:
    """Posterior rank (1 = best) intervals and the chance of a top-`top` finish."""
    rng = np.random.default_rng(seed)
    n = len(theta)
    lo, hi, med, p_top = (np.empty(n) for _ in range(4))
    ranks = np.empty((draws, n), dtype=np.int32)
    for k in range(draws):
        sample = theta + sd * rng.standard_normal(n)
        order = np.argsort(-sample, kind="stable")
        ranks[k, order] = np.arange(1, n + 1)
    lo, hi = np.percentile(ranks, [2.5, 97.5], axis=0)
    med = np.median(ranks, axis=0)
    p_top = (ranks <= top).mean(axis=0)
    return {"lo": np.floor(lo).astype(int), "hi": np.ceil(hi).astype(int), "median": med, "p_top": p_top}


def correlation_ci(a: np.ndarray, b: np.ndarray, cluster: np.ndarray, *, n_boot: int, seed: int) -> dict:
    """Pearson r of (a, b) with a bootstrap interval that resamples clusters (players)."""
    r = float(np.corrcoef(a, b)[0, 1])
    rng = np.random.default_rng(seed)
    ids = pd.unique(cluster)
    pos = {c: np.flatnonzero(cluster == c) for c in ids}
    samples = np.empty(n_boot)
    for k in range(n_boot):
        pick = rng.choice(ids, size=len(ids), replace=True)
        idx = np.concatenate([pos[c] for c in pick])
        samples[k] = np.corrcoef(a[idx], b[idx])[0, 1]
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return {"r": r, "lo": float(lo), "hi": float(hi), "pairs": int(len(a)), "players": int(len(ids))}
