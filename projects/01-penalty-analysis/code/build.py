"""
build.py — Penalty conversion after a goalkeeper foul
─────────────────────────────────────────────────────

Loads FULL_DICT_ROWS from the local READY_DATA folder, combines the
SPECIALS + SUMMARY DataFrames per competition, links every penalty to its
own taker, fouled player and conceder, and writes every number needed by
the dashboard to ../data/data.json.

Unit of analysis: one penalty. A team's penalty is linked when that team
took exactly one penalty in the match — the taker (PKatt) and the fouled
player (PKwon) are then on that team, the conceder (PKcon) on the other.

Primary test (one-tailed):
    Treatment = linked penalties where the GK conceded the foul AND the
                fouled player took the penalty himself (the "hurt taker").
    Control   = every other linked penalty.
    H0: conversion_treatment = conversion_control
    H1: conversion_treatment < conversion_control       (one-tailed)
    Test: statsmodels.proportions_ztest(alternative='smaller')
          + Wilson 95% CIs on each proportion, Newcombe 95% CI on the
          difference, minimum detectable effect at 80% power

Secondary outputs: per-league breakdown of the same test, the 2x2
matrix of (GK foul x taker-was-fouled-player) for visual context, and
descriptive overall / per-league / per-season conversion rates.

Run:
    python code/build.py

Override raw-data location with the env var RENBALL_DATA_PATH.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (
    confint_proportions_2indep, proportion_confint, proportion_effectsize, proportions_ztest,
)

# ── Config ─────────────────────────────────────────────────
DEFAULT_DATA_PATH = r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA"
DATA_PATH = Path(os.environ.get("RENBALL_DATA_PATH", DEFAULT_DATA_PATH))

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_DIR / "data" / "data.json"

LEAGUE_LABELS = {
    "PL": "Premier League",
    "LALIGA": "La Liga",
    "SERIEA": "Serie A",
    "BUNDESLIGA": "Bundesliga",
    "LIGUE1": "Ligue 1",
}

SPECIALS_COLS = [
    "Competition", "Player", "#", "Nation", "Pos", "Age", "attendance",
    "team_formation", "team_name", "team_id", "opposition_id",
    "opposition_name", "opposition_formation", "score", "goals_scored",
    "goals_conceded", "outcome", "date", "match_id", "dayofweek",
    "gameweek", "site", "xg_scored", "xg_conceded", "Season", "Min",
    "Min Match Weight", "Performance_PKwon", "Performance_PKcon",
]
SUMMARY_COLS = [
    "Competition", "Player", "#", "Nation", "Pos", "Age", "attendance",
    "team_formation", "team_name", "team_id", "opposition_id",
    "opposition_name", "opposition_formation", "score", "goals_scored",
    "goals_conceded", "outcome", "date", "match_id", "dayofweek",
    "gameweek", "start_time", "site", "xg_scored", "xg_conceded",
    "Season", "Min", "Min Match Weight", "Performance_PK",
    "Performance_PKatt",
]
JOIN_KEYS = [
    "Competition", "Player", "#", "Nation", "Pos", "Age", "attendance",
    "team_formation", "team_name", "team_id", "opposition_id",
    "opposition_name", "opposition_formation", "score", "goals_scored",
    "goals_conceded", "outcome", "date", "match_id", "dayofweek",
    "gameweek", "site", "xg_scored", "xg_conceded", "Season", "Min",
    "Min Match Weight",
]
PEN_COLS = ["Performance_PK", "Performance_PKatt", "Performance_PKwon", "Performance_PKcon"]

MATRIX_LABELS = {
    "gk_won":    "GK fouled the player who then took the penalty",  # treatment cell
    "gk_other":  "GK conceded, the taker was not the fouled player",
    "ngk_won":   "Outfielder fouled, fouled player took the penalty",
    "ngk_other": "Outfielder conceded, the taker was not the fouled player",
}

CONTROL_KEYS = ["gk_other", "ngk_won", "ngk_other"]

# Why an attempt can't be tied to one taker / fouled player / conceder
EXCLUDE_REASONS = {
    "multi":       "team took 2+ penalties in the match",
    "no_con":      "no conceder recorded",
    "multi_con":   "opponent recorded 2+ conceded penalties",
    "multi_won":   "2+ players credited with winning it",
    "no_opponent": "opponent rows missing",
}


# ── Data prep ──────────────────────────────────────────────
def load_pickle(name: str):
    return pd.read_pickle(DATA_PATH / f"{name}.pkl")


def build_combined_dicts(full_dict_rows: dict) -> dict:
    """Combine ROWS_DICTS_SPECIALS + ROWS_DICTS_SUMMARY per competition."""
    specials_dicts: dict[str, pd.DataFrame] = {}
    summary_dicts: dict[str, pd.DataFrame] = {}

    for competition, data in full_dict_rows.items():
        if "ROWS_DICTS_SPECIALS" not in data or "ROWS_DICTS_SUMMARY" not in data:
            continue
        specials_frames = [df.assign(Season=season) for season, df in data["ROWS_DICTS_SPECIALS"].items()]
        summary_frames = [df.assign(Season=season) for season, df in data["ROWS_DICTS_SUMMARY"].items()]
        if specials_frames:
            specials_dicts[competition] = pd.concat(specials_frames, ignore_index=True)[SPECIALS_COLS]
        if summary_frames:
            summary_dicts[competition] = pd.concat(summary_frames, ignore_index=True)[SUMMARY_COLS]

    combined: dict[str, pd.DataFrame] = {}
    for competition in specials_dicts:
        if competition not in summary_dicts:
            continue
        combined[competition] = pd.merge(
            specials_dicts[competition],
            summary_dicts[competition],
            on=JOIN_KEYS,
            how="outer",
            suffixes=("_specials", "_summary"),
        )
    return combined


def loose_pen_match_ids(df: pd.DataFrame):
    return df.loc[(df[PEN_COLS] != 0).any(axis=1), "match_id"].unique()


def rate_pct(conv: int, att: int) -> float:
    return (conv / att * 100.0) if att else 0.0


def attempts_conversions(df: pd.DataFrame) -> tuple[int, int]:
    return int(df["Performance_PKatt"].sum()), int(df["Performance_PK"].sum())


# ── Matrix + primary test helpers ──────────────────────────
def empty_cells() -> dict:
    return {k: {"label": v, "attempts": 0, "conversions": 0} for k, v in MATRIX_LABELS.items()}


def link_penalties(df: pd.DataFrame, league: str) -> tuple[pd.DataFrame, dict]:
    """One row per penalty tied to its own taker, fouled player and conceder.

    Works per (match, team): when a team took exactly one penalty in a match,
    its taker and fouled player are on that team and the conceder is the one
    opponent row with PKcon = 1. Returns the linked penalties and the number
    of attempts left unlinked, by EXCLUDE_REASONS key.
    """
    d = df[df["match_id"].isin(loose_pen_match_ids(df))].copy()
    d[PEN_COLS] = d[PEN_COLS].fillna(0).astype(int)
    teams = d.groupby("match_id")["team_id"].unique()
    rows_by_team = {k: g for k, g in d.groupby(["match_id", "team_id"])}

    linked, excluded = [], {k: 0 for k in EXCLUDE_REASONS}
    for (mid, tid), grp in rows_by_team.items():
        att = int(grp["Performance_PKatt"].sum())
        if att == 0:
            continue
        others = [t for t in teams[mid] if t != tid]
        if len(others) != 1:
            excluded["no_opponent"] += att
            continue
        if att >= 2:
            excluded["multi"] += att
            continue
        opp = rows_by_team[(mid, others[0])]
        conceders = opp[opp["Performance_PKcon"] > 0]
        n_con = int(conceders["Performance_PKcon"].sum())
        if n_con == 0:
            excluded["no_con"] += 1
            continue
        if n_con >= 2:
            excluded["multi_con"] += 1
            continue
        winners = grp[grp["Performance_PKwon"] > 0]
        if int(winners["Performance_PKwon"].sum()) >= 2:
            excluded["multi_won"] += 1
            continue
        taker = grp[grp["Performance_PKatt"] == 1].iloc[0]
        won_by = "none" if winners.empty else ("taker" if winners.iloc[0]["Player"] == taker["Player"] else "other")
        linked.append({
            "match_id": mid, "team_id": tid, "league": league, "season": str(taker["Season"]),
            "taker": taker["Player"], "scored": int(taker["Performance_PK"]),
            "conceder_gk": bool(conceders.iloc[0]["Pos"] == "GK"), "won_by": won_by,
        })
    return pd.DataFrame(linked), excluded


def cells_from_linked(L: pd.DataFrame) -> dict:
    """The 2x2 of (GK conceded) x (taker was the fouled player), one entry per penalty."""
    cells = empty_cells()
    taker_won = L["won_by"] == "taker"
    masks = {
        "gk_won":    L["conceder_gk"] & taker_won,
        "gk_other":  L["conceder_gk"] & ~taker_won,
        "ngk_won":   ~L["conceder_gk"] & taker_won,
        "ngk_other": ~L["conceder_gk"] & ~taker_won,
    }
    for key, mask in masks.items():
        cells[key]["attempts"] = int(mask.sum())
        cells[key]["conversions"] = int(L.loc[mask, "scored"].sum())
    return finalize_cells(cells)


def finalize_cells(cells: dict) -> dict:
    for c in cells.values():
        c["rate"] = round(rate_pct(c["conversions"], c["attempts"]), 2)
    return cells


def proportion_block(att: int, conv: int) -> dict:
    if att == 0:
        return {"attempts": 0, "conversions": 0, "rate": 0.0, "ci_lo": None, "ci_hi": None}
    lo, hi = proportion_confint(conv, att, alpha=0.05, method="wilson")
    return {
        "attempts": att,
        "conversions": conv,
        "misses": att - conv,
        "rate": round(rate_pct(conv, att), 2),
        "ci_lo": round(float(lo) * 100, 2),
        "ci_hi": round(float(hi) * 100, 2),
    }


def mde_pp(p_control: float, n_t: int, n_c: int, power: float = 0.80, alpha: float = 0.05) -> float | None:
    """Smallest one-tailed drop (pp) below the control rate detectable at the given power."""
    for drop in np.arange(0.005, 0.5, 0.0005):
        es = proportion_effectsize(p_control, p_control - drop)
        if NormalIndPower().power(es, nobs1=n_t, alpha=alpha, ratio=n_c / n_t, alternative="larger") >= power:
            return round(float(drop) * 100, 2)
    return None


def primary_from_cells(cells: dict, label: str, code: str | None = None) -> dict:
    """One-tailed two-prop z-test: treatment (gk_won) vs control (gk_other + ngk_won + ngk_other)."""
    t_att = cells["gk_won"]["attempts"]
    t_conv = cells["gk_won"]["conversions"]
    c_att = sum(cells[k]["attempts"] for k in CONTROL_KEYS)
    c_conv = sum(cells[k]["conversions"] for k in CONTROL_KEYS)

    treatment = proportion_block(t_att, t_conv)
    control = proportion_block(c_att, c_conv)

    if t_att == 0 or c_att == 0:
        test = {
            "z_stat": None, "p_value": None,
            "significant_at_05": None, "rate_diff_pp": None,
            "alternative": "smaller (one-tailed)",
        }
    else:
        z, p = proportions_ztest([t_conv, c_conv], [t_att, c_att], alternative="smaller")
        d_lo, d_hi = confint_proportions_2indep(t_conv, t_att, c_conv, c_att, method="newcomb")
        test = {
            "z_stat": round(float(z), 4),
            "p_value": round(float(p), 6),
            "significant_at_05": bool(p < 0.05),
            "rate_diff_pp": round(treatment["rate"] - control["rate"], 4),
            "diff_ci_lo": round(float(d_lo) * 100, 2),   # Newcombe 95% CI, treatment − control, pp
            "diff_ci_hi": round(float(d_hi) * 100, 2),
            "alternative": "smaller (one-tailed)",
        }

    block = {
        "label": label,
        "treatment": treatment,
        "control": control,
        "test": test,
    }
    if code is not None:
        block["code"] = code
    return block


# ── Main ───────────────────────────────────────────────────
def main() -> None:
    print(f"Loading FULL_DICT_ROWS from {DATA_PATH} ...")
    full = load_pickle("FULL_DICT_ROWS")

    combined = build_combined_dicts(full)
    leagues = list(combined.keys())
    print(f"[OK] Combined dicts built for: {leagues}")

    loose_ids = {c: list(loose_pen_match_ids(df)) for c, df in combined.items()}
    loose_dfs = {c: df[df["match_id"].isin(loose_ids[c])] for c, df in combined.items()}

    # ── Descriptive (loose filter) ────────────────────────
    overall_att, overall_conv = 0, 0
    by_league = []
    for league in leagues:
        att, conv = attempts_conversions(loose_dfs[league])
        overall_att += att
        overall_conv += conv
        by_league.append({
            "code": league,
            "label": LEAGUE_LABELS.get(league, league),
            "attempts": att,
            "conversions": conv,
            "rate": round(rate_pct(conv, att), 2),
        })

    all_loose = pd.concat(loose_dfs.values(), ignore_index=True)
    season_summary = (
        all_loose.groupby("Season", as_index=False)
        .agg(attempts=("Performance_PKatt", "sum"), conversions=("Performance_PK", "sum"))
        .sort_values("Season")
    )
    by_season = [
        {
            "season": str(row.Season),
            "attempts": int(row.attempts),
            "conversions": int(row.conversions),
            "rate": round(rate_pct(int(row.conversions), int(row.attempts)), 2),
        }
        for row in season_summary.itertuples()
    ]

    # ── Penalty-level linkage ─────────────────────────────
    linked_parts, excluded = [], {k: 0 for k in EXCLUDE_REASONS}
    for league in leagues:
        part, why = link_penalties(combined[league], league)
        linked_parts.append(part)
        for k, v in why.items():
            excluded[k] += v
    L = pd.concat(linked_parts, ignore_index=True)
    n_linked = len(L)
    print(f"[OK] Linked {n_linked} of {overall_att} penalties; unlinked: {excluded}")

    # ── 2×2 matrix (linked penalties) ─────────────────────
    pooled_cells = cells_from_linked(L)
    per_league_cells = {league: cells_from_linked(L[L["league"] == league]) for league in leagues}

    matrix_block = {
        "rows": [
            {"key": "won",   "label": "Taker = the player who was fouled"},
            {"key": "other", "label": "Taker = not the fouled player (incl. handballs)"},
        ],
        "cols": [
            {"key": "gk",  "label": "Goalkeeper caused the foul"},
            {"key": "ngk", "label": "Outfielder caused the foul"},
        ],
        "cells": [
            {"row": "won",   "col": "gk",  "is_treatment": True,  **pooled_cells["gk_won"]},
            {"row": "other", "col": "gk",  "is_treatment": False, **pooled_cells["gk_other"]},
            {"row": "won",   "col": "ngk", "is_treatment": False, **pooled_cells["ngk_won"]},
            {"row": "other", "col": "ngk", "is_treatment": False, **pooled_cells["ngk_other"]},
        ],
    }

    # ── Primary test (one-tailed) ─────────────────────────
    primary = primary_from_cells(pooled_cells, "Top 5 (pooled)")
    primary["question"] = (
        "When the goalkeeper fouls the player who then takes the penalty, "
        "is the conversion rate lower than otherwise?"
    )
    primary["h0"] = "Treatment and control have the same conversion rate."
    primary["h1_alt"] = "Treatment conversion rate is LOWER than control (one-tailed)."
    primary["treatment"]["label"] = "GK fouled the taker (hurt-taker cell)"
    primary["control"]["label"] = "All other penalties (3 cells pooled)"
    primary["pooled"] = proportion_block(n_linked, int(L["scored"].sum()))
    t_blk, c_blk = primary["treatment"], primary["control"]
    primary["test"]["mde_pp"] = mde_pp(c_blk["conversions"] / c_blk["attempts"], t_blk["attempts"], c_blk["attempts"])

    primary_by_league = []
    for league in leagues:
        block = primary_from_cells(per_league_cells[league], LEAGUE_LABELS.get(league, league), code=league)
        primary_by_league.append(block)
    primary["by_league"] = primary_by_league
    t_by_league = [b["treatment"]["attempts"] for b in primary_by_league]

    # ── Payload ───────────────────────────────────────────
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "leagues": [{"code": c, "label": LEAGUE_LABELS.get(c, c)} for c in leagues],
            "seasons": [s["season"] for s in by_season],
            "n_matches_loose": sum(len(v) for v in loose_ids.values()),
            "n_penalties_total": overall_att,
            "n_linked": n_linked,
            "n_matches_linked": int(L["match_id"].nunique()),
            "linked_share_pct": round(n_linked / overall_att * 100, 1),
            "n_unlinked": overall_att - n_linked,
            "unlinked": {k: {"label": EXCLUDE_REASONS[k], "attempts": v} for k, v in excluded.items()},
            "treatment_n_by_league_min": min(t_by_league),
            "treatment_n_by_league_max": max(t_by_league),
            "filter_note": (
                "Descriptive stats (overall, by_league, by_season) use the loose filter — "
                "any match with a non-zero penalty event. The primary test and 2x2 matrix "
                "use linked penalties — one row per penalty whose taker, fouled player and "
                "conceder are unambiguous (the team took exactly one penalty in that match)."
            ),
        },
        "overall": {
            "attempts": overall_att,
            "conversions": overall_conv,
            "rate": round(rate_pct(overall_conv, overall_att), 2),
        },
        "by_league": by_league,
        "by_season": by_season,
        "primary": primary,
        "matrix": matrix_block,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"[OK] Wrote {OUTPUT_PATH.relative_to(PROJECT_DIR)} ({OUTPUT_PATH.stat().st_size/1024:.1f} KB)")

    # ── Console summary ──────────────────────────────────
    t = primary["treatment"]
    c = primary["control"]
    test = primary["test"]
    print("\n-- Primary test (one-tailed: treatment < control) --")
    print(f"  Treatment (GK fouled the taker):  {t['conversions']}/{t['attempts']} = {t['rate']}%  "
          f"95% CI [{t['ci_lo']}%, {t['ci_hi']}%]")
    print(f"  Control   (all other penalties):  {c['conversions']}/{c['attempts']} = {c['rate']}%  "
          f"95% CI [{c['ci_lo']}%, {c['ci_hi']}%]")
    print(f"  diff = {test['rate_diff_pp']:+.2f} pp  95% CI [{test['diff_ci_lo']:+.2f}, {test['diff_ci_hi']:+.2f}]   "
          f"z = {test['z_stat']:+.4f}   p (one-tailed) = {test['p_value']:.6f}   MDE(80%) = {test['mde_pp']} pp   "
          f"verdict: {'REJECT H0' if test['significant_at_05'] else 'fail to reject H0'}")
    print("\n-- Per-league primary test --")
    print(f"  {'league':<18} {'t_rate':>7} {'t_n':>5}   {'c_rate':>7} {'c_n':>5}   {'z':>8} {'p':>10}")
    for blk in primary_by_league:
        tt, cc, tst = blk["treatment"], blk["control"], blk["test"]
        z = "  n/a   " if tst["z_stat"]   is None else f"{tst['z_stat']:>+8.3f}"
        p = "   n/a    " if tst["p_value"] is None else f"{tst['p_value']:>10.4f}"
        print(f"  {blk['label']:<18} {tt['rate']:>7.2f} {tt['attempts']:>5}   "
              f"{cc['rate']:>7.2f} {cc['attempts']:>5}   {z} {p}")

    print("\n-- 2x2 matrix (linked penalties) --")
    for cell in matrix_block["cells"]:
        marker = "  <-- TREATMENT" if cell["is_treatment"] else ""
        print(f"  {cell['row']:>5} x {cell['col']:>4}:  "
              f"{cell['conversions']}/{cell['attempts']} = {cell['rate']:>5}%   ({cell['label']}){marker}")

    print(f"\nDescriptive overall (loose filter): {overall_conv}/{overall_att} = {payload['overall']['rate']}%")


if __name__ == "__main__":
    main()
