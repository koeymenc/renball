"""
Points by Gamestate (v3) — Analysis
Includes both time-agnostic (v2) and time-aware (v3) value models.
"""
import numpy as np
import pandas as pd

from config import KEEP_SET, KEEP_PAIRS, ORDER_MAP, TIME_BINS, BIN_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
#  UNTIMED STATE VALUE FUNCTIONS  (identical to v2)
# ═══════════════════════════════════════════════════════════════════════

def build_pre_goal_state_rows(goal_events: pd.DataFrame,
                              carry_minute_bin: bool = False) -> pd.DataFrame:
    """
    For each goal moment create TWO rows (pre-goal state):
      - scoring team  with  gd_before, final_result/points from scoring team's perspective
      - conceding team with -gd_before, final_result/points FLIPPED to the conceder's
        perspective (W↔L, 3↔0; draws stay as D / 1 point)

    The flip is required so the empirical state value `E[final_points | gd, minute_bin]`
    is symmetric: a team currently leading 7-0 should have expected points ≈ 3, and a
    team currently trailing 7-0 should have expected points ≈ 0. Without the flip, both
    sides inherit the scoring team's outcome and the table aliases them together.

    If carry_minute_bin=True, minute_bin is preserved on both rows.
    """
    if goal_events.empty:
        return pd.DataFrame()

    base_cols = ["season", "match_key", "event_idx", "gd_before", "final_result", "final_points"]
    if carry_minute_bin:
        base_cols = base_cols + ["minute_bin"]

    scorer = goal_events[["scoring_team"] + base_cols].copy()
    scorer = scorer.rename(columns={"scoring_team": "team", "gd_before": "gd"})

    conceder = goal_events[["opponent_team"] + base_cols].copy()
    conceder["gd"] = -conceder["gd_before"]
    conceder["final_result"] = conceder["final_result"].map({"W": "L", "L": "W", "D": "D"})
    conceder["final_points"] = conceder["final_points"].map({3: 0, 1: 1, 0: 3}).astype(int)
    conceder = conceder.drop(columns=["gd_before"]).rename(columns={"opponent_team": "team"})

    return pd.concat([scorer, conceder], ignore_index=True)


def state_summary(pre_states: pd.DataFrame) -> pd.DataFrame:
    """Expected points at each GD state (time-agnostic value function)."""
    if pre_states.empty:
        return pd.DataFrame()

    g = pre_states.groupby("gd")
    probs = g["final_result"].value_counts(normalize=True).unstack(fill_value=0.0)
    probs = probs.rename(columns={"W": "pW", "D": "pD", "L": "pL"})

    n = g.size().rename("n")
    ep = g["final_points"].mean().rename("exp_points")

    res = pd.concat([n, probs, ep], axis=1).reset_index().sort_values("gd").reset_index(drop=True)
    for c in ("pW", "pD", "pL"):
        if c not in res.columns:
            res[c] = 0.0
    return res


def goal_value_table(state_vals: pd.DataFrame) -> pd.DataFrame:
    """Delta EP for moving from gd to gd+1."""
    if state_vals.empty:
        return pd.DataFrame()

    a = state_vals[["gd", "exp_points"]].rename(columns={"gd": "gd_before", "exp_points": "ep_before"})
    b = state_vals[["gd", "exp_points"]].rename(columns={"gd": "gd_after", "exp_points": "ep_after"})

    m = pd.merge(a, b, left_on="gd_before", right_on="gd_after", how="inner")
    m = m.loc[m["gd_after"] == m["gd_before"] + 1].copy()
    m["delta_ep"] = m["ep_after"] - m["ep_before"]
    return m.sort_values("gd_before").reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════
#  TIMED STATE VALUE FUNCTIONS  (new in v3)
# ═══════════════════════════════════════════════════════════════════════

def state_summary_timed(pre_states: pd.DataFrame) -> pd.DataFrame:
    """
    Expected points at each (GD, minute_bin) state.
    Same logic as state_summary but grouped by ["gd", "minute_bin"].
    """
    if pre_states.empty:
        return pd.DataFrame()

    # Drop unknown bins from timed analysis
    ps = pre_states[pre_states["minute_bin"] != BIN_UNKNOWN].copy()
    if ps.empty:
        return pd.DataFrame()

    g = ps.groupby(["gd", "minute_bin"])
    probs = g["final_result"].value_counts(normalize=True).unstack(fill_value=0.0)
    probs = probs.rename(columns={"W": "pW", "D": "pD", "L": "pL"})

    n = g.size().rename("n")
    ep = g["final_points"].mean().rename("exp_points")

    res = pd.concat([n, probs, ep], axis=1).reset_index()
    res = res.sort_values(["gd", "minute_bin"]).reset_index(drop=True)
    for c in ("pW", "pD", "pL"):
        if c not in res.columns:
            res[c] = 0.0
    return res


# ═══════════════════════════════════════════════════════════════════════
#  TRANSITION SUMMARIES
# ═══════════════════════════════════════════════════════════════════════

def transition_summary(goal_events: pd.DataFrame,
                       state_vals: pd.DataFrame = None) -> pd.DataFrame:
    """Untimed transition table (v2 logic)."""
    if goal_events.empty:
        return pd.DataFrame()

    g = goal_events.groupby(["gd_before", "gd_after"], dropna=False)
    probs = g["final_result"].value_counts(normalize=True).unstack(fill_value=0.0)
    probs = probs.rename(columns={"W": "pW", "D": "pD", "L": "pL"})

    n = g.size().rename("n")
    ep = g["final_points"].mean().rename("exp_points")

    res = pd.concat([n, probs, ep], axis=1).reset_index()
    for c in ("pW", "pD", "pL"):
        if c not in res.columns:
            res[c] = 0.0
    res = res.sort_values(["gd_before", "gd_after"]).reset_index(drop=True)

    if state_vals is not None and not state_vals.empty:
        ep_map = state_vals.set_index("gd")["exp_points"]
        res["ep_before_state"] = res["gd_before"].map(ep_map)
        res["ep_after_state"] = res["gd_after"].map(ep_map)
        res["delta_exp_points"] = res["ep_after_state"] - res["ep_before_state"]

    return res


def transition_summary_timed(goal_events: pd.DataFrame,
                             state_vals_timed: pd.DataFrame = None) -> pd.DataFrame:
    """
    Time-aware transition table: group by (gd_before, gd_after, minute_bin).
    Uses Approach A: delta_EP = EP(gd_after, bin) - EP(gd_before, bin) from timed state values.
    """
    if goal_events.empty:
        return pd.DataFrame()

    ev = goal_events[goal_events["minute_bin"] != BIN_UNKNOWN].copy()
    if ev.empty:
        return pd.DataFrame()

    g = ev.groupby(["gd_before", "gd_after", "minute_bin"], dropna=False)
    probs = g["final_result"].value_counts(normalize=True).unstack(fill_value=0.0)
    probs = probs.rename(columns={"W": "pW", "D": "pD", "L": "pL"})

    n = g.size().rename("n")
    ep = g["final_points"].mean().rename("exp_points")

    res = pd.concat([n, probs, ep], axis=1).reset_index()
    for c in ("pW", "pD", "pL"):
        if c not in res.columns:
            res[c] = 0.0
    res = res.sort_values(["gd_before", "gd_after", "minute_bin"]).reset_index(drop=True)

    # Approach A: state-value delta
    if state_vals_timed is not None and not state_vals_timed.empty:
        ep_map = state_vals_timed.set_index(["gd", "minute_bin"])["exp_points"]
        res["ep_before_state"] = res.set_index(["gd_before", "minute_bin"]).index.map(
            lambda idx: ep_map.get(idx, np.nan)
        )
        res["ep_after_state"] = res.set_index(["gd_after", "minute_bin"]).index.map(
            lambda idx: ep_map.get(idx, np.nan)
        )
        res["delta_exp_points"] = res["ep_after_state"] - res["ep_before_state"]

    return res


# ═══════════════════════════════════════════════════════════════════════
#  VALUE MAPS  (transition → EP collected)
# ═══════════════════════════════════════════════════════════════════════

def prep_transitions(df: pd.DataFrame) -> pd.DataFrame:
    """Filter transitions to KEEP_SET, sort, and add exp_points_collected (untimed)."""
    d = df.copy()
    d = d[d.apply(lambda r: (int(r["gd_before"]), int(r["gd_after"])) in KEEP_SET, axis=1)].copy()
    d["_ord"] = d.apply(lambda r: ORDER_MAP.get((int(r["gd_before"]), int(r["gd_after"])), 999), axis=1)
    d = d.sort_values("_ord").reset_index(drop=True).drop(columns=["_ord"])
    d["exp_points_collected"] = d["exp_points"].diff().fillna(0.0)
    return d


def prep_value_map(transitions: pd.DataFrame) -> dict:
    """Untimed value map: (gd_before, gd_after) → ep_collected."""
    prepped = prep_transitions(transitions)
    return {
        (int(r.gd_before), int(r.gd_after)): float(r.exp_points_collected)
        for r in prepped.itertuples(index=False)
    }


def prep_transitions_timed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter timed transitions to KEEP_SET, sort by (minute_bin, gd_before, gd_after),
    and add exp_points_collected per bin (diff within each bin group).
    """
    d = df.copy()
    d = d[d.apply(lambda r: (int(r["gd_before"]), int(r["gd_after"])) in KEEP_SET, axis=1)].copy()
    d = d[d["minute_bin"] != BIN_UNKNOWN].copy()

    d["_ord"] = d.apply(lambda r: ORDER_MAP.get((int(r["gd_before"]), int(r["gd_after"])), 999), axis=1)
    d = d.sort_values(["minute_bin", "_ord"]).reset_index(drop=True).drop(columns=["_ord"])

    # diff within each minute_bin group
    d["exp_points_collected"] = d.groupby("minute_bin")["exp_points"].diff().fillna(0.0)
    return d


def prep_value_map_timed(transitions_timed: pd.DataFrame) -> dict:
    """Timed value map: (gd_before, gd_after, minute_bin) → ep_collected."""
    prepped = prep_transitions_timed(transitions_timed)
    return {
        (int(r.gd_before), int(r.gd_after), r.minute_bin): float(r.exp_points_collected)
        for r in prepped.itertuples(index=False)
    }


# ═══════════════════════════════════════════════════════════════════════
#  HEATMAP TABLE (flat: gd_before, gd_after, minute_bin, ep_collected, n)
# ═══════════════════════════════════════════════════════════════════════

def build_heatmap_table(transitions_timed_prepped: pd.DataFrame) -> pd.DataFrame:
    """
    Flat table for the dashboard heatmap view.
    Rows = (gd_before, gd_after, minute_bin), values = n + ep_collected.
    """
    cols = ["gd_before", "gd_after", "minute_bin", "n", "exp_points", "exp_points_collected"]
    available = [c for c in cols if c in transitions_timed_prepped.columns]
    return transitions_timed_prepped[available].copy().reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════
#  CONTRIBUTOR TABLES  (scorer / assist — timed + untimed)
# ═══════════════════════════════════════════════════════════════════════

def _contributor_table(goal_events: pd.DataFrame, contributor_col: str,
                       val_map_untimed: dict, val_map_timed: dict) -> pd.DataFrame:
    """
    Build a per-contributor table for one season of goal events.
    Includes both timed and untimed EP, plus cnt_* (GD transition) and cnt_bin_* (time bin) columns.
    """
    ev = goal_events.copy()
    ev = ev[ev.apply(lambda r: (int(r["gd_before"]), int(r["gd_after"])) in KEEP_SET, axis=1)].copy()

    # Untimed EP per goal
    ev["ep_untimed"] = ev.apply(
        lambda r: val_map_untimed.get((int(r["gd_before"]), int(r["gd_after"])), 0.0), axis=1
    )

    # Timed EP per goal
    ev["ep_timed"] = ev.apply(
        lambda r: val_map_timed.get(
            (int(r["gd_before"]), int(r["gd_after"]), r.get("minute_bin", BIN_UNKNOWN)), 0.0
        ), axis=1
    )

    ev["contributor"] = ev[contributor_col].fillna("Unknown").astype(str)

    # ── Base aggregation ──────────────────────────────────────────
    base = (
        ev.groupby(["scoring_team", "contributor"], as_index=False)
          .agg(
              goals_involved=("contributor", "size"),
              exp_points_collected_untimed=("ep_untimed", "sum"),
              exp_points_collected_timed=("ep_timed", "sum"),
          )
    )

    # ── GD transition cnt columns ─────────────────────────────────
    ev["pair_col"] = ev.apply(
        lambda r: f"cnt_{int(r['gd_before'])}_to_{int(r['gd_after'])}", axis=1
    )
    pivot_gd = (
        ev.pivot_table(index=["scoring_team", "contributor"],
                       columns="pair_col", values="gd_before",
                       aggfunc="size", fill_value=0)
          .reset_index()
    )

    # ── Time-bin cnt columns ──────────────────────────────────────
    ev["bin_col"] = ev["minute_bin"].apply(lambda b: f"cnt_bin_{b}")
    pivot_bin = (
        ev.pivot_table(index=["scoring_team", "contributor"],
                       columns="bin_col", values="gd_before",
                       aggfunc="size", fill_value=0)
          .reset_index()
    )

    # ── Time-bin EP columns ───────────────────────────────────────
    ev["ep_bin_col"] = ev["minute_bin"].apply(lambda b: f"ep_bin_{b}")
    ep_by_bin = (
        ev.groupby(["scoring_team", "contributor", "ep_bin_col"])["ep_timed"]
          .sum()
          .unstack(fill_value=0.0)
          .reset_index()
    )

    # ── Merge all ─────────────────────────────────────────────────
    keys = ["scoring_team", "contributor"]
    out = base.merge(pivot_gd, on=keys, how="left")
    out = out.merge(pivot_bin, on=keys, how="left")
    out = out.merge(ep_by_bin, on=keys, how="left")

    # ── Derived columns ───────────────────────────────────────────
    out["delta_ep_timed_vs_untimed"] = (
        out["exp_points_collected_timed"] - out["exp_points_collected_untimed"]
    )
    out["delta_ep_minus_goals"] = out["exp_points_collected_timed"] - out["goals_involved"]
    out["ratio_ep_per_goal"] = out["exp_points_collected_timed"] / out["goals_involved"]

    # ── Column ordering ───────────────────────────────────────────
    base_cols = [
        "scoring_team", "contributor", "goals_involved",
        "exp_points_collected_timed", "exp_points_collected_untimed",
        "delta_ep_timed_vs_untimed",
    ]
    cnt_gd_cols = sorted(c for c in out.columns if c.startswith("cnt_") and not c.startswith("cnt_bin_"))
    cnt_bin_cols = sorted(c for c in out.columns if c.startswith("cnt_bin_"))
    ep_bin_cols = sorted(c for c in out.columns if c.startswith("ep_bin_"))
    tail_cols = ["delta_ep_minus_goals", "ratio_ep_per_goal"]

    ordered = base_cols + cnt_gd_cols + cnt_bin_cols + ep_bin_cols + tail_cols
    # Keep only columns that exist
    ordered = [c for c in ordered if c in out.columns]

    return out[ordered].sort_values(
        ["goals_involved", "exp_points_collected_timed"], ascending=False
    ).reset_index(drop=True)


def scorer_table_for_season(goal_events: pd.DataFrame,
                            val_map_untimed: dict, val_map_timed: dict) -> pd.DataFrame:
    return _contributor_table(goal_events, "goalscorer", val_map_untimed, val_map_timed)


def sca1_table_for_season(goal_events: pd.DataFrame,
                           val_map_untimed: dict, val_map_timed: dict) -> pd.DataFrame:
    return _contributor_table(goal_events, "sca1_creator", val_map_untimed, val_map_timed)


def build_contributor_tables(results: dict, val_map_untimed: dict,
                             val_map_timed: dict, col: str) -> dict:
    """Build nested {league -> {season -> df}} for a given contributor column."""
    tables = {}
    for league, data in results.items():
        ge = data.get("goal_events")
        if not isinstance(ge, pd.DataFrame) or ge.empty:
            continue
        tables[league] = {}
        for season in sorted(ge["season"].dropna().unique()):
            ge_s = ge[ge["season"] == season].copy()
            tables[league][season] = _contributor_table(ge_s, col, val_map_untimed, val_map_timed)
    return tables


def build_goals_plus_assists_tables(scorer_tables: dict, sca1_tables: dict) -> dict:
    """Merge scorer + SCA1 tables into combined Goals+Assists tables."""
    out = {}
    leagues = sorted(set(list(scorer_tables.keys()) + list(sca1_tables.keys())))

    for league in leagues:
        out[league] = {}
        seasons = set()
        if league in scorer_tables:
            seasons |= set(scorer_tables[league].keys())
        if league in sca1_tables:
            seasons |= set(sca1_tables[league].keys())

        for season in sorted(seasons):
            g = scorer_tables.get(league, {}).get(season)
            a = sca1_tables.get(league, {}).get(season)

            if not isinstance(g, pd.DataFrame) and not isinstance(a, pd.DataFrame):
                continue

            keys = ["scoring_team", "contributor"]
            empty = pd.DataFrame(columns=keys)

            g = g.copy() if isinstance(g, pd.DataFrame) and not g.empty else empty.copy()
            a = a.copy() if isinstance(a, pd.DataFrame) and not a.empty else empty.copy()

            # Identify all numeric columns to sum
            numeric_cols_g = [c for c in g.columns if c not in keys]
            numeric_cols_a = [c for c in a.columns if c not in keys]
            all_numeric = sorted(set(numeric_cols_g + numeric_cols_a))

            for df in (g, a):
                for c in all_numeric:
                    if c not in df.columns:
                        df[c] = 0.0

            keep = keys + all_numeric
            g, a = g[keep].copy(), a[keep].copy()

            for df in (g, a):
                for c in all_numeric:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

            m = g.merge(a, on=keys, how="outer", suffixes=("_g", "_a"))

            for c in all_numeric:
                m[c] = m.get(f"{c}_g", 0).fillna(0) + m.get(f"{c}_a", 0).fillna(0)

            drop = [c for c in m.columns if c.endswith("_g") or c.endswith("_a")]
            m = m.drop(columns=drop, errors="ignore")

            # Recompute derived columns
            if "exp_points_collected_timed" in m.columns and "goals_involved" in m.columns:
                m["delta_ep_minus_goals"] = m["exp_points_collected_timed"] - m["goals_involved"]
                m["ratio_ep_per_goal"] = (
                    m["exp_points_collected_timed"] / m["goals_involved"].replace(0, np.nan)
                )
            if "exp_points_collected_timed" in m.columns and "exp_points_collected_untimed" in m.columns:
                m["delta_ep_timed_vs_untimed"] = (
                    m["exp_points_collected_timed"] - m["exp_points_collected_untimed"]
                )

            m = m.sort_values(
                ["goals_involved", "exp_points_collected_timed"], ascending=False
            ).reset_index(drop=True)
            out[league][season] = m

    return out


# ═══════════════════════════════════════════════════════════════════════
#  AGGREGATION  (roll up by league / season / total)
# ═══════════════════════════════════════════════════════════════════════

def _aggregate_one(df_all: pd.DataFrame) -> pd.DataFrame:
    """Group by (scoring_team, contributor) and SUM all numeric columns."""
    keys = ["scoring_team", "contributor"]
    numeric_cols = [c for c in df_all.columns if c not in keys]

    agg_map = {c: "sum" for c in numeric_cols}
    out = df_all.groupby(keys, as_index=False).agg(agg_map)

    # Recompute derived columns (ratios can't be summed)
    if "exp_points_collected_timed" in out.columns and "goals_involved" in out.columns:
        out["delta_ep_minus_goals"] = out["exp_points_collected_timed"] - out["goals_involved"]
        out["ratio_ep_per_goal"] = (
            out["exp_points_collected_timed"] / out["goals_involved"].replace(0, np.nan)
        )
    if "exp_points_collected_timed" in out.columns and "exp_points_collected_untimed" in out.columns:
        out["delta_ep_timed_vs_untimed"] = (
            out["exp_points_collected_timed"] - out["exp_points_collected_untimed"]
        )

    sort_by = [c for c in ["goals_involved", "exp_points_collected_timed"] if c in out.columns]
    if sort_by:
        out = out.sort_values(sort_by, ascending=False)
    return out.reset_index(drop=True)


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns exist; keep all numeric columns."""
    d = df.copy()
    renames = {
        "scoring_team": ["team", "squad", "Team", "Squad"],
        "contributor": ["goalscorer", "player", "scorer", "Player"],
        "goals_involved": ["goals_scored", "goals", "count", "n_goals"],
    }
    for target, candidates in renames.items():
        if target not in d.columns:
            for cand in candidates:
                if cand in d.columns:
                    d = d.rename(columns={cand: target})
                    break

    required = ["scoring_team", "contributor"]
    missing = [c for c in required if c not in d.columns]
    if missing:
        raise KeyError(f"Missing columns {missing}. Available: {list(d.columns)}")

    return d.copy()


def aggregate_tables(table_dict: dict):
    """
    Roll up {league -> {season -> df}} into:
      (total_by_league, total_by_season, total_all)
    """
    total_by_league = {}
    for league, seasons_dict in table_dict.items():
        parts = [_standardize(df) for df in seasons_dict.values()
                 if isinstance(df, pd.DataFrame) and not df.empty]
        if parts:
            total_by_league[league] = _aggregate_one(pd.concat(parts, ignore_index=True))

    all_seasons = sorted({s for lg in table_dict for s in table_dict[lg]})
    total_by_season = {}
    for season in all_seasons:
        parts = []
        for seasons_dict in table_dict.values():
            df = seasons_dict.get(season)
            if isinstance(df, pd.DataFrame) and not df.empty:
                parts.append(_standardize(df))
        if parts:
            total_by_season[season] = _aggregate_one(pd.concat(parts, ignore_index=True))

    parts = [_standardize(df)
             for seasons_dict in table_dict.values()
             for df in seasons_dict.values()
             if isinstance(df, pd.DataFrame) and not df.empty]
    total_all = _aggregate_one(pd.concat(parts, ignore_index=True)) if parts else pd.DataFrame()

    return total_by_league, total_by_season, total_all
