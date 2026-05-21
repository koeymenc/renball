"""
build.py — Renball Project 02 (Points by Gamestate) build orchestrator
======================================================================

Black-box wrapper around the v3 Points-by-Gamestate pipeline.

What it does:
  1. Loads the per-league match-event pickles from RENBALL_MATCH_DATA_PATH.
  2. Runs the v3 analysis (per-league + pooled, untimed + timed).
  3. Writes TWO JSON artefacts:
       - data/data.json              -> small payload for analysis.html
                                        (editorial page: stat callouts +
                                         5 headline visuals, pooled-only).
       - data/dashboard_payload.json -> full Tabulator payload for
                                        dashboard.html (datasets x views x
                                        leagues x seasons, with drill-down).

The math is unchanged from the source pipeline (config.py, extraction.py,
analysis.py, dashboard.py). This script only handles path config and
JSON serialisation.

Run:
    python code/build.py
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Make sibling modules importable when run as `python code/build.py`
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from config import DATA_DIR, BIN_UNKNOWN, TIME_BINS, MIN_GD, MAX_GD
from extraction import load_leagues, build_goal_event_dataset, _clean_player_name


# ════════════════════════════════════════════════════════════════════════
# Player-minutes pipeline (FULL_DICT_ROWS.pkl in RENBALL_DATA_PATH)
# ════════════════════════════════════════════════════════════════════════
# FULL_DICT_ROWS was pickled under pandas <2 — the pandas.core.indexes.numeric
# module has since been removed. Provide a shim so the pickle still loads.
def _install_pandas_pickle_shim():
    if "pandas.core.indexes.numeric" in sys.modules:
        return
    import pandas.core.indexes.base as _base
    class _Stub:
        Int64Index = _base.Index
        UInt64Index = _base.Index
        Float64Index = _base.Index
        NumericIndex = _base.Index
    sys.modules["pandas.core.indexes.numeric"] = _Stub()


def load_player_minutes(default_data_path: str = r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA") -> dict:
    """
    Returns a dict {cleaned_contributor_name -> total_minutes} pooled across
    all (competition, season) in FULL_DICT_ROWS.pkl. Top-5 leagues only —
    Eredivisie is not in this pickle, so Eredivisie-only players have no
    minutes record and are filtered out of the per-90 leaderboard.
    """
    data_path = Path(os.environ.get("RENBALL_DATA_PATH", default_data_path))
    pkl = data_path / "FULL_DICT_ROWS.pkl"
    if not pkl.exists():
        print(f"  [minutes] FULL_DICT_ROWS.pkl not found at {pkl}, skipping per-90 build")
        return {}

    _install_pandas_pickle_shim()
    with open(pkl, "rb") as f:
        full = pickle.load(f)

    rows = []
    for comp, sections in full.items():
        summary = sections.get("ROWS_DICTS_SUMMARY")
        if not isinstance(summary, dict):
            continue
        for season, df in summary.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            if "Player" not in df.columns or "Min" not in df.columns:
                continue
            sub = df[["Player", "Min"]].copy()
            sub["contributor"] = sub["Player"].apply(_clean_player_name)
            sub["Min"] = pd.to_numeric(sub["Min"], errors="coerce").fillna(0)
            rows.append(sub[["contributor", "Min"]])

    if not rows:
        return {}

    all_rows = pd.concat(rows, ignore_index=True)
    all_rows = all_rows[all_rows["contributor"].notna()]
    grouped = (all_rows.groupby("contributor", as_index=False)["Min"]
                       .sum()
                       .rename(columns={"Min": "minutes_played"}))
    return dict(zip(grouped["contributor"].astype(str),
                    grouped["minutes_played"].astype(float)))
from analysis import (
    build_pre_goal_state_rows,
    state_summary,
    state_summary_timed,
    transition_summary,
    transition_summary_timed,
    prep_transitions,
    prep_transitions_timed,
    prep_value_map,
    prep_value_map_timed,
    build_heatmap_table,
    build_contributor_tables,
    build_goals_plus_assists_tables,
    aggregate_tables,
)
from dashboard import build_payload


# ════════════════════════════════════════════════════════════════════════
# Output paths
# ════════════════════════════════════════════════════════════════════════
DATA_DIR_OUT = PROJECT_DIR / "data"
DATA_JSON = DATA_DIR_OUT / "data.json"
DASHBOARD_DIR = DATA_DIR_OUT / "dashboard"
DASHBOARD_MANIFEST = DASHBOARD_DIR / "manifest.json"

# Dataset key -> subfolder name under data/dashboard/. Each view of a
# dataset becomes its own JSON file inside the subfolder, so a (dataset,
# view) pair maps to one fetch. The manifest is the authoritative index.
DATASET_DIRS = {
    "Goalscorer":          "goalscorer",
    "Assist":              "assist",
    "Goals+Assists":       "goals_assists",
    "Transitions":         "transitions",
    "Transitions (Timed)": "transitions_timed",
    "Transition Heatmap":  "heatmap",
}


def _slug(s: str) -> str:
    """Filesystem-safe lowercase slug for view names. 'Per League & Season' -> 'per_league_season'."""
    out = []
    prev_us = False
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        elif not prev_us:
            out.append("_")
            prev_us = True
    return "".join(out).strip("_")

# Columns whose values must never be dropped by sparse encoding
# (string identifiers + the universally-displayed numeric base columns).
# pW/pD/pL are kept because a missing probability column reads as "no data"
# in the dashboard, but in reality 0 is a valid value (e.g. pW at gd=-7).
SPARSE_KEEP_KEYS = {
    "scoring_team", "contributor", "minute_bin",
    "gd_before", "gd_after",
    "goals_involved",
    "exp_points_collected_timed",
    "exp_points_collected_untimed",
    "exp_points_collected",
    "exp_points",
    "pW", "pD", "pL",
    "n",
    # Minutes-played + per-90 (added in v3.1) — always preserve, 0 is a valid value
    "minutes_played", "ep_per_90",
}

# Columns dropped from the payload because they are pure functions of base
# columns; the dashboard JS recomputes them at render time. Saves ~700 KB
# per Goals+Assists view (3 columns × thousands of rows × ~30 chars/cell).
DERIVED_DROP = {
    "delta_ep_timed_vs_untimed",   # = exp_points_collected_timed - exp_points_collected_untimed
    "delta_ep_minus_goals",        # = exp_points_collected_timed - goals_involved
    "ratio_ep_per_goal",           # = exp_points_collected_timed / goals_involved
}

# Datasets where contributor-table column-name shortening applies. Transition
# / heatmap views use entirely different columns and stay unmodified.
_CONTRIB_DATASETS = {"Goalscorer", "Assist", "Goals+Assists"}

# Sparse-column rename scheme. Manifest exposes the mapping so dashboard.js
# can reconstruct full column names for display.
#   cnt_<gd_before>_to_<gd_after>  -> g.<gd_before>.<gd_after>
#   cnt_bin_<bin>                  -> b.<bin>
#   ep_bin_<bin>                   -> e.<bin>
KEY_SCHEME = {
    "cnt_gd_prefix":  "g.",   # short prefix for cnt_X_to_Y
    "cnt_bin_prefix": "b.",   # short prefix for cnt_bin_X
    "ep_bin_prefix":  "e.",
}


def _shorten_key(k: str) -> str:
    if k.startswith("cnt_bin_"):
        return KEY_SCHEME["cnt_bin_prefix"] + k[len("cnt_bin_"):]
    if k.startswith("ep_bin_"):
        return KEY_SCHEME["ep_bin_prefix"] + k[len("ep_bin_"):]
    if k.startswith("cnt_") and "_to_" in k:
        # cnt_-1_to_0  ->  g.-1.0
        body = k[len("cnt_"):]
        before, after = body.split("_to_")
        return KEY_SCHEME["cnt_gd_prefix"] + f"{before}.{after}"
    return k


# ════════════════════════════════════════════════════════════════════════
# JSON helpers (numpy-safe, NaN -> None)
# ════════════════════════════════════════════════════════════════════════
def _py(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        x = float(v)
        return None if np.isnan(x) else x
    if isinstance(v, float):
        return None if np.isnan(v) else v
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    return v


def _round(x, n=4):
    v = _py(x)
    return None if v is None else round(float(v), n)


def _write_json(path: Path, obj, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"ensure_ascii": False, "default": str}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, **kwargs)
    size_kb = path.stat().st_size / 1024
    rel = path.relative_to(PROJECT_DIR)
    if size_kb >= 1024:
        print(f"  Wrote {rel} ({size_kb / 1024:,.1f} MB)")
    else:
        print(f"  Wrote {rel} ({size_kb:,.1f} KB)")


def _round_floats_in_records(obj, ndigits: int = 3):
    """
    Walk the dashboard payload and round every float to ndigits in-place.
    Trims raw-data string length by ~50% with no perceptible precision loss
    for EP values that are O(1) and probabilities in [0, 1].
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, float):
                obj[k] = round(v, ndigits)
            elif isinstance(v, (dict, list)):
                _round_floats_in_records(v, ndigits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, float):
                obj[i] = round(v, ndigits)
            elif isinstance(v, (dict, list)):
                _round_floats_in_records(v, ndigits)


def _sparsify_row(row: dict, *, contributor: bool) -> dict:
    """
    Sparse encoding for one record:
      - drop keys in DERIVED_DROP (contributor tables only — recomputed in JS)
      - drop keys with numeric-zero or None values, except SPARSE_KEEP_KEYS
      - shorten cnt_*/ep_bin_*/cnt_bin_* keys per KEY_SCHEME (contributor only)
    """
    out = {}
    for k, v in row.items():
        if contributor and k in DERIVED_DROP:
            continue
        if k in SPARSE_KEEP_KEYS:
            out[k] = v
            continue
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = v
            continue
        if isinstance(v, (int, float)) and v == 0:
            continue
        out_k = _shorten_key(k) if contributor else k
        out[out_k] = v
    return out


def _sparsify_records(records: list, *, contributor: bool) -> list:
    return [_sparsify_row(r, contributor=contributor) for r in records]


def _sparsify_view(view, *, contributor: bool):
    """
    Walk one dataset's view container. The Tabulator payload uses three
    shapes per view (see dashboard.build_payload):
      - list[record]                              (rare)
      - {key: list[record]}                       (Totals by League / Season / All / Pooled)
      - {league: {season: list[record]}}          (Per League & Season — nested)
    """
    if isinstance(view, list):
        return _sparsify_records(view, contributor=contributor)
    if isinstance(view, dict):
        out = {}
        for k, v in view.items():
            if isinstance(v, list):
                out[k] = _sparsify_records(v, contributor=contributor)
            elif isinstance(v, dict):
                inner = {}
                for k2, v2 in v.items():
                    if isinstance(v2, list):
                        inner[k2] = _sparsify_records(v2, contributor=contributor)
                    else:
                        inner[k2] = v2
                out[k] = inner
            else:
                out[k] = v
        return out
    return view


def _write_dashboard_files(payload: dict) -> None:
    """
    Split the Tabulator payload into one JSON file per (dataset, view),
    grouped into a subfolder per dataset, plus a manifest at the root.
    Each file is compact-JSON, 3dp-rounded, sparse-encoded.

    Layout:
      data/dashboard/manifest.json
      data/dashboard/<dataset_slug>/<view_slug>.json
    """
    # Wipe any stale per-dataset flat files from the earlier shape.
    if DASHBOARD_DIR.exists():
        for stale in DASHBOARD_DIR.glob("*.json"):
            if stale.name != "manifest.json":
                stale.unlink()

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    # Round once across the whole payload (saves repeating per dataset).
    _round_floats_in_records(payload, ndigits=3)

    manifest = {
        "meta": dict(payload.get("meta", {})),
        "columnHelp": payload.get("columnHelp", {}),
        "always_keep": sorted(SPARSE_KEEP_KEYS),
        "derived_columns": sorted(DERIVED_DROP),
        "key_scheme": KEY_SCHEME,
        "datasets": {},
    }

    oversize = []  # (display_label, MB) for any view > 5 MB

    for ds_name, ds_slug in DATASET_DIRS.items():
        if ds_name not in payload["datasets"]:
            continue
        is_contrib = ds_name in _CONTRIB_DATASETS
        ds_dir = DASHBOARD_DIR / ds_slug
        ds_dir.mkdir(parents=True, exist_ok=True)

        view_entries = {}
        for view_name, container in payload["datasets"][ds_name].items():
            sparse = _sparsify_view(container, contributor=is_contrib)
            view_slug = _slug(view_name)
            out_path = ds_dir / f"{view_slug}.json"
            _write_json(out_path, sparse, compact=True)

            size_kb = round(out_path.stat().st_size / 1024, 1)
            rel_file = f"{ds_slug}/{view_slug}.json"
            view_entries[view_name] = {"file": rel_file, "size_kb": size_kb}
            if size_kb > 5 * 1024:
                oversize.append((f"{ds_name} / {view_name}", size_kb / 1024))

        manifest["datasets"][ds_name] = {
            "contributor": is_contrib,
            "views": view_entries,
        }

    _write_json(DASHBOARD_MANIFEST, manifest)  # pretty manifest is small

    # Hard guard: warn if any view file crosses the 5 MB committable threshold.
    if oversize:
        print("  WARNING: dashboard view files over 5 MB (see CLAUDE.md §9):")
        for name, mb in oversize:
            print(f"    {name}: {mb:.1f} MB")
    else:
        # Roll-up so the user sees the structure took shape correctly.
        total = sum(v["size_kb"]
                    for ds in manifest["datasets"].values()
                    for v in ds["views"].values())
        n_views = sum(len(ds["views"]) for ds in manifest["datasets"].values())
        print(f"  OK: {n_views} view files, total {total / 1024:.1f} MB, all < 5 MB.")


# ════════════════════════════════════════════════════════════════════════
# Editorial payload builders
# ════════════════════════════════════════════════════════════════════════
def _gd_range():
    return list(range(MIN_GD, MAX_GD + 1))


def build_state_value_table(state_vals_timed: pd.DataFrame) -> dict:
    """
    State Value Table — expected final points at each (gd_before, time_bin).
    Shape: rows = gd in [MIN_GD, MAX_GD], cols = TIME_BINS.
    Cell = {"exp_points": float, "n": int} or None if missing.
    """
    gds = _gd_range()
    bins = list(TIME_BINS)

    if state_vals_timed is None or state_vals_timed.empty:
        return {"gd_range": gds, "time_bins": bins, "matrix": []}

    df = state_vals_timed[state_vals_timed["minute_bin"] != BIN_UNKNOWN].copy()
    lookup = {(int(r.gd), r.minute_bin): (float(r.exp_points), int(r.n))
              for r in df.itertuples(index=False)}

    matrix = []
    for gd in gds:
        row = []
        for b in bins:
            hit = lookup.get((gd, b))
            if hit is None:
                row.append(None)
            else:
                row.append({"exp_points": round(hit[0], 4), "n": hit[1]})
        matrix.append(row)

    return {"gd_range": gds, "time_bins": bins, "matrix": matrix}


def build_value_heatmap(transitions_timed_prepped: pd.DataFrame) -> dict:
    """
    EP value heatmap — for each (gd_before -> gd_after) transition kept in
    KEEP_SET (one-step), show ep_collected by time_bin.
    Cell = {"ep_collected": float, "n": int}.
    """
    bins = list(TIME_BINS)
    if transitions_timed_prepped is None or transitions_timed_prepped.empty:
        return {"time_bins": bins, "transitions": [], "matrix": []}

    df = transitions_timed_prepped.copy()
    df["gd_before"] = df["gd_before"].astype(int)
    df["gd_after"] = df["gd_after"].astype(int)

    pairs = sorted({(int(r.gd_before), int(r.gd_after)) for r in df.itertuples(index=False)},
                   key=lambda p: p[0])

    lookup = {(int(r.gd_before), int(r.gd_after), r.minute_bin):
              (float(r.exp_points_collected), int(r.n))
              for r in df.itertuples(index=False)}

    def _arrow(gd):  # use a thin minus for negative numbers
        return f"{gd}".replace("-", "−")

    transitions = [
        {
            "gd_before": gb,
            "gd_after": ga,
            "label": f"{_arrow(gb)}→{_arrow(ga)}",
        }
        for (gb, ga) in pairs
    ]

    matrix = []
    for (gb, ga) in pairs:
        row = []
        for b in bins:
            hit = lookup.get((gb, ga, b))
            if hit is None:
                row.append(None)
            else:
                row.append({"ep_collected": round(hit[0], 4), "n": hit[1]})
        matrix.append(row)

    return {"time_bins": bins, "transitions": transitions, "matrix": matrix}


def build_early_vs_late_0to1(val_map_timed: dict) -> dict:
    """
    Early-vs-late 0->1 — EP collected from a 0->1 goal in each time bin.
    """
    bins = list(TIME_BINS)
    series = [val_map_timed.get((0, 1, b)) for b in bins]
    return {
        "time_bins": bins,
        "ep_collected": [_round(v, 4) for v in series],
    }


def _pool_by_contributor(total_all: pd.DataFrame,
                         minutes_by_player: dict | None = None) -> pd.DataFrame:
    """
    Re-pool the (scoring_team, contributor) totals to one row per
    contributor. Picks the primary team (most goals_involved) as the
    representative team label.

    `minutes_played` / `ep_per_90` are player-level (not team-level) so they
    must NOT be summed across the (team, contributor) rows of a player who
    moved teams. They're attached from the pooled `minutes_by_player` lookup
    AFTER the groupby.

    Drops "Unknown" — those are FBref shot rows where the goalscorer/SCA1
    string couldn't be parsed by extraction._clean_player_name (~2,250 events
    of the goalscorer table; mostly own-goals, fragmented entries, etc.).
    They aggregate to a fake "player" who would otherwise top the leaderboards.
    """
    if total_all is None or total_all.empty:
        return pd.DataFrame()

    df = total_all.copy()
    df["contributor"] = df["contributor"].fillna("Unknown").astype(str)
    df = df[df["contributor"].str.strip().str.lower() != "unknown"]

    # Primary team = team with most goals_involved for this player
    primary = (
        df.sort_values("goals_involved", ascending=False)
          .drop_duplicates("contributor", keep="first")[["contributor", "scoring_team"]]
          .rename(columns={"scoring_team": "primary_team"})
    )

    sum_cols = [
        "goals_involved",
        "exp_points_collected_timed",
        "exp_points_collected_untimed",
        "delta_ep_timed_vs_untimed",
    ]
    # Also carry through per-bin EP columns so downstream callers can build
    # the top-10-by-bin table without a second pass.
    ep_bin_cols = [c for c in df.columns if c.startswith("ep_bin_")]
    sum_cols = [c for c in sum_cols + ep_bin_cols if c in df.columns]
    # Strip player-level columns so the sum across (team, contributor) doesn't
    # double-count them when the player moved teams.
    sum_cols = [c for c in sum_cols if c not in {"minutes_played", "ep_per_90"}]

    pooled = df.groupby("contributor", as_index=False)[sum_cols].sum()
    pooled = pooled.merge(primary, on="contributor", how="left")

    if minutes_by_player is not None:
        pooled["minutes_played"] = (
            pooled["contributor"].map(minutes_by_player).fillna(0).astype(int)
        )
        ep = pooled["exp_points_collected_timed"].astype(float)
        mins = pooled["minutes_played"].astype(float)
        pooled["ep_per_90"] = np.where(mins > 0, (ep / mins) * 90.0, 0.0).round(3)

    return pooled


# Top-5 European leagues (used to scope the per-90 leaderboard so that
# Eredivisie goals don't compete against minutes-played sourced only from
# the Top-5 FULL_DICT_ROWS.pkl).
_TOP5_LEAGUES = {"Premier-League", "Serie-A", "Bundesliga", "La-Liga", "Ligue-1"}


def _ga_total_top5(ga_totals: tuple) -> pd.DataFrame:
    """
    Per-(team, contributor) rows pooled across Top-5 leagues only. Used as
    the input to the EP-per-90 leaderboard so a player's `ep_timed` and
    their `minutes_played` cover the same set of leagues.
    """
    by_league = ga_totals[0] if ga_totals else {}
    parts = [df.copy() for lg, df in by_league.items()
             if lg in _TOP5_LEAGUES and isinstance(df, pd.DataFrame) and not df.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _ep_bins_for_row(row: pd.Series) -> dict:
    """Pull ep_bin_<bin> values out of a pooled row as a {bin: value} dict."""
    return {b: _round(row.get(f"ep_bin_{b}"), 3) for b in TIME_BINS}


def build_top10_ep(ga_total_all: pd.DataFrame, top_n: int = 10) -> list:
    pooled = _pool_by_contributor(ga_total_all)
    if pooled.empty or "exp_points_collected_timed" not in pooled.columns:
        return []
    pooled = pooled.sort_values("exp_points_collected_timed", ascending=False).head(top_n)
    out = []
    for _, r in pooled.iterrows():
        out.append({
            "player": r["contributor"],
            "team": r["primary_team"],
            "goals_involved": int(r["goals_involved"]),
            "ep_timed": _round(r["exp_points_collected_timed"], 3),
            "ep_untimed": _round(r["exp_points_collected_untimed"], 3),
            "ep_bins": _ep_bins_for_row(r),
        })
    return out


def build_top10_ep_per_90(ga_total_top5: pd.DataFrame, minutes_by_player: dict,
                          *, top_n: int = 10, min_minutes: int = 900) -> list:
    """
    Top players by EP collected per 90 minutes played (Goals + Assists,
    Top-5 leagues only — both `ep_timed` and `minutes_played` scoped the same
    way). Players with < min_minutes minutes are filtered out.
    """
    if ga_total_top5 is None or ga_total_top5.empty or not minutes_by_player:
        return []
    pooled = _pool_by_contributor(ga_total_top5, minutes_by_player=minutes_by_player)
    if pooled.empty or "ep_per_90" not in pooled.columns:
        return []
    pooled = pooled[pooled["minutes_played"] >= min_minutes]
    if pooled.empty:
        return []
    pooled = pooled.sort_values("ep_per_90", ascending=False).head(top_n)
    return [
        {
            "player": r["contributor"],
            "team": r["primary_team"],
            "goals_involved": int(r["goals_involved"]),
            "minutes_played": int(r["minutes_played"]),
            "ep_timed": _round(r["exp_points_collected_timed"], 3),
            "ep_per_90": _round(r["ep_per_90"], 3),
        }
        for _, r in pooled.iterrows()
    ]


def build_top10_ep_collectors_with_minutes(ga_total_all: pd.DataFrame,
                                           minutes_by_player: dict,
                                           top_n: int = 10) -> list:
    """
    Top-10 by total EP collected (across all six leagues), enriched with
    minutes_played and ep_per_90 from the pooled Top-5 minutes lookup.
    For players whose career in scope falls entirely outside the Top-5
    (Eredivisie-only), ep_per_90 is None.
    """
    if ga_total_all is None or ga_total_all.empty:
        return []
    pooled = _pool_by_contributor(ga_total_all, minutes_by_player=minutes_by_player)
    if pooled.empty or "exp_points_collected_timed" not in pooled.columns:
        return []
    pooled = pooled.sort_values("exp_points_collected_timed", ascending=False).head(top_n)
    out = []
    for _, r in pooled.iterrows():
        mins = int(r.get("minutes_played", 0))
        ep_per_90 = _round(r.get("ep_per_90"), 3) if mins > 0 else None
        out.append({
            "player": r["contributor"],
            "team": r["primary_team"],
            "goals_involved": int(r["goals_involved"]),
            "minutes_played": mins if mins > 0 else None,
            "ep_timed": _round(r["exp_points_collected_timed"], 3),
            "ep_per_90": ep_per_90,
        })
    return out


def build_top10_upgrade(ga_total_all: pd.DataFrame, top_n: int = 10,
                        min_goals: int = 5) -> list:
    """
    Top players upgraded by the time-aware re-rating
    (largest positive delta_ep_timed_vs_untimed). Min-goals threshold
    keeps the list meaningful (single-late-goal flukes filtered).
    """
    pooled = _pool_by_contributor(ga_total_all)
    if pooled.empty or "delta_ep_timed_vs_untimed" not in pooled.columns:
        return []
    pooled = pooled[pooled["goals_involved"] >= min_goals]
    pooled = pooled.sort_values("delta_ep_timed_vs_untimed", ascending=False).head(top_n)
    return [
        {
            "player": r.contributor,
            "team": r.primary_team,
            "goals_involved": int(r.goals_involved),
            "ep_timed": _round(r.exp_points_collected_timed, 3),
            "ep_untimed": _round(r.exp_points_collected_untimed, 3),
            "delta_ep": _round(r.delta_ep_timed_vs_untimed, 3),
        }
        for r in pooled.itertuples(index=False)
    ]


def build_callouts(goal_events_all: pd.DataFrame,
                   state_vals_timed: pd.DataFrame,
                   val_map_timed: dict,
                   ga_total_all: pd.DataFrame) -> dict:
    """
    Four headline numbers:
      - total_goals
      - unique_states (count of (gd × time_bin) cells with data)
      - ep_value_gap (most valuable transition - least valuable, with labels)
      - biggest_upgrade (player with largest positive delta_ep_timed_vs_untimed)
    """
    # 1. Total goals (excluding unknown-bin if you wanted to, but headline = all)
    total_goals = int(len(goal_events_all))

    # 2. Unique modelled states
    unique_states = 0
    if state_vals_timed is not None and not state_vals_timed.empty:
        unique_states = int(
            state_vals_timed[state_vals_timed["minute_bin"] != BIN_UNKNOWN].shape[0]
        )

    # 3. EP value gap — across the value map (gd_before, gd_after, bin)
    gap = {"gap": None, "best": None, "worst": None,
           "best_label": None, "worst_label": None}
    if val_map_timed:
        items = [(k, v) for k, v in val_map_timed.items() if v is not None]
        if items:
            best_k, best_v = max(items, key=lambda kv: kv[1])
            worst_k, worst_v = min(items, key=lambda kv: kv[1])

            def _lbl(k):
                gb, ga, b = k
                arr = lambda x: f"{x}".replace("-", "−")
                return f"{arr(gb)}→{arr(ga)} @ {b}"

            gap = {
                "gap": round(float(best_v - worst_v), 4),
                "best": round(float(best_v), 4),
                "worst": round(float(worst_v), 4),
                "best_label": _lbl(best_k),
                "worst_label": _lbl(worst_k),
            }

    # 4. Biggest player upgrade
    upgrade = None
    pooled = _pool_by_contributor(ga_total_all)
    if not pooled.empty and "delta_ep_timed_vs_untimed" in pooled.columns:
        # apply same min-goals threshold for meaningful headline
        filt = pooled[pooled["goals_involved"] >= 5]
        if not filt.empty:
            top = filt.sort_values("delta_ep_timed_vs_untimed", ascending=False).iloc[0]
            upgrade = {
                "player": str(top["contributor"]),
                "team": str(top["primary_team"]),
                "goals_involved": int(top["goals_involved"]),
                "delta_ep": round(float(top["delta_ep_timed_vs_untimed"]), 3),
                "ep_timed": round(float(top["exp_points_collected_timed"]), 3),
                "ep_untimed": round(float(top["exp_points_collected_untimed"]), 3),
            }

    return {
        "total_goals": total_goals,
        "unique_states": unique_states,
        "ep_value_gap": gap,
        "biggest_upgrade": upgrade,
    }


# ════════════════════════════════════════════════════════════════════════
# Pipeline (mirrors main.py, no exports / no inline HTML write)
# ════════════════════════════════════════════════════════════════════════
def run_pipeline():
    print(f"[1/6] Loading data from: {DATA_DIR}")
    all_leagues = load_leagues(DATA_DIR)

    print("\n[2/6] Per-league analysis...")
    results = {}
    for league, league_data in all_leagues.items():
        goal_events, _debug = build_goal_event_dataset(league_data)

        # Untimed
        pre_states = build_pre_goal_state_rows(goal_events)
        state_vals = state_summary(pre_states)
        transitions = transition_summary(goal_events, state_vals=state_vals)

        # Timed
        pre_states_t = build_pre_goal_state_rows(goal_events, carry_minute_bin=True)
        state_vals_t = state_summary_timed(pre_states_t)
        transitions_t = transition_summary_timed(goal_events, state_vals_timed=state_vals_t)

        results[league] = {
            "goal_events": goal_events,
            "state_vals": state_vals,
            "transitions": transitions,
            "state_vals_timed": state_vals_t,
            "transitions_timed": transitions_t,
        }
        print(f"  {league}: goals={len(goal_events):,}  "
              f"transitions={len(transitions):,}  "
              f"timed={len(transitions_t):,}")

    print("\n[3/6] Pooled analysis...")
    goal_events_all = pd.concat(
        [d["goal_events"].assign(league=lg)
         for lg, d in results.items() if not d["goal_events"].empty],
        ignore_index=True,
    )

    pre_states_pooled = build_pre_goal_state_rows(goal_events_all)
    state_vals_pooled = state_summary(pre_states_pooled)
    transitions_pooled = transition_summary(goal_events_all, state_vals=state_vals_pooled)

    pre_states_pooled_t = build_pre_goal_state_rows(goal_events_all, carry_minute_bin=True)
    state_vals_pooled_t = state_summary_timed(pre_states_pooled_t)
    transitions_pooled_t = transition_summary_timed(goal_events_all,
                                                    state_vals_timed=state_vals_pooled_t)

    print(f"  Total goals: {len(goal_events_all):,}")

    transitions_pooled_f = prep_transitions(transitions_pooled)
    transitions_by_league_f = {
        lg: prep_transitions(d["transitions"])
        for lg, d in results.items()
        if isinstance(d.get("transitions"), pd.DataFrame) and not d["transitions"].empty
    }

    transitions_pooled_timed_f = prep_transitions_timed(transitions_pooled_t)
    transitions_by_league_timed_f = {
        lg: prep_transitions_timed(d["transitions_timed"])
        for lg, d in results.items()
        if isinstance(d.get("transitions_timed"), pd.DataFrame) and not d["transitions_timed"].empty
    }

    val_map_untimed = prep_value_map(transitions_pooled)
    val_map_timed = prep_value_map_timed(transitions_pooled_t)

    heatmap_pooled = build_heatmap_table(transitions_pooled_timed_f)
    heatmap_by_league = {lg: build_heatmap_table(df)
                         for lg, df in transitions_by_league_timed_f.items()}

    print("\n[4/6] Building contributor tables...")
    scorer_tables = build_contributor_tables(results, val_map_untimed, val_map_timed, "goalscorer")
    sca1_tables = build_contributor_tables(results, val_map_untimed, val_map_timed, "sca1_creator")
    ga_tables = build_goals_plus_assists_tables(scorer_tables, sca1_tables)

    print("\n[5/6] Aggregating totals...")
    scorer_totals = aggregate_tables(scorer_tables)
    sca1_totals = aggregate_tables(sca1_tables)
    ga_totals = aggregate_tables(ga_tables)

    return {
        "goal_events_all": goal_events_all,
        "state_vals_pooled_t": state_vals_pooled_t,
        "transitions_pooled_timed_f": transitions_pooled_timed_f,
        "val_map_timed": val_map_timed,
        "scorer_tables": scorer_tables,
        "sca1_tables": sca1_tables,
        "ga_tables": ga_tables,
        "scorer_totals": scorer_totals,
        "sca1_totals": sca1_totals,
        "ga_totals": ga_totals,
        "transitions_pooled_f": transitions_pooled_f,
        "transitions_by_league_f": transitions_by_league_f,
        "transitions_pooled_timed_full": transitions_pooled_timed_f,
        "transitions_by_league_timed_f": transitions_by_league_timed_f,
        "heatmap_pooled": heatmap_pooled,
        "heatmap_by_league": heatmap_by_league,
        "results": results,
    }


def _attach_minutes_to_contributor_tables(ctx: dict, minutes_by_player: dict) -> None:
    """
    In-place: add `minutes_played` and `ep_per_90` columns to every contributor
    DataFrame in the build context (scorer/SCA1/G+A nested tables AND the
    aggregated totals). The dashboard payload picks these up automatically.
    """
    if not minutes_by_player:
        return

    def _attach(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return df
        if "contributor" not in df.columns:
            return df
        df = df.copy()
        df["minutes_played"] = df["contributor"].map(minutes_by_player).fillna(0).astype(int)
        ep = df.get("exp_points_collected_timed")
        if ep is not None:
            mins = df["minutes_played"].astype(float)
            df["ep_per_90"] = np.where(
                mins > 0, (ep / mins) * 90.0, 0.0
            )
            df["ep_per_90"] = df["ep_per_90"].round(3)
        return df

    def _walk_nested(d: dict):
        return {lg: {ss: _attach(df) for ss, df in seasons.items()}
                for lg, seasons in d.items()}

    def _walk_keyed(d: dict):
        return {k: _attach(df) for k, df in d.items()}

    # Nested {league: {season: df}}
    for key in ("scorer_tables", "sca1_tables", "ga_tables"):
        ctx[key] = _walk_nested(ctx[key])

    # Aggregated tuples: (by_league, by_season, all_df)
    for key in ("scorer_totals", "sca1_totals", "ga_totals"):
        by_lg, by_ss, all_df = ctx[key]
        ctx[key] = (_walk_keyed(by_lg), _walk_keyed(by_ss), _attach(all_df))


def main():
    ctx = run_pipeline()

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[6/6] Loading player minutes + writing JSON artefacts ({created_at})...")

    # Player minutes (Top-5 leagues only — FULL_DICT_ROWS doesn't cover Eredivisie)
    minutes_by_player = load_player_minutes()
    if minutes_by_player:
        print(f"  Loaded minutes for {len(minutes_by_player):,} players")
        _attach_minutes_to_contributor_tables(ctx, minutes_by_player)

    # ── Editorial payload (data.json) ─────────────────────────
    ga_total_all = ctx["ga_totals"][2]  # (by_league, by_season, all)
    leagues = sorted(ctx["results"].keys())
    seasons = sorted(
        {str(s) for d in ctx["results"].values()
         for s in d["goal_events"]["season"].dropna().unique()}
    ) if ctx["results"] else []

    editorial = {
        "meta": {
            "generated_at": created_at,
            "leagues": leagues,
            "seasons": seasons,
            "time_bins": list(TIME_BINS),
            "gd_range": _gd_range(),
        },
        "callouts": build_callouts(
            goal_events_all=ctx["goal_events_all"],
            state_vals_timed=ctx["state_vals_pooled_t"],
            val_map_timed=ctx["val_map_timed"],
            ga_total_all=ga_total_all,
        ),
        "state_value_table": build_state_value_table(ctx["state_vals_pooled_t"]),
        "value_heatmap": build_value_heatmap(ctx["transitions_pooled_timed_f"]),
        "early_vs_late_0to1": build_early_vs_late_0to1(ctx["val_map_timed"]),
        "top10_ep_collectors": build_top10_ep(ga_total_all),
        "top10_timed_upgrade": build_top10_upgrade(ga_total_all),
        # Per-90 leaderboard: scope EP + minutes to the same league set
        # (Top-5 only; FULL_DICT_ROWS doesn't cover Eredivisie).
        "top10_ep_per_90":
            build_top10_ep_per_90(_ga_total_top5(ctx["ga_totals"]), minutes_by_player),
        "top10_ep_collectors_with_minutes":
            build_top10_ep_collectors_with_minutes(ga_total_all, minutes_by_player),
    }
    # Editorial payload stays pretty-printed (small + human-readable)
    _write_json(DATA_JSON, editorial)

    # ── Dashboard payload (per-(dataset, view) JSON files) ────
    dash_payload = build_payload(
        scorer_tables=ctx["scorer_tables"],
        sca1_tables=ctx["sca1_tables"],
        ga_tables=ctx["ga_tables"],
        scorer_totals=ctx["scorer_totals"],
        sca1_totals=ctx["sca1_totals"],
        ga_totals=ctx["ga_totals"],
        transitions_pooled=ctx["transitions_pooled_f"],
        transitions_by_league=ctx["transitions_by_league_f"],
        transitions_pooled_timed=ctx["transitions_pooled_timed_full"],
        transitions_by_league_timed=ctx["transitions_by_league_timed_f"],
        heatmap_pooled=ctx["heatmap_pooled"],
        heatmap_by_league=ctx["heatmap_by_league"],
        created_at=created_at,
    )
    # Split per dataset + sparse-encode. Each file < 5 MB target;
    # dashboard.html fetches manifest first then lazy-loads each dataset.
    _write_dashboard_files(dash_payload)

    print("\nDone.")


if __name__ == "__main__":
    main()
