"""
build.py — Penalty conversion after a goalkeeper foul
─────────────────────────────────────────────────────

Loads FULL_DICT_ROWS from the local READY_DATA folder, combines the
SPECIALS + SUMMARY DataFrames per competition, restricts to clean
single-penalty matches, and writes every number needed by the dashboard
to ../data/data.json.

Primary test (one-tailed):
    Treatment = matches where the GK committed the foul AND the player
                who was fouled then took the penalty (the "hurt taker").
    Control   = every other penalty in the strict-filter universe.
    H0: conversion_treatment = conversion_control
    H1: conversion_treatment < conversion_control       (one-tailed)
    Test: statsmodels.proportions_ztest(alternative='smaller')
          + Wilson 95% CIs on each proportion

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

import pandas as pd
from statsmodels.stats.proportion import proportion_confint, proportions_ztest

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
    "gk_other":  "GK fouled, but a different player took the penalty",
    "ngk_won":   "Outfielder fouled, fouled player took the penalty",
    "ngk_other": "Outfielder fouled, a different player took the penalty",
}

CONTROL_KEYS = ["gk_other", "ngk_won", "ngk_other"]


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


def strict_pen_match_ids(df: pd.DataFrame):
    max_per_match = df.groupby("match_id")[PEN_COLS].max()
    return max_per_match[
        (max_per_match <= 1).all(axis=1) & (max_per_match > 0).any(axis=1)
    ].index


def rate_pct(conv: int, att: int) -> float:
    return (conv / att * 100.0) if att else 0.0


def attempts_conversions(df: pd.DataFrame) -> tuple[int, int]:
    return int(df["Performance_PKatt"].sum()), int(df["Performance_PK"].sum())


# ── Matrix + primary test helpers ──────────────────────────
def empty_cells() -> dict:
    return {k: {"label": v, "attempts": 0, "conversions": 0} for k, v in MATRIX_LABELS.items()}


def accumulate_cells_from_df(df: pd.DataFrame, cells: dict) -> None:
    """Walk one league's strict-filtered DataFrame and add to the 4 matrix cells."""
    for _mid, grp in df.groupby("match_id"):
        caused_by_gk = grp[(grp["Performance_PKcon"] == 1) & (grp["Pos"] == "GK")]
        not_caused_by_gk = grp[(grp["Performance_PKcon"] == 1) & (grp["Pos"] != "GK")]
        taker_won = grp[(grp["Performance_PKatt"] == 1) & (grp["Performance_PKwon"] == 1)]
        taker_not_won = grp[(grp["Performance_PKatt"] == 1) & (grp["Performance_PKwon"] == 0)]

        if not caused_by_gk.empty and not taker_won.empty:
            cells["gk_won"]["attempts"] += len(taker_won)
            cells["gk_won"]["conversions"] += int(taker_won["Performance_PK"].sum())
        if not caused_by_gk.empty and not taker_not_won.empty:
            cells["gk_other"]["attempts"] += len(taker_not_won)
            cells["gk_other"]["conversions"] += int(taker_not_won["Performance_PK"].sum())
        if not not_caused_by_gk.empty and not taker_won.empty:
            cells["ngk_won"]["attempts"] += len(taker_won)
            cells["ngk_won"]["conversions"] += int(taker_won["Performance_PK"].sum())
        if not not_caused_by_gk.empty and not taker_not_won.empty:
            cells["ngk_other"]["attempts"] += len(taker_not_won)
            cells["ngk_other"]["conversions"] += int(taker_not_won["Performance_PK"].sum())


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
        "rate": round(rate_pct(conv, att), 2),
        "ci_lo": round(float(lo) * 100, 2),
        "ci_hi": round(float(hi) * 100, 2),
    }


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
        test = {
            "z_stat": round(float(z), 4),
            "p_value": round(float(p), 6),
            "significant_at_05": bool(p < 0.05),
            "rate_diff_pp": round(treatment["rate"] - control["rate"], 4),
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

    strict_ids = {c: list(strict_pen_match_ids(df)) for c, df in combined.items()}
    strict_dfs = {c: df[df["match_id"].isin(strict_ids[c])] for c, df in combined.items()}

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

    # ── 2×2 matrix (strict filter) ────────────────────────
    pooled_cells = empty_cells()
    per_league_cells: dict[str, dict] = {}
    for league in leagues:
        league_cells = empty_cells()
        accumulate_cells_from_df(strict_dfs[league], league_cells)
        finalize_cells(league_cells)
        per_league_cells[league] = league_cells
        accumulate_cells_from_df(strict_dfs[league], pooled_cells)
    finalize_cells(pooled_cells)

    matrix_block = {
        "rows": [
            {"key": "won",   "label": "Taker = the player who was fouled"},
            {"key": "other", "label": "Taker = a different player"},
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

    primary_by_league = []
    for league in leagues:
        block = primary_from_cells(per_league_cells[league], LEAGUE_LABELS.get(league, league), code=league)
        primary_by_league.append(block)
    primary["by_league"] = primary_by_league

    # ── Payload ───────────────────────────────────────────
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "leagues": [{"code": c, "label": LEAGUE_LABELS.get(c, c)} for c in leagues],
            "seasons": [s["season"] for s in by_season],
            "n_matches_loose": sum(len(v) for v in loose_ids.values()),
            "n_matches_strict": sum(len(v) for v in strict_ids.values()),
            "filter_note": (
                "Descriptive stats (overall, by_league, by_season) use the loose filter — "
                "any match with a non-zero penalty event. The primary test and 2x2 matrix "
                "use the strict filter — matches where every penalty column has max <= 1, "
                "i.e. single-penalty matches with unambiguous attribution."
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
    print(f"  diff = {test['rate_diff_pp']:+.2f} pp   z = {test['z_stat']:+.4f}   "
          f"p (one-tailed) = {test['p_value']:.6f}   "
          f"verdict: {'REJECT H0' if test['significant_at_05'] else 'fail to reject H0'}")

    print("\n-- Per-league primary test --")
    print(f"  {'league':<18} {'t_rate':>7} {'t_n':>5}   {'c_rate':>7} {'c_n':>5}   {'z':>8} {'p':>10}")
    for blk in primary_by_league:
        tt, cc, tst = blk["treatment"], blk["control"], blk["test"]
        z = "  n/a   " if tst["z_stat"]   is None else f"{tst['z_stat']:>+8.3f}"
        p = "   n/a    " if tst["p_value"] is None else f"{tst['p_value']:>10.4f}"
        print(f"  {blk['label']:<18} {tt['rate']:>7.2f} {tt['attempts']:>5}   "
              f"{cc['rate']:>7.2f} {cc['attempts']:>5}   {z} {p}")

    print("\n-- 2x2 matrix (strict universe) --")
    for cell in matrix_block["cells"]:
        marker = "  <-- TREATMENT" if cell["is_treatment"] else ""
        print(f"  {cell['row']:>5} x {cell['col']:>4}:  "
              f"{cell['conversions']}/{cell['attempts']} = {cell['rate']:>5}%   ({cell['label']}){marker}")

    print(f"\nDescriptive overall (loose filter): {overall_conv}/{overall_att} = {payload['overall']['rate']}%")


if __name__ == "__main__":
    main()
