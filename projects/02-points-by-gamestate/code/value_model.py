"""
value_model.py — team-minute state values, goal values, intervals, calibration
==============================================================================

Unit of analysis for the value model: the team-minute. Every match in the
model contributes 2 × 90 rows (each side, minutes 1–90), each carrying the
goal difference at the start of that minute and the side's final result
(official score). Stoppage time folds into minute 45 / 90.

  V(gd, bin)   expected final points of a team at goal difference gd during
               a minute in that 15-minute bin = mean of 3·W + 1·D over those
               team-minutes. 0–0s and goalless spells count, unlike a table
               sampled only at goal moments.
  U(gd)        the same with the bins pooled (time-blind).
  goal value   V(gd + 1, bin) − V(gd, bin) for a goal from gd to gd + 1 in
               that bin; time-blind U(gd + 1) − U(gd).

Everything is computed from per-match count arrays C[match, gd, bin, W/D/L],
so a bootstrap over matches (stratified by league) is a weighted sum.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import MIN_GD, MAX_GD, TIME_BINS

GDS = np.arange(MIN_GD, MAX_GD + 1)            # −7 … +7
N_GD, N_BIN = len(GDS), len(TIME_BINS)
MINUTES = np.arange(1, 91)
MINUTE_BIN = (MINUTES - 1) // 15                # minute 1–15 → bin 0, …, 76–90 → bin 5
BIN_INDEX = {b: i for i, b in enumerate(TIME_BINS)}
W, D, L = 0, 1, 2


def gd_index(gd) -> np.ndarray:
    return np.clip(np.asarray(gd, dtype=int), MIN_GD, MAX_GD) - MIN_GD


# ── Panel ───────────────────────────────────────────────────────────────
def panel_counts(matches: pd.DataFrame, goals: pd.DataFrame) -> np.ndarray:
    """C[m, gd, bin, outcome]: team-minutes per match by state and the side's final result.

    `matches` needs match_id, home_goals, away_goals (the result used);
    `goals` needs match_id, side, minute_state. A goal in minute t changes
    the state from minute t + 1.
    """
    C = np.zeros((len(matches), N_GD, N_BIN, 3), dtype=np.int32)
    by_match = {k: g for k, g in goals.groupby("match_id", sort=False)}
    for i, r in enumerate(matches.itertuples(index=False)):
        gd = np.zeros(90, dtype=int)                          # home perspective
        g = by_match.get(r.match_id)
        if g is not None:
            for side, t in zip(g["side"], g["minute_state"]):
                gd[MINUTES > t] += 1 if side == "home" else -1
        hg, ag = r.home_goals, r.away_goals
        res_home = W if hg > ag else (D if hg == ag else L)
        res_away = {W: L, D: D, L: W}[res_home]
        np.add.at(C[i], (gd_index(gd), MINUTE_BIN, res_home), 1)
        np.add.at(C[i], (gd_index(-gd), MINUTE_BIN, res_away), 1)
    return C


# ── Values from counts ──────────────────────────────────────────────────
def values(Csum: np.ndarray) -> dict:
    """State values and goal values from summed counts [gd, bin, 3]."""
    N = Csum.sum(-1).astype(float)
    S = 3.0 * Csum[..., W] + Csum[..., D]
    with np.errstate(invalid="ignore", divide="ignore"):
        V = np.where(N > 0, S / N, np.nan)
        P = np.where(N[..., None] > 0, Csum / N[..., None], np.nan)
        Nu = N.sum(1)
        U = np.where(Nu > 0, S.sum(1) / Nu, np.nan)
    goal_t = np.full((N_GD, N_BIN), np.nan)
    goal_t[:-1] = V[1:] - V[:-1]                    # row gd: goal from gd to gd + 1
    goal_u = np.full(N_GD, np.nan)
    goal_u[:-1] = U[1:] - U[:-1]
    return {"N": N, "V": V, "P": P, "U": U, "goal_t": goal_t, "goal_u": goal_u}


def goal_value_lookup(vals: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-cell goal values with the time-blind value filling cells the panel never saw."""
    gt, gu = vals["goal_t"], vals["goal_u"]
    filled = np.isnan(gt) & ~np.isnan(gu)[:, None]
    return np.where(filled, gu[:, None], gt), gu, filled


# ── Bootstrap ───────────────────────────────────────────────────────────
def boot_weights(strata: np.ndarray, n_boot: int, seed: int):
    """Yield match weight vectors: a resample of matches within each stratum (league)."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(strata == s) for s in pd.unique(strata)]
    m = len(strata)
    for _ in range(n_boot):
        w = np.zeros(m)
        for idx in groups:
            w += np.bincount(rng.choice(idx, size=idx.size, replace=True), minlength=m)
        yield w


def pct_ci(samples: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = np.nanpercentile(samples, [2.5, 97.5], axis=axis)
    return lo, hi


# ── Calibration ─────────────────────────────────────────────────────────
def predictions(Csum: np.ndarray, *, timed: bool) -> np.ndarray:
    """P[gd, bin, outcome] from training counts; time-blind rows broadcast over bins.
    Unseen cells fall back to the time-blind row, then to the overall base rate."""
    N = Csum.sum(-1, keepdims=True).astype(float)
    base = Csum.sum((0, 1)) / Csum.sum()
    Cu = Csum.sum(1, keepdims=True)
    Nu = Cu.sum(-1, keepdims=True).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        pu = np.where(Nu > 0, Cu / Nu, base)
        pt = np.where(N > 0, Csum / N, pu)
    return pt if timed else np.broadcast_to(pu, Csum.shape).copy()


def brier_per_match(Cm: np.ndarray, P: np.ndarray) -> np.ndarray:
    """Sum over a match's team-minutes of the 3-outcome Brier score, from counts:
    Σ_k (p_k − o_k)² = Σ_k p_k² − 2 p_obs + 1 per team-minute."""
    Nm = Cm.sum(-1)
    return (Nm * (P ** 2).sum(-1)).sum((1, 2)) - 2 * (Cm * P).sum((1, 2, 3)) + Nm.sum((1, 2))
