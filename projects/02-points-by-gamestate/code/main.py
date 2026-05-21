"""
Points by Gamestate (v3) — Main Pipeline
=========================================
Extends v2 with time-bin aware value model.

Run: python main.py
"""
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, OUTPUT_DIR, BIN_UNKNOWN
from extraction import load_leagues, build_goal_event_dataset
from analysis import (
    build_pre_goal_state_rows,
    state_summary,
    state_summary_timed,
    goal_value_table,
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
from dashboard import build_payload, build_dashboard_html


# ═══════════════════════════════════════════════════════════════════════
#  WIDE METRIC TABLES (for Excel)
# ═══════════════════════════════════════════════════════════════════════

def build_metric_table(metric: str, pooled_df: pd.DataFrame,
                       per_league: dict) -> pd.DataFrame:
    base = pooled_df[["gd_before", "gd_after", "n"]].copy()
    base["Pooled"] = pooled_df[metric].values
    for lg, df in per_league.items():
        if metric in df.columns:
            tmp = df[["gd_before", "gd_after", metric]].rename(columns={metric: lg})
            base = base.merge(tmp, on=["gd_before", "gd_after"], how="left")
    cols = ["gd_before", "gd_after", "n", "Pooled"] + [lg for lg in per_league if lg in base.columns]
    return base[cols].sort_values(["gd_before", "gd_after"]).reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════
#  EXCEL EXPORT
# ═══════════════════════════════════════════════════════════════════════

def _safe_sheet_name(s: str) -> str:
    s = str(s)
    for ch in [":", "\\", "/", "?", "*", "[", "]"]:
        s = s.replace(ch, "_")
    return s[:31]


def write_dict_sheets(path: str, sheets: dict):
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in sheets.items():
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            df.to_excel(w, sheet_name=_safe_sheet_name(name), index=False)
    print(f"  Saved: {path}")


def export_excel(scorer_tables, sca1_tables,
                 scorer_totals, sca1_totals,
                 transitions_pooled_f, transitions_by_league_f,
                 export_root):
    for label, totals in [("Goalscorer", scorer_totals), ("SCA1", sca1_totals)]:
        by_lg, by_ss, total_all = totals
        folder = os.path.join(export_root, label)
        os.makedirs(folder, exist_ok=True)
        write_dict_sheets(os.path.join(folder, "totals_by_league.xlsx"),
                          {lg: df for lg, df in by_lg.items()})
        write_dict_sheets(os.path.join(folder, "totals_by_season.xlsx"),
                          {f"Season_{s}": df for s, df in by_ss.items()})
        write_dict_sheets(os.path.join(folder, "totals_all.xlsx"), {"All": total_all})

    # Transition metric sheets (untimed)
    metrics = {}
    for m in ["pD", "pL", "pW", "exp_points", "exp_points_collected"]:
        if m in transitions_pooled_f.columns:
            metrics[m] = build_metric_table(m, transitions_pooled_f, transitions_by_league_f)
    path = os.path.join(export_root, "transition_tables.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for name, df in metrics.items():
            df.to_excel(w, sheet_name=name, index=False)
    print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════════════════════════════

def validate(goal_events_all, transitions_timed_pooled_f, val_map_timed):
    """Run sanity checks from the research doc (TODO 9)."""
    print("\n  Validation:")

    # 1. minute_bin distribution
    vc = goal_events_all["minute_bin"].value_counts()
    unknown_count = vc.get(BIN_UNKNOWN, 0)
    total = len(goal_events_all)
    print(f"    minute_bin distribution ({total:,} goals, {unknown_count} unknown):")
    for b in sorted(vc.index):
        print(f"      {b:>8}: {vc[b]:>6,}  ({100*vc[b]/total:.1f}%)")

    # 2. Late 0->1 should be worth more than early 0->1
    ep_01_early = val_map_timed.get((0, 1, "0-15"), None)
    ep_01_late = val_map_timed.get((0, 1, "75-90"), None)
    if ep_01_early is not None and ep_01_late is not None:
        status = "OK" if ep_01_late > ep_01_early else "UNEXPECTED"
        print(f"    0->1 early (0-15): {ep_01_early:.4f}  vs  late (75-90): {ep_01_late:.4f}  [{status}]")

    # 3. Late equalizer (-1->0) in 75-90 should be high
    ep_eq_late = val_map_timed.get((-1, 0, "75-90"), None)
    if ep_eq_late is not None:
        print(f"    -1->0 late (75-90) EP: {ep_eq_late:.4f}  (should be high)")

    print()


# ═══════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # ── 1. Load data ──────────────────────────────────────────────
    print("\n[1/7] Loading data...")
    all_leagues = load_leagues(DATA_DIR)

    # ── 2. Per-league analysis ────────────────────────────────────
    print("\n[2/7] Per-league analysis...")
    results = {}

    for league, league_data in all_leagues.items():
        goal_events, debug_store = build_goal_event_dataset(league_data)

        # Untimed
        pre_states = build_pre_goal_state_rows(goal_events)
        state_vals = state_summary(pre_states)
        goal_vals = goal_value_table(state_vals)
        transitions = transition_summary(goal_events, state_vals=state_vals)

        # Timed
        pre_states_t = build_pre_goal_state_rows(goal_events, carry_minute_bin=True)
        state_vals_t = state_summary_timed(pre_states_t)
        transitions_t = transition_summary_timed(goal_events, state_vals_timed=state_vals_t)

        results[league] = {
            "goal_events": goal_events,
            "debug_store": debug_store,
            "pre_states": pre_states,
            "state_vals": state_vals,
            "goal_value": goal_vals,
            "transitions": transitions,
            "state_vals_timed": state_vals_t,
            "transitions_timed": transitions_t,
        }

        print(f"  {league}: goals={len(goal_events):,}  "
              f"transitions={len(transitions):,}  "
              f"transitions_timed={len(transitions_t):,}")

    # ── 3. Pooled (all leagues) ───────────────────────────────────
    print("\n[3/7] Pooled analysis...")
    goal_events_all = pd.concat(
        [d["goal_events"].assign(league=lg)
         for lg, d in results.items() if not d["goal_events"].empty],
        ignore_index=True,
    )

    # Untimed pooled
    pre_states_pooled = build_pre_goal_state_rows(goal_events_all)
    state_vals_pooled = state_summary(pre_states_pooled)
    transitions_pooled = transition_summary(goal_events_all, state_vals=state_vals_pooled)

    # Timed pooled
    pre_states_pooled_t = build_pre_goal_state_rows(goal_events_all, carry_minute_bin=True)
    state_vals_pooled_t = state_summary_timed(pre_states_pooled_t)
    transitions_pooled_t = transition_summary_timed(goal_events_all, state_vals_timed=state_vals_pooled_t)

    print(f"  Total goals: {len(goal_events_all):,}")
    print(f"  Transitions pooled: {len(transitions_pooled):,} (untimed), {len(transitions_pooled_t):,} (timed)")

    # Prepped transitions
    transitions_pooled_f = prep_transitions(transitions_pooled)
    transitions_by_league_f = {}
    for league, d in results.items():
        t = d.get("transitions")
        if isinstance(t, pd.DataFrame) and not t.empty:
            transitions_by_league_f[league] = prep_transitions(t)

    transitions_pooled_timed_f = prep_transitions_timed(transitions_pooled_t)
    transitions_by_league_timed_f = {}
    for league, d in results.items():
        t = d.get("transitions_timed")
        if isinstance(t, pd.DataFrame) and not t.empty:
            transitions_by_league_timed_f[league] = prep_transitions_timed(t)

    # Value maps
    val_map_untimed = prep_value_map(transitions_pooled)
    val_map_timed = prep_value_map_timed(transitions_pooled_t)

    # Heatmap tables
    heatmap_pooled = build_heatmap_table(transitions_pooled_timed_f)
    heatmap_by_league = {lg: build_heatmap_table(df)
                         for lg, df in transitions_by_league_timed_f.items()}

    # ── 4. Validation ─────────────────────────────────────────────
    print("\n[4/7] Validation...")
    validate(goal_events_all, transitions_pooled_timed_f, val_map_timed)

    # ── 5. Build contributor tables ───────────────────────────────
    print("[5/7] Building contributor tables...")
    scorer_tables = build_contributor_tables(results, val_map_untimed, val_map_timed, "goalscorer")
    sca1_tables = build_contributor_tables(results, val_map_untimed, val_map_timed, "sca1_creator")
    ga_tables = build_goals_plus_assists_tables(scorer_tables, sca1_tables)

    print(f"  Scorer leagues: {list(scorer_tables.keys())}")
    print(f"  SCA1 leagues:   {list(sca1_tables.keys())}")
    print(f"  G+A leagues:    {list(ga_tables.keys())}")

    # ── 6. Aggregate totals ───────────────────────────────────────
    print("\n[6/7] Aggregating totals...")
    scorer_totals = aggregate_tables(scorer_tables)
    sca1_totals = aggregate_tables(sca1_tables)
    ga_totals = aggregate_tables(ga_tables)

    # ── 7. Export ─────────────────────────────────────────────────
    print("\n[7/7] Exporting...")
    export_root = os.path.join(OUTPUT_DIR, f"Exports_{ts}")
    os.makedirs(export_root, exist_ok=True)
    print(f"  Export root: {export_root}")

    export_excel(scorer_tables, sca1_tables,
                 scorer_totals, sca1_totals,
                 transitions_pooled_f, transitions_by_league_f,
                 export_root)

    # HTML dashboard
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = build_payload(
        scorer_tables=scorer_tables,
        sca1_tables=sca1_tables,
        ga_tables=ga_tables,
        scorer_totals=scorer_totals,
        sca1_totals=sca1_totals,
        ga_totals=ga_totals,
        transitions_pooled=transitions_pooled_f,
        transitions_by_league=transitions_by_league_f,
        transitions_pooled_timed=transitions_pooled_timed_f,
        transitions_by_league_timed=transitions_by_league_timed_f,
        heatmap_pooled=heatmap_pooled,
        heatmap_by_league=heatmap_by_league,
        created_at=created_at,
    )

    out_html = os.path.join(OUTPUT_DIR, f"Dashboard_{ts}.html")
    build_dashboard_html(payload, out_html=out_html, standalone=False)

    print(f"\nDone! Dashboard: {out_html}")


def inspect_match(results: dict, league: str, season_key: str, match_key: str):
    return results.get(league, {}).get("debug_store", {}).get(season_key, {}).get(match_key)


if __name__ == "__main__":
    main()
