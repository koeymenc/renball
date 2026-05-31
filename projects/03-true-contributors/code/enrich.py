"""
enrich.py - Renball Project 03 (The True Contributors) enrichment helpers
=========================================================================

Layers player metadata (minutes, position, age) on top of project 02's
contributor tables, integrates SCA2 as a third credit layer, and produces
the 7 research-question rankings (Q1 ... Q7).

This module is the only place project 03 reaches outside the goal_events
DataFrame produced by project 02. All FBref-summary-table reads live here;
all weighted/credit aggregation logic lives here; project 02 stays untouched.

ASCII-only prints (Windows console safety - see CLAUDE.md memory).
"""
from __future__ import annotations

import os
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


# ════════════════════════════════════════════════════════════════════════
# Scope / threshold constants (locked in Phase 0 discussion)
# ════════════════════════════════════════════════════════════════════════
TOP5_LEAGUES = {"Premier-League", "Serie-A", "Bundesliga", "La-Liga", "Ligue-1"}

# FULL_DICT_ROWS comp keys -> goal_events league names (project 02 filename convention)
COMP_TO_LEAGUE = {
    "PL":         "Premier-League",
    "SERIEA":     "Serie-A",
    "BUNDESLIGA": "Bundesliga",
    "LALIGA":     "La-Liga",
    "LIGUE1":     "Ligue-1",
}
LEAGUE_TO_COMP = {v: k for k, v in COMP_TO_LEAGUE.items()}

# FBref granular Pos -> 4 buckets (GK / DF / MF / FW)
POS_BUCKETS = {
    "GK": "GK",
    "CB": "DF", "LB": "DF", "RB": "DF", "LWB": "DF", "RWB": "DF",
    "WB": "DF", "FB": "DF", "DF": "DF",
    "CM": "MF", "DM": "MF", "AM": "MF", "LM": "MF", "RM": "MF", "MF": "MF",
    "FW": "FW", "LW": "FW", "RW": "FW", "ST": "FW", "CF": "FW",
}
# Q5 panels: outfield only. GK dropped per Phase 1 review - GK EP/90 is
# structurally suppressed by the framework (only credits scorer/SCA1/SCA2
# touchpoints, which GKs occupy rarely). The methodology section addresses
# this as a documented limitation rather than rendering near-zero GK rows.
POSITION_ORDER = ["DF", "MF", "FW"]

# Per-90 / qualification thresholds
MIN_MIN_DEFAULT = 1000      # Q1a, Q1b, Q2, Q5
MIN_MIN_YOUNG = 500         # Q7
MIN_GOALS_INVOLVED_Q3 = 15  # Q3 late-game share (3-layer credits)
MIN_GOALS_INVOLVED_Q4 = 5   # Q4 ratios

# Q1b weights (EP only - per refinement R-Q1b)
WEIGHT_SCORER = 0.40
WEIGHT_SCA1 = 0.35
WEIGHT_SCA2 = 0.25

# Scope metadata stamped onto every per-90 view (per user addition to R3)
PER_90_SCOPE = "Top 5 leagues only"
PER_90_SCOPE_NOTE = (
    "Per-90 calculations exclude Eredivisie due to unavailable minutes data "
    "(FULL_DICT_ROWS.pkl covers Premier League, La Liga, Serie A, Bundesliga, "
    "Ligue 1 only)."
)

DEFAULT_READY_DATA = r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA"


# ════════════════════════════════════════════════════════════════════════
# Pickle shim (FULL_DICT_ROWS was pickled under pandas < 2)
# ════════════════════════════════════════════════════════════════════════
def _install_pandas_pickle_shim() -> None:
    if "pandas.core.indexes.numeric" in sys.modules:
        return
    import pandas.core.indexes.base as _base
    class _Stub:
        Int64Index = _base.Index
        UInt64Index = _base.Index
        Float64Index = _base.Index
        NumericIndex = _base.Index
    sys.modules["pandas.core.indexes.numeric"] = _Stub()


# ════════════════════════════════════════════════════════════════════════
# Player metadata loading (minutes / position / age)
# ════════════════════════════════════════════════════════════════════════
def _primary_pos_token(s) -> str | None:
    """First token of FBref Pos string ('CM,LB' -> 'CM'). None if unparseable."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return None
    tok = str(s).split(",")[0].strip().upper()
    return tok or None


def _bucket_pos(pos_token: str | None) -> str | None:
    if pos_token is None:
        return None
    return POS_BUCKETS.get(pos_token)


def load_player_meta(default_data_path: str = DEFAULT_READY_DATA) -> dict:
    """
    Read FULL_DICT_ROWS.pkl -> ROWS_DICTS_SUMMARY and return:

        {
          "per_season": {
              (player, league, season): {"minutes": int, "pos": str, "age": float}
          },
          "pooled": {
              player: {"minutes": int, "pos": str, "age": float, "leagues": set}
          }
        }

    Notes
    -----
    - league is the goal_events-style key (Premier-League, La-Liga, etc.)
      mapped from FULL_DICT_ROWS comp keys (PL, LALIGA, ...).
    - `pos` is the modal bucketed value (GK/DF/MF/FW) across all rows for
      that scope.
    - `age` is the player's max age across all observed rows (effectively
      "age at end of most recent observed match"), float per FBref format.
    - Top-5 leagues only. Eredivisie players simply won't appear.
    """
    data_path = Path(os.environ.get("RENBALL_DATA_PATH", default_data_path))
    pkl = data_path / "FULL_DICT_ROWS.pkl"
    if not pkl.exists():
        print(f"  [enrich] FULL_DICT_ROWS.pkl not found at {pkl}")
        return {"per_season": {}, "pooled": {}}

    _install_pandas_pickle_shim()
    with open(pkl, "rb") as f:
        full = pickle.load(f)

    # Lazy import to avoid sys.path dependencies at module load
    from extraction import _clean_player_name

    parts = []
    for comp, sections in full.items():
        league = COMP_TO_LEAGUE.get(comp)
        if league is None:
            continue
        summary = sections.get("ROWS_DICTS_SUMMARY") if isinstance(sections, dict) else None
        if not isinstance(summary, dict):
            continue
        for season, df in summary.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            cols_needed = ["Player", "Min", "Pos", "Age"]
            if not all(c in df.columns for c in cols_needed):
                continue
            sub = df[cols_needed].copy()
            sub["player"] = sub["Player"].apply(_clean_player_name)
            sub["minutes"] = pd.to_numeric(sub["Min"], errors="coerce").fillna(0)
            sub["pos_token"] = sub["Pos"].apply(_primary_pos_token)
            sub["pos_bucket"] = sub["pos_token"].apply(_bucket_pos)
            sub["age"] = pd.to_numeric(sub["Age"], errors="coerce")
            sub["league"] = league
            sub["season"] = str(season)
            parts.append(sub[["player", "league", "season", "minutes",
                              "pos_bucket", "age"]])

    if not parts:
        return {"per_season": {}, "pooled": {}}

    all_rows = pd.concat(parts, ignore_index=True)
    all_rows = all_rows[all_rows["player"].notna()].copy()

    # ── Per (player, league, season) ──────────────────────────────────
    per_season: dict = {}
    grouper = all_rows.groupby(["player", "league", "season"], sort=False)
    for (player, league, season), grp in grouper:
        mins = int(grp["minutes"].sum())
        if mins == 0:
            continue
        pos_counts = Counter(p for p in grp["pos_bucket"] if p is not None)
        pos = pos_counts.most_common(1)[0][0] if pos_counts else None
        age = float(grp["age"].max()) if grp["age"].notna().any() else None
        per_season[(str(player), league, season)] = {
            "minutes": mins, "pos": pos, "age": age,
        }

    # ── Pooled by player (across all leagues + seasons) ───────────────
    pooled: dict = {}
    for player, grp in all_rows.groupby("player", sort=False):
        mins = int(grp["minutes"].sum())
        if mins == 0:
            continue
        pos_counts = Counter(p for p in grp["pos_bucket"] if p is not None)
        pos = pos_counts.most_common(1)[0][0] if pos_counts else None
        age = float(grp["age"].max()) if grp["age"].notna().any() else None
        pooled[str(player)] = {
            "minutes": mins, "pos": pos, "age": age,
            "leagues": set(grp["league"].unique()),
        }

    print(f"  [enrich] per_season keys: {len(per_season):,}  pooled players: {len(pooled):,}")
    return {"per_season": per_season, "pooled": pooled}


# ════════════════════════════════════════════════════════════════════════
# SCA2 + three-layer credit merge
# ════════════════════════════════════════════════════════════════════════
def build_sca2_tables(results: dict, val_map_untimed: dict,
                      val_map_timed: dict) -> dict:
    """Mirror of project 02's scorer/SCA1 builds, but for sca2_creator."""
    from analysis import build_contributor_tables
    return build_contributor_tables(results, val_map_untimed, val_map_timed,
                                     "sca2_creator")


def build_three_layer_tables(scorer_tables: dict, sca1_tables: dict,
                              sca2_tables: dict) -> dict:
    """
    Q1a credit model: scorer + SCA1 + SCA2, each = 1 credit per event.

    Composes project 02's two-table merger:
        three_layer = (scorer + sca1) + sca2

    Each `+` is `build_goals_plus_assists_tables`, which outer-merges on
    (scoring_team, contributor) and SUMS numeric columns. Repeating it with
    sca2 produces the desired 3-layer credit table without mutating project
    02's code. cnt_*, cnt_bin_*, ep_bin_* columns all stack correctly.
    """
    from analysis import build_goals_plus_assists_tables
    ga = build_goals_plus_assists_tables(scorer_tables, sca1_tables)
    return build_goals_plus_assists_tables(ga, sca2_tables)


def build_weighted_credit_per_event(goal_events: pd.DataFrame,
                                     val_map_timed: dict,
                                     val_map_untimed: dict,
                                     keep_set: set) -> pd.DataFrame:
    """
    Q1b: walk each goal event, emit up to 3 weighted credit rows. Weights
    apply to EP only; the goals_involved count column stays a raw 1 per
    credit row.

    Returns rows: (scoring_team, player, role, ep_weighted_timed,
                   ep_weighted_untimed, credits=1, league, season).
    Filters to KEEP_SET transitions (mirrors project 02's _contributor_table).
    """
    if goal_events.empty:
        return pd.DataFrame()

    ev = goal_events.copy()
    ev = ev[ev.apply(
        lambda r: (int(r["gd_before"]), int(r["gd_after"])) in keep_set, axis=1
    )].copy()

    # Lazy import to avoid sys.path dependency
    from config import BIN_UNKNOWN

    def _ep_t(r):
        return val_map_timed.get(
            (int(r["gd_before"]), int(r["gd_after"]),
             r.get("minute_bin", BIN_UNKNOWN)), 0.0)

    def _ep_u(r):
        return val_map_untimed.get(
            (int(r["gd_before"]), int(r["gd_after"])), 0.0)

    ev["ep_timed_raw"] = ev.apply(_ep_t, axis=1)
    ev["ep_untimed_raw"] = ev.apply(_ep_u, axis=1)

    role_specs = [
        ("goalscorer", "scorer", WEIGHT_SCORER),
        ("sca1_creator", "sca1", WEIGHT_SCA1),
        ("sca2_creator", "sca2", WEIGHT_SCA2),
    ]

    out_rows = []
    for col, role, weight in role_specs:
        if col not in ev.columns:
            continue
        sub = ev[ev[col].notna() & (ev[col].astype(str).str.strip().str.lower() != "unknown")].copy()
        if sub.empty:
            continue
        sub["player"] = sub[col].astype(str)
        sub["role"] = role
        sub["ep_weighted_timed"] = sub["ep_timed_raw"] * weight
        sub["ep_weighted_untimed"] = sub["ep_untimed_raw"] * weight
        sub["credits"] = 1
        keep_cols = ["scoring_team", "player", "role",
                     "ep_weighted_timed", "ep_weighted_untimed", "credits"]
        for c in ("league", "season"):
            if c in sub.columns:
                keep_cols.append(c)
        out_rows.append(sub[keep_cols])

    if not out_rows:
        return pd.DataFrame()
    return pd.concat(out_rows, ignore_index=True)


def aggregate_weighted_credit(per_event: pd.DataFrame,
                               scope: str = "pooled") -> pd.DataFrame:
    """
    Aggregate the per-event weighted credit table to one row per
    (scoring_team, player). `scope` selects which groupby keys to use:

      'pooled'    -> (scoring_team, player)
      'season'    -> (scoring_team, player, season)
      'league_season' -> (scoring_team, player, league, season)
    """
    if per_event.empty:
        return pd.DataFrame()

    keys_map = {
        "pooled":         ["scoring_team", "player"],
        "season":         ["scoring_team", "player", "season"],
        "league_season":  ["scoring_team", "player", "league", "season"],
    }
    keys = keys_map[scope]

    agg = (per_event.groupby(keys, as_index=False)
                    .agg(ep_weighted_timed=("ep_weighted_timed", "sum"),
                         ep_weighted_untimed=("ep_weighted_untimed", "sum"),
                         goals_involved=("credits", "sum")))

    # Per-role credit breakdown for Q1b explainability
    role_pivot = (per_event.pivot_table(index=keys, columns="role",
                                          values="credits", aggfunc="sum",
                                          fill_value=0)
                            .reset_index())
    rename = {r: f"credits_{r}" for r in ("scorer", "sca1", "sca2")
              if r in role_pivot.columns}
    role_pivot = role_pivot.rename(columns=rename)
    for c in ("credits_scorer", "credits_sca1", "credits_sca2"):
        if c not in role_pivot.columns:
            role_pivot[c] = 0

    out = agg.merge(role_pivot, on=keys, how="left")
    return out.sort_values("ep_weighted_timed", ascending=False).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════
# Pooling helper: collapse (scoring_team, player) -> player
# ════════════════════════════════════════════════════════════════════════
def pool_by_player(df: pd.DataFrame, player_col: str = "contributor",
                    team_col: str = "scoring_team",
                    drop_unknown: bool = True) -> pd.DataFrame:
    """
    Sum across teams (when a player moved mid-period), keep primary_team =
    team with most goals_involved. Mirrors project 02's `_pool_by_contributor`
    but lives here so this module doesn't depend on project 02's private
    build.py helpers.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    work[player_col] = work[player_col].fillna("Unknown").astype(str)
    if drop_unknown:
        work = work[work[player_col].str.strip().str.lower() != "unknown"]
    if work.empty:
        return pd.DataFrame()

    primary = (work.sort_values("goals_involved", ascending=False)
                   .drop_duplicates(player_col, keep="first")
                   [[player_col, team_col]]
                   .rename(columns={team_col: "primary_team"}))

    sum_cols = [c for c in work.columns
                if c not in (player_col, team_col)
                and pd.api.types.is_numeric_dtype(work[c])]

    pooled = work.groupby(player_col, as_index=False)[sum_cols].sum()
    pooled = pooled.merge(primary, on=player_col, how="left")

    # Recompute ratios that don't sum
    if "exp_points_collected_timed" in pooled.columns and "goals_involved" in pooled.columns:
        gi = pooled["goals_involved"].replace(0, np.nan)
        pooled["ratio_ep_per_goal"] = pooled["exp_points_collected_timed"] / gi
        pooled["delta_ep_minus_goals"] = (
            pooled["exp_points_collected_timed"] - pooled["goals_involved"]
        )
    if "exp_points_collected_timed" in pooled.columns and "exp_points_collected_untimed" in pooled.columns:
        pooled["delta_ep_timed_vs_untimed"] = (
            pooled["exp_points_collected_timed"] - pooled["exp_points_collected_untimed"]
        )

    return pooled


def attach_player_meta(pooled: pd.DataFrame, meta_pooled: dict,
                       player_col: str = "contributor",
                       require_minutes: bool = True) -> pd.DataFrame:
    """
    Attach minutes / pos / age columns from the pooled meta lookup. Rows
    without a metadata entry get minutes=0; if require_minutes=True, those
    rows are dropped (per-90 boards always require minutes).
    """
    if pooled.empty:
        return pooled

    def _get(d, key):
        m = meta_pooled.get(d, {})
        return m.get(key)

    pooled = pooled.copy()
    pooled["minutes"] = pooled[player_col].map(lambda p: meta_pooled.get(p, {}).get("minutes", 0)).fillna(0).astype(int)
    pooled["pos"] = pooled[player_col].map(lambda p: meta_pooled.get(p, {}).get("pos"))
    pooled["age"] = pooled[player_col].map(lambda p: meta_pooled.get(p, {}).get("age"))

    if "exp_points_collected_timed" in pooled.columns:
        ep = pooled["exp_points_collected_timed"].astype(float)
        mins = pooled["minutes"].astype(float)
        pooled["ep_per_90"] = np.where(mins > 0, (ep / mins) * 90.0, 0.0).round(3)

    if require_minutes:
        pooled = pooled[pooled["minutes"] > 0].copy()

    return pooled


# ════════════════════════════════════════════════════════════════════════
# Q1a / Q1b - Top-N leaderboards
# ════════════════════════════════════════════════════════════════════════
def _top_n_rows(df: pd.DataFrame, sort_col: str, top_n: int,
                 min_minutes: int) -> pd.DataFrame:
    if df.empty:
        return df
    if min_minutes > 0:
        df = df[df["minutes"] >= min_minutes]
    return df.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)


def _row_to_record(r, rank: int, *, weighted: bool = False) -> dict:
    rec = {
        "rank": rank,
        "player": str(r["contributor" if "contributor" in r else "player"]),
        "primary_team": str(r["primary_team"]),
        "minutes": int(r["minutes"]),
        "goals_involved": int(r["goals_involved"]),
        "pos": (r.get("pos") if pd.notna(r.get("pos")) else None),
        "age": (round(float(r["age"]), 2) if pd.notna(r.get("age")) else None),
    }
    if weighted:
        rec["ep_weighted_timed"] = round(float(r["ep_weighted_timed"]), 3)
        rec["ep_weighted_per_90"] = round(float(r["ep_weighted_per_90"]), 3)
        for c in ("credits_scorer", "credits_sca1", "credits_sca2"):
            if c in r.index:
                rec[c] = int(r[c])
    else:
        rec["ep_timed"] = round(float(r["exp_points_collected_timed"]), 3)
        rec["ep_per_90"] = round(float(r["ep_per_90"]), 3)
    return rec


def build_q1a_full_credit(three_layer_total_all_top5: pd.DataFrame,
                           player_meta: dict, top_n: int = 50,
                           min_minutes: int = MIN_MIN_DEFAULT) -> dict:
    """Q1a - Top N EP/90, all 3 roles count = 1 credit each."""
    pooled = pool_by_player(three_layer_total_all_top5, player_col="contributor")
    pooled = attach_player_meta(pooled, player_meta["pooled"],
                                  player_col="contributor", require_minutes=True)
    top = _top_n_rows(pooled, "ep_per_90", top_n, min_minutes)
    rows = [_row_to_record(r, rank=i + 1)
            for i, (_, r) in enumerate(top.iterrows())]
    return {
        "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
        "min_minutes": min_minutes, "credit_model": "full (each role = 1)",
        "rows": rows,
    }


def build_q1b_weighted_credit(weighted_total_top5: pd.DataFrame,
                               player_meta: dict, top_n: int = 50,
                               min_minutes: int = MIN_MIN_DEFAULT) -> dict:
    """Q1b - Top N weighted EP/90, 0.40 / 0.35 / 0.25 on EP only."""
    if weighted_total_top5.empty:
        return {"scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
                "min_minutes": min_minutes, "rows": []}

    # weighted_total_top5 already at (scoring_team, player) level. Pool to player.
    work = weighted_total_top5.copy()
    work = work.rename(columns={"player": "contributor"})
    work["primary_team"] = work["scoring_team"]
    # pool: sum by player, primary_team = team with most goals_involved
    primary = (work.sort_values("goals_involved", ascending=False)
                   .drop_duplicates("contributor", keep="first")
                   [["contributor", "scoring_team"]]
                   .rename(columns={"scoring_team": "primary_team"}))
    sum_cols = [c for c in work.columns
                if c not in ("contributor", "scoring_team", "primary_team")
                and pd.api.types.is_numeric_dtype(work[c])]
    pooled = work.groupby("contributor", as_index=False)[sum_cols].sum()
    pooled = pooled.merge(primary, on="contributor", how="left")

    # attach minutes
    pooled["minutes"] = pooled["contributor"].map(
        lambda p: player_meta["pooled"].get(p, {}).get("minutes", 0)
    ).fillna(0).astype(int)
    pooled["pos"] = pooled["contributor"].map(
        lambda p: player_meta["pooled"].get(p, {}).get("pos")
    )
    pooled["age"] = pooled["contributor"].map(
        lambda p: player_meta["pooled"].get(p, {}).get("age")
    )
    pooled = pooled[pooled["minutes"] > 0].copy()

    mins = pooled["minutes"].astype(float)
    pooled["ep_weighted_per_90"] = np.where(
        mins > 0, (pooled["ep_weighted_timed"].astype(float) / mins) * 90.0, 0.0
    ).round(3)

    top = _top_n_rows(pooled, "ep_weighted_per_90", top_n, min_minutes)
    rows = [_row_to_record(r, rank=i + 1, weighted=True)
            for i, (_, r) in enumerate(top.iterrows())]
    return {
        "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
        "min_minutes": min_minutes,
        "weights": {"scorer": WEIGHT_SCORER, "sca1": WEIGHT_SCA1, "sca2": WEIGHT_SCA2},
        "rows": rows,
    }


def build_q1_rank_shift(q1a_rows: list, q1b_rows: list,
                         top_n: int = 30) -> list:
    """
    Q1a-vs-Q1b rank-shift table for the slope chart in section 2.
    Union of top-N from both, with rank_a / rank_b / delta (b - a; positive
    means weighting helped the player).
    """
    a_rank = {r["player"]: r["rank"] for r in q1a_rows[:top_n]}
    b_rank = {r["player"]: r["rank"] for r in q1b_rows[:top_n]}
    players = set(a_rank) | set(b_rank)
    out = []
    for p in players:
        ra = a_rank.get(p)
        rb = b_rank.get(p)
        if ra is None and rb is None:
            continue
        # delta: A -> B. If a player drops out of B, treat as "off chart"
        delta = (ra - rb) if (ra is not None and rb is not None) else None
        out.append({
            "player": p,
            "rank_a": ra,
            "rank_b": rb,
            "delta": delta,
        })
    out.sort(key=lambda r: (r["rank_a"] if r["rank_a"] is not None else 999,
                              r["rank_b"] if r["rank_b"] is not None else 999))
    return out


# ════════════════════════════════════════════════════════════════════════
# Q2 - Per-(league, season) MVP grid
# ════════════════════════════════════════════════════════════════════════
def build_q2_mvp_grid(three_layer_tables: dict, player_meta: dict,
                       actual_mvps: dict | None = None,
                       min_minutes: int = MIN_MIN_DEFAULT) -> dict:
    """
    For every (league, season) cell in Top-5 leagues, model's top EP/90 pick.
    Plus a combined Top-5 row per season for the 5L MVP. Optional
    `actual_mvps` lookup annotates each cell with the real-world winner.
    """
    actual_mvps = actual_mvps or {}
    actual_by_league = actual_mvps.get("by_league", {})
    actual_combined = actual_mvps.get("combined_ballon_dor", {})

    per_season = player_meta["per_season"]

    def _mvp_for(df_cell: pd.DataFrame, league: str | None,
                  season: str) -> dict | None:
        """Top EP/90 player in a single (league, season) df, using per-season minutes."""
        if df_cell is None or df_cell.empty:
            return None
        pooled = pool_by_player(df_cell, player_col="contributor")
        if pooled.empty or "exp_points_collected_timed" not in pooled.columns:
            return None

        # Per-season minutes for THIS cell only
        def _mins(player: str) -> int:
            if league is not None:
                m = per_season.get((player, league, season))
                return int(m["minutes"]) if m else 0
            # Combined 5L: sum minutes across all 5 leagues for that season
            total = 0
            for lg in TOP5_LEAGUES:
                m = per_season.get((player, lg, season))
                if m:
                    total += int(m["minutes"])
            return total

        pooled["minutes"] = pooled["contributor"].apply(_mins)
        pooled = pooled[pooled["minutes"] >= min_minutes].copy()
        if pooled.empty:
            return None

        mins = pooled["minutes"].astype(float)
        ep = pooled["exp_points_collected_timed"].astype(float)
        pooled["ep_per_90"] = np.where(mins > 0, (ep / mins) * 90.0, 0.0)
        pooled = pooled.sort_values("ep_per_90", ascending=False).head(1)
        r = pooled.iloc[0]
        return {
            "player": str(r["contributor"]),
            "primary_team": str(r["primary_team"]),
            "minutes": int(r["minutes"]),
            "ep_timed": round(float(r["exp_points_collected_timed"]), 3),
            "ep_per_90": round(float(r["ep_per_90"]), 3),
            "goals_involved": int(r["goals_involved"]),
        }

    leagues_present = [lg for lg in sorted(three_layer_tables.keys())
                       if lg in TOP5_LEAGUES]
    seasons_present = sorted({s for lg in leagues_present
                                for s in three_layer_tables.get(lg, {}).keys()},
                              key=str)

    grid: dict = {}
    for league in leagues_present:
        grid[league] = {}
        for season in seasons_present:
            cell = three_layer_tables.get(league, {}).get(season)
            pick = _mvp_for(cell, league, season)
            actual = actual_by_league.get(league, {}).get(season)
            grid[league][season] = {
                "model_pick": pick,
                "actual": actual,
            }

    # Combined 5L per season
    combined: dict = {}
    for season in seasons_present:
        # Build a combined (league-agnostic) df for that season
        parts = [three_layer_tables[lg].get(season) for lg in leagues_present
                 if season in three_layer_tables.get(lg, {})]
        parts = [p for p in parts if isinstance(p, pd.DataFrame) and not p.empty]
        if not parts:
            combined[season] = {"model_pick": None,
                                  "actual_ballon_dor": actual_combined.get(season)}
            continue
        merged = pd.concat(parts, ignore_index=True)
        # Re-aggregate by (team, contributor) since same player might appear in
        # multiple league sheets (only possible if mid-season transfer)
        keys = ["scoring_team", "contributor"]
        numeric = [c for c in merged.columns if c not in keys
                   and pd.api.types.is_numeric_dtype(merged[c])]
        merged = merged.groupby(keys, as_index=False)[numeric].sum()
        pick = _mvp_for(merged, league=None, season=season)
        combined[season] = {
            "model_pick": pick,
            "actual_ballon_dor": actual_combined.get(season),
        }

    return {
        "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
        "min_minutes": min_minutes,
        "leagues": leagues_present,
        "seasons": seasons_present,
        "grid": grid,
        "combined_5l": combined,
    }


# ════════════════════════════════════════════════════════════════════════
# Q3 - Late-game specialists
# ════════════════════════════════════════════════════════════════════════
def build_q3_late_game(three_layer_total_all: pd.DataFrame,
                        top_n: int = 20,
                        min_goals_involved: int = MIN_GOALS_INVOLVED_Q3,
                        editorial_min: int = 30) -> dict:
    """
    Two views:
      - rows:               dashboard view (>= min_goals_involved, default 15)
      - rows_substantive:   editorial view (>= editorial_min, default 30)
                            drops super-sub small samples
    Both sort by share_late descending, take top_n.
    """
    pooled = pool_by_player(three_layer_total_all, player_col="contributor")
    if pooled.empty:
        return {"min_goals_involved": min_goals_involved,
                "editorial_min": editorial_min,
                "rows": [], "rows_substantive": []}

    bins_late = ["ep_bin_60-75", "ep_bin_75-90"]
    bins_all = [c for c in pooled.columns if c.startswith("ep_bin_")]
    for c in bins_late + bins_all:
        if c not in pooled.columns:
            pooled[c] = 0.0

    pooled["ep_late"] = pooled[bins_late].sum(axis=1)
    pooled["ep_all_bins"] = pooled[bins_all].sum(axis=1)
    pooled["share_late"] = np.where(pooled["ep_all_bins"] > 0,
                                     pooled["ep_late"] / pooled["ep_all_bins"], 0.0)

    def _rows_for(min_cr: int) -> list:
        qual = pooled[pooled["goals_involved"] >= min_cr]
        top = qual.sort_values("share_late", ascending=False).head(top_n)
        out = []
        for i, (_, r) in enumerate(top.iterrows()):
            out.append({
                "rank": i + 1,
                "player": str(r["contributor"]),
                "primary_team": str(r["primary_team"]),
                "goals_involved": int(r["goals_involved"]),
                "ep_total": round(float(r["ep_all_bins"]), 3),
                "ep_late": round(float(r["ep_late"]), 3),
                "share_late": round(float(r["share_late"]), 4),
            })
        return out

    return {
        "min_goals_involved": min_goals_involved,
        "editorial_min": editorial_min,
        "top_n": top_n,
        "rows": _rows_for(min_goals_involved),
        "rows_substantive": _rows_for(editorial_min),
    }


# ════════════════════════════════════════════════════════════════════════
# Q4 - Efficiency ratios (Q4c deferred)
# ════════════════════════════════════════════════════════════════════════
def build_q4_efficiency(three_layer_total_all: pd.DataFrame,
                         top_n: int = 20,
                         min_goals_involved: int = MIN_GOALS_INVOLVED_Q4,
                         editorial_min: int = 20) -> dict:
    """
    Two views per ratio:
      - q4a / q4b:                            dashboard (>= min_goals_involved, default 5)
      - q4a_substantive / q4b_substantive:    editorial  (>= editorial_min, default 20)
    """
    pooled = pool_by_player(three_layer_total_all, player_col="contributor")
    if pooled.empty:
        return {"q4a": [], "q4b": [],
                "q4a_substantive": [], "q4b_substantive": [],
                "q4c_note": "deferred"}

    def _q4a_rows(min_cr: int) -> list:
        q = pooled[pooled["goals_involved"] >= min_cr]
        top = q.sort_values("ratio_ep_per_goal", ascending=False).head(top_n)
        return [{
            "rank": i + 1,
            "player": str(r["contributor"]),
            "primary_team": str(r["primary_team"]),
            "goals_involved": int(r["goals_involved"]),
            "ep_timed": round(float(r["exp_points_collected_timed"]), 3),
            "ratio_ep_per_goal": round(float(r["ratio_ep_per_goal"]), 4),
        } for i, (_, r) in enumerate(top.iterrows())]

    def _q4b_rows(min_cr: int) -> list:
        q = pooled[(pooled["goals_involved"] >= min_cr) &
                   (pooled["exp_points_collected_untimed"] > 0)].copy()
        q["multiplier"] = (q["exp_points_collected_timed"] /
                            q["exp_points_collected_untimed"])
        top = q.sort_values("multiplier", ascending=False).head(top_n)
        return [{
            "rank": i + 1,
            "player": str(r["contributor"]),
            "primary_team": str(r["primary_team"]),
            "goals_involved": int(r["goals_involved"]),
            "ep_timed": round(float(r["exp_points_collected_timed"]), 3),
            "ep_untimed": round(float(r["exp_points_collected_untimed"]), 3),
            "multiplier": round(float(r["multiplier"]), 4),
        } for i, (_, r) in enumerate(top.iterrows())]

    return {
        "q4a": _q4a_rows(min_goals_involved),
        "q4b": _q4b_rows(min_goals_involved),
        "q4a_substantive": _q4a_rows(editorial_min),
        "q4b_substantive": _q4b_rows(editorial_min),
        "q4c_note": "EP per shot deferred - requires non-goal shot extraction (TODO).",
        "min_goals_involved": min_goals_involved,
        "editorial_min": editorial_min,
        "top_n": top_n,
    }


# ════════════════════════════════════════════════════════════════════════
# Q5 - Position-adjusted EP/90 (4 panels)
# ════════════════════════════════════════════════════════════════════════
GK_LIMITATION_NOTE = (
    "Q5 reports outfield positions (DF/MF/FW) only. Goalkeepers are excluded: "
    "the EP framework credits scorers, assist-creators (SCA1) and pre-assist-"
    "creators (SCA2), three touchpoints GKs occupy rarely. Top GKs in this "
    "dataset post ~0.1 EP/90 vs ~1.1 for top forwards - a structural ratio "
    "reflecting the framework's coverage, not the keepers' actual value. "
    "Quantifying GK contribution requires a different model (e.g. shot-stopping "
    "over expected, distribution value)."
)


def build_q5_position_adjusted(three_layer_total_all_top5: pd.DataFrame,
                                player_meta: dict, top_n: int = 5,
                                min_minutes: int = MIN_MIN_DEFAULT) -> dict:
    pooled = pool_by_player(three_layer_total_all_top5, player_col="contributor")
    pooled = attach_player_meta(pooled, player_meta["pooled"],
                                  player_col="contributor", require_minutes=True)
    pooled = pooled[pooled["minutes"] >= min_minutes].copy()

    panels: dict = {}
    for pos in POSITION_ORDER:
        sub = pooled[pooled["pos"] == pos]
        sub = sub.sort_values("ep_per_90", ascending=False).head(top_n)
        rows = [_row_to_record(r, rank=i + 1)
                for i, (_, r) in enumerate(sub.iterrows())]
        panels[pos] = {"rows": rows}

    return {
        "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
        "min_minutes": min_minutes,
        "top_n": top_n,
        "panels": panels,
        "gk_limitation_note": GK_LIMITATION_NOTE,
    }


# ════════════════════════════════════════════════════════════════════════
# Q6 - Hidden Architects (SCA2 layer)
# ════════════════════════════════════════════════════════════════════════
def build_q6_hidden_architects(sca2_total_all: pd.DataFrame,
                                sca2_total_top5: pd.DataFrame,
                                scorer_total_all: pd.DataFrame,
                                sca1_total_all: pd.DataFrame,
                                player_meta: dict,
                                top_n_abs: int = 20, top_n_per90: int = 10,
                                min_minutes: int = MIN_MIN_DEFAULT) -> dict:
    """
    Top by absolute SCA2 EP + top by SCA2 EP/90 + stacked-bar EP-by-role.

    `sca2_total_all` covers all 6 leagues and is used for the absolute board.
    `sca2_total_top5` is Top-5 only and is used for the per-90 board, so the
    SCA2 EP numerator and the Top-5 minutes denominator cover the same scope
    (mirrors the R3 constraint applied elsewhere).
    """
    pooled_sca2 = pool_by_player(sca2_total_all, player_col="contributor")
    if pooled_sca2.empty:
        return {"abs_top": [], "per_90_top": {"rows": []},
                "layer_breakdown": []}

    # Absolute SCA2 EP top (all leagues)
    abs_top = pooled_sca2.sort_values("exp_points_collected_timed",
                                        ascending=False).head(top_n_abs)
    abs_rows = [{
        "rank": i + 1,
        "player": str(r["contributor"]),
        "primary_team": str(r["primary_team"]),
        "goals_involved": int(r["goals_involved"]),
        "ep_timed": round(float(r["exp_points_collected_timed"]), 3),
    } for i, (_, r) in enumerate(abs_top.iterrows())]

    # SCA2 per-90 top: numerator = Top-5 SCA2 EP only; denominator = Top-5 minutes
    pooled_per90_src = pool_by_player(sca2_total_top5, player_col="contributor")
    pooled_per90 = attach_player_meta(pooled_per90_src, player_meta["pooled"],
                                        player_col="contributor",
                                        require_minutes=True)
    pooled_per90 = pooled_per90[pooled_per90["minutes"] >= min_minutes]
    per90_top = pooled_per90.sort_values("ep_per_90",
                                            ascending=False).head(top_n_per90)
    per90_rows = [{
        "rank": i + 1,
        "player": str(r["contributor"]),
        "primary_team": str(r["primary_team"]),
        "minutes": int(r["minutes"]),
        "goals_involved": int(r["goals_involved"]),
        "ep_timed": round(float(r["exp_points_collected_timed"]), 3),
        "ep_per_90": round(float(r["ep_per_90"]), 3),
        "pos": (r.get("pos") if pd.notna(r.get("pos")) else None),
    } for i, (_, r) in enumerate(per90_top.iterrows())]

    # Layer breakdown for stacked-bar (top_n_abs players)
    pooled_scorer = pool_by_player(scorer_total_all, player_col="contributor")
    pooled_sca1 = pool_by_player(sca1_total_all, player_col="contributor")

    def _ep(d: pd.DataFrame, player: str) -> float:
        if d.empty:
            return 0.0
        m = d[d["contributor"] == player]
        if m.empty:
            return 0.0
        return float(m["exp_points_collected_timed"].iloc[0])

    layer = []
    for rec in abs_rows:
        p = rec["player"]
        es = round(_ep(pooled_scorer, p), 3)
        e1 = round(_ep(pooled_sca1, p), 3)
        e2 = round(_ep(pooled_sca2, p), 3)
        layer.append({
            "player": p, "primary_team": rec["primary_team"],
            "ep_scorer": es, "ep_sca1": e1, "ep_sca2": e2,
            "ep_total": round(es + e1 + e2, 3),
        })

    return {
        "abs_top": abs_rows,
        "per_90_top": {
            "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
            "min_minutes": min_minutes,
            "rows": per90_rows,
        },
        "layer_breakdown": layer,
    }


# ════════════════════════════════════════════════════════════════════════
# Q7 - Young players to watch
# ════════════════════════════════════════════════════════════════════════
def build_q7_young_players(three_layer_total_all_top5: pd.DataFrame,
                            player_meta: dict, top_n: int = 10,
                            max_age: float = 23.0,
                            min_minutes: int = MIN_MIN_YOUNG) -> dict:
    pooled = pool_by_player(three_layer_total_all_top5, player_col="contributor")
    pooled = attach_player_meta(pooled, player_meta["pooled"],
                                  player_col="contributor", require_minutes=True)
    pooled = pooled[pooled["minutes"] >= min_minutes].copy()
    pooled = pooled[pooled["age"].notna() & (pooled["age"] <= max_age)].copy()
    top = pooled.sort_values("ep_per_90", ascending=False).head(top_n)
    rows = [_row_to_record(r, rank=i + 1)
            for i, (_, r) in enumerate(top.iterrows())]
    return {
        "scope": PER_90_SCOPE, "scope_note": PER_90_SCOPE_NOTE,
        "max_age": max_age, "min_minutes": min_minutes,
        "rows": rows,
    }
