"""
build.py - Renball Project 03 (The True Contributors) build orchestrator
========================================================================

Reuses project 02's pipeline (no mutation) to produce:
  - data/data.json                 -> editorial payload (analysis.html)
  - data/dashboard/manifest.json   -> Tabulator dashboard index
  - data/dashboard/<view>.json     -> one file per ranking view (lazy-loaded)

Pipeline:
  1. Run project 02's analysis -> goal_events, val_maps, scorer/SCA1 tables
  2. Build SCA2 contributor tables (project 02's _contributor_table)
  3. enrich.load_player_meta() -> minutes / pos / age (per-season + pooled)
  4. enrich.build_three_layer_tables() -> 3-layer credit tables (Q1a base)
  5. enrich.build_weighted_credit_*() -> weighted credit tables (Q1b base)
  6. Build Q1a, Q1b, Q2, Q3, Q4, Q5, Q6, Q7 outputs
  7. Write data/data.json + data/dashboard/*.json + manifest.json
  8. Print summary numbers for the user's Phase 1 review

ASCII-only prints (Windows console safety).

Run:
    python code/build.py

Environment:
    RENBALL_MATCH_DATA_PATH  -> per-league match-event pickles (project 02)
    RENBALL_DATA_PATH        -> READY_DATA/ for FULL_DICT_ROWS.pkl
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Console stdout: force UTF-8 so player names with diacritics don't crash
# Windows cp1252 on the summary print at the end (data JSONs are already UTF-8).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Make project 02's code importable without mutating it.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_DIR.parent.parent
P02_CODE = REPO_ROOT / "projects" / "02-points-by-gamestate" / "code"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(P02_CODE))

from config import DATA_DIR, KEEP_SET  # project 02
from extraction import load_leagues, build_goal_event_dataset
from analysis import (
    build_pre_goal_state_rows,
    state_summary,
    state_summary_timed,
    transition_summary,
    transition_summary_timed,
    prep_value_map,
    prep_value_map_timed,
    build_contributor_tables,
    aggregate_tables,
)

import enrich  # this project


# ════════════════════════════════════════════════════════════════════════
# Output paths
# ════════════════════════════════════════════════════════════════════════
DATA_DIR_OUT = PROJECT_DIR / "data"
DATA_JSON = DATA_DIR_OUT / "data.json"
DASHBOARD_DIR = DATA_DIR_OUT / "dashboard"
DASHBOARD_MANIFEST = DASHBOARD_DIR / "manifest.json"
STATIC_DIR = DATA_DIR_OUT / "static"
ACTUAL_MVPS_JSON = STATIC_DIR / "actual_mvps.json"


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


def _clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_clean_for_json(v) for v in obj)
    return _py(obj)


def _write_json(path: Path, obj, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"ensure_ascii": False, "default": str}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    cleaned = _clean_for_json(obj)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, **kwargs)
    size_kb = path.stat().st_size / 1024
    rel = path.relative_to(PROJECT_DIR)
    if size_kb >= 1024:
        print(f"  Wrote {rel} ({size_kb / 1024:,.1f} MB)")
    else:
        print(f"  Wrote {rel} ({size_kb:,.1f} KB)")


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════
def _filter_tables_top5(nested: dict) -> dict:
    return {lg: ss for lg, ss in nested.items()
            if lg in enrich.TOP5_LEAGUES}


def _load_actual_mvps() -> dict:
    if not ACTUAL_MVPS_JSON.exists():
        return {}
    try:
        with open(ACTUAL_MVPS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [actual_mvps] failed to load: {e!r}")
        return {}


# ════════════════════════════════════════════════════════════════════════
# Pipeline: run project 02's analysis end-to-end
# ════════════════════════════════════════════════════════════════════════
def run_p02_pipeline() -> dict:
    print(f"[1/8] Loading match data from: {DATA_DIR}")
    all_leagues = load_leagues(DATA_DIR)

    print("\n[2/8] Per-league analysis (project 02)...")
    results: dict = {}
    for league, league_data in all_leagues.items():
        goal_events, _ = build_goal_event_dataset(league_data)

        # Untimed
        pre = build_pre_goal_state_rows(goal_events)
        sv = state_summary(pre)
        tr = transition_summary(goal_events, state_vals=sv)

        # Timed
        pre_t = build_pre_goal_state_rows(goal_events, carry_minute_bin=True)
        sv_t = state_summary_timed(pre_t)
        tr_t = transition_summary_timed(goal_events, state_vals_timed=sv_t)

        results[league] = {
            "goal_events": goal_events,
            "state_vals": sv, "transitions": tr,
            "state_vals_timed": sv_t, "transitions_timed": tr_t,
        }
        print(f"  {league}: goals={len(goal_events):,}  "
              f"transitions={len(tr):,}  timed={len(tr_t):,}")

    print("\n[3/8] Pooled analysis...")
    goal_events_all = pd.concat(
        [d["goal_events"].assign(league=lg)
         for lg, d in results.items() if not d["goal_events"].empty],
        ignore_index=True,
    )

    pre_pooled = build_pre_goal_state_rows(goal_events_all)
    sv_pooled = state_summary(pre_pooled)
    tr_pooled = transition_summary(goal_events_all, state_vals=sv_pooled)

    pre_pooled_t = build_pre_goal_state_rows(goal_events_all, carry_minute_bin=True)
    sv_pooled_t = state_summary_timed(pre_pooled_t)
    tr_pooled_t = transition_summary_timed(goal_events_all,
                                            state_vals_timed=sv_pooled_t)

    val_map_untimed = prep_value_map(tr_pooled)
    val_map_timed = prep_value_map_timed(tr_pooled_t)
    print(f"  goal_events_all: {len(goal_events_all):,}")
    print(f"  val_map_timed entries: {len(val_map_timed):,}  "
          f"val_map_untimed entries: {len(val_map_untimed):,}")

    print("\n[4/8] Contributor tables (project 02 + SCA2)...")
    scorer_tables = build_contributor_tables(results, val_map_untimed, val_map_timed,
                                              "goalscorer")
    sca1_tables = build_contributor_tables(results, val_map_untimed, val_map_timed,
                                             "sca1_creator")
    sca2_tables = enrich.build_sca2_tables(results, val_map_untimed, val_map_timed)
    three_layer_tables = enrich.build_three_layer_tables(scorer_tables, sca1_tables,
                                                           sca2_tables)
    print(f"  scorer leagues:    {len(scorer_tables)}")
    print(f"  SCA1 leagues:      {len(sca1_tables)}")
    print(f"  SCA2 leagues:      {len(sca2_tables)}")
    print(f"  three-layer leagues: {len(three_layer_tables)}")

    print("\n[5/8] Aggregating totals...")
    scorer_totals = aggregate_tables(scorer_tables)
    sca1_totals = aggregate_tables(sca1_tables)
    sca2_totals = aggregate_tables(sca2_tables)
    three_layer_totals = aggregate_tables(three_layer_tables)

    # Top-5 only versions for per-90 boards
    three_layer_top5 = aggregate_tables(_filter_tables_top5(three_layer_tables))
    sca2_top5_totals = aggregate_tables(_filter_tables_top5(sca2_tables))

    return {
        "results": results,
        "goal_events_all": goal_events_all,
        "val_map_timed": val_map_timed,
        "val_map_untimed": val_map_untimed,
        "scorer_tables": scorer_tables,
        "sca1_tables": sca1_tables,
        "sca2_tables": sca2_tables,
        "three_layer_tables": three_layer_tables,
        "scorer_totals": scorer_totals,
        "sca1_totals": sca1_totals,
        "sca2_totals": sca2_totals,
        "sca2_top5_totals": sca2_top5_totals,
        "three_layer_totals": three_layer_totals,
        "three_layer_top5_totals": three_layer_top5,
    }


# ════════════════════════════════════════════════════════════════════════
# Weighted credit (Q1b) pipeline
# ════════════════════════════════════════════════════════════════════════
def build_weighted_pipeline(goal_events_all: pd.DataFrame, val_map_timed: dict,
                              val_map_untimed: dict) -> dict:
    # Per-event credit (with league/season carried through)
    per_event = enrich.build_weighted_credit_per_event(
        goal_events_all, val_map_timed, val_map_untimed, KEEP_SET
    )
    print(f"  weighted per-event rows: {len(per_event):,}")

    # Top-5 only variant
    per_event_top5 = per_event[per_event["league"].isin(enrich.TOP5_LEAGUES)] \
        if "league" in per_event.columns else per_event
    print(f"  weighted per-event Top-5: {len(per_event_top5):,}")

    weighted_top5_pooled = enrich.aggregate_weighted_credit(per_event_top5,
                                                              scope="pooled")
    weighted_all_pooled = enrich.aggregate_weighted_credit(per_event, scope="pooled")

    return {
        "per_event": per_event,
        "per_event_top5": per_event_top5,
        "weighted_top5_pooled": weighted_top5_pooled,
        "weighted_all_pooled": weighted_all_pooled,
    }


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════
def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Project 03 - The True Contributors  ({created_at})")
    print("=" * 72)

    ctx = run_p02_pipeline()

    print("\n[6/8] Loading player metadata (minutes / pos / age)...")
    player_meta = enrich.load_player_meta()

    print("\n[7/8] Weighted-credit pipeline (Q1b)...")
    weighted = build_weighted_pipeline(
        ctx["goal_events_all"], ctx["val_map_timed"], ctx["val_map_untimed"]
    )

    print("\n[8/8] Building Q1...Q7 outputs...")

    three_layer_all = ctx["three_layer_totals"][2]
    three_layer_all_top5 = ctx["three_layer_top5_totals"][2]
    actual_mvps = _load_actual_mvps()

    q1a = enrich.build_q1a_full_credit(three_layer_all_top5, player_meta)
    q1b = enrich.build_q1b_weighted_credit(weighted["weighted_top5_pooled"],
                                              player_meta)
    q1_shift = enrich.build_q1_rank_shift(q1a["rows"], q1b["rows"], top_n=30)

    q2 = enrich.build_q2_mvp_grid(ctx["three_layer_tables"], player_meta,
                                     actual_mvps=actual_mvps)
    q3 = enrich.build_q3_late_game(three_layer_all)
    q4 = enrich.build_q4_efficiency(three_layer_all)
    q5 = enrich.build_q5_position_adjusted(three_layer_all_top5, player_meta)
    q6 = enrich.build_q6_hidden_architects(
        sca2_total_all=ctx["sca2_totals"][2],
        sca2_total_top5=ctx["sca2_top5_totals"][2],
        scorer_total_all=ctx["scorer_totals"][2],
        sca1_total_all=ctx["sca1_totals"][2],
        player_meta=player_meta,
    )
    q7 = enrich.build_q7_young_players(three_layer_all_top5, player_meta)

    # ── Editorial payload (data.json) ──────────────────────────────
    leagues = sorted(ctx["results"].keys())
    seasons = sorted({str(s) for d in ctx["results"].values()
                       for s in d["goal_events"]["season"].dropna().unique()})

    editorial = {
        "meta": {
            "generated_at": created_at,
            "leagues": leagues,
            "seasons": seasons,
            "total_goals": int(len(ctx["goal_events_all"])),
            "total_players_with_meta": len(player_meta["pooled"]),
        },
        "scope_note_global": enrich.PER_90_SCOPE_NOTE,
        "q1a_full_credit": q1a,
        "q1b_weighted_credit": q1b,
        "q1_rank_shift": q1_shift,
        "q2_mvp_grid": q2,
        "q3_late_game": q3,
        "q4_efficiency": q4,
        "q5_position": q5,
        "q6_architects": q6,
        "q7_young": q7,
    }

    _write_json(DATA_JSON, editorial)

    # ── Dashboard payload (one file per Q view) ────────────────────
    _write_dashboard_files(editorial, created_at)

    # ── Summary print for Phase 1 review ───────────────────────────
    print("\n" + "=" * 72)
    print("PHASE 1 SUMMARY  (review these before HTML in Phase 2)")
    print("=" * 72)
    _print_phase1_summary(editorial)


def _write_dashboard_files(editorial: dict, created_at: str) -> None:
    """One JSON per Q view, plus a manifest at data/dashboard/manifest.json."""
    if DASHBOARD_DIR.exists():
        for stale in DASHBOARD_DIR.glob("*.json"):
            if stale.name != "manifest.json":
                stale.unlink()

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    views: dict = {
        "Q1a Full-Credit Leaderboard": ("q1a_full_credit.json", editorial["q1a_full_credit"]),
        "Q1b Weighted-Credit Leaderboard": ("q1b_weighted_credit.json", editorial["q1b_weighted_credit"]),
        "Q1 Rank Shift (A vs B)": ("q1_rank_shift.json", {"rows": editorial["q1_rank_shift"]}),
        "Q2 MVP Grid": ("q2_mvp_grid.json", editorial["q2_mvp_grid"]),
        "Q3 Late-Game Specialists": ("q3_late_game.json", editorial["q3_late_game"]),
        "Q4 Efficiency Ratios": ("q4_efficiency.json", editorial["q4_efficiency"]),
        "Q5 Position-Adjusted": ("q5_position.json", editorial["q5_position"]),
        "Q6 Hidden Architects (SCA2)": ("q6_architects.json", editorial["q6_architects"]),
        "Q7 Young Players": ("q7_young.json", editorial["q7_young"]),
    }

    manifest = {
        "meta": {
            "created_at": created_at,
            "leagues": editorial["meta"]["leagues"],
            "seasons": editorial["meta"]["seasons"],
        },
        "scope_note_global": editorial["scope_note_global"],
        "views": {},
    }

    for label, (fname, payload) in views.items():
        out = DASHBOARD_DIR / fname
        _write_json(out, payload, compact=True)
        manifest["views"][label] = {
            "file": fname,
            "size_kb": round(out.stat().st_size / 1024, 1),
        }

    _write_json(DASHBOARD_MANIFEST, manifest)


# ════════════════════════════════════════════════════════════════════════
# Phase 1 summary printer
# ════════════════════════════════════════════════════════════════════════
def _hdr(s: str) -> None:
    print(f"\n--- {s} ---")


def _row_short(r: dict, cols: list) -> str:
    parts = []
    for c in cols:
        v = r.get(c)
        if v is None:
            parts.append(f"{c}=-")
            continue
        if isinstance(v, float):
            parts.append(f"{c}={v:.3f}")
        else:
            parts.append(f"{c}={v}")
    return "  ".join(parts)


def _print_phase1_summary(ed: dict) -> None:
    meta = ed["meta"]
    print(f"\nDataset: {meta['total_goals']:,} goal events, "
          f"{len(meta['leagues'])} leagues, {len(meta['seasons'])} seasons")
    print(f"  leagues: {', '.join(meta['leagues'])}")
    print(f"  seasons: {meta['seasons'][0]} ... {meta['seasons'][-1]}")
    print(f"  players with minutes/pos/age: {meta['total_players_with_meta']:,}")

    _hdr("Q1a - Top 10 EP/90 (full credit, >=1000 min, Top-5)")
    for r in ed["q1a_full_credit"]["rows"][:10]:
        print(" ", _row_short(r, ["rank", "player", "primary_team", "minutes",
                                    "ep_per_90", "goals_involved", "pos", "age"]))

    _hdr("Q1b - Top 10 weighted EP/90 (0.40/0.35/0.25, Top-5)")
    for r in ed["q1b_weighted_credit"]["rows"][:10]:
        print(" ", _row_short(r, ["rank", "player", "primary_team", "minutes",
                                    "ep_weighted_per_90", "goals_involved", "pos"]))

    _hdr("Q1 - Biggest rank shifts A vs B (top 10 by abs delta)")
    shifts = [s for s in ed["q1_rank_shift"] if s["delta"] is not None]
    shifts.sort(key=lambda r: -abs(r["delta"]))
    for r in shifts[:10]:
        print(f"  {r['player']:<32}  A={r['rank_a']:>3}  B={r['rank_b']:>3}  "
              f"delta={r['delta']:+d}")

    _hdr("Q2 - Per-Season MVPs (model picks, sample)")
    grid = ed["q2_mvp_grid"]["grid"]
    seasons_grid = ed["q2_mvp_grid"]["seasons"]
    for season in seasons_grid:
        line_parts = []
        for lg in ed["q2_mvp_grid"]["leagues"]:
            cell = grid.get(lg, {}).get(season, {}).get("model_pick")
            who = (f"{cell['player']} ({cell['ep_per_90']:.2f})"
                   if cell else "-")
            line_parts.append(f"{lg[:3]}:{who}")
        print(f"  {season}  " + "  |  ".join(line_parts))
    _hdr("Q2 - Combined 5L MVPs (model)")
    for season, cell in ed["q2_mvp_grid"]["combined_5l"].items():
        pick = cell.get("model_pick")
        actual = cell.get("actual_ballon_dor")
        actual_name = (actual.get("name") if isinstance(actual, dict) else None) or "-"
        if pick:
            print(f"  {season}  model: {pick['player']} ({pick['ep_per_90']:.2f}, "
                  f"{pick['primary_team']})  | actual: {actual_name}")
        else:
            print(f"  {season}  model: -  | actual: {actual_name}")

    _hdr("Q3 - Top 10 late-game share (>=15 credits)")
    for r in ed["q3_late_game"]["rows"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<28}  share={r['share_late']:.3f}  "
              f"ep_late={r['ep_late']:.2f}/{r['ep_total']:.2f}  "
              f"credits={r['goals_involved']}")

    _hdr("Q4a - Top 10 EP per goal involved (>=5 credits)")
    for r in ed["q4_efficiency"]["q4a"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<28}  "
              f"ratio={r['ratio_ep_per_goal']:.3f}  "
              f"ep={r['ep_timed']:.2f}  credits={r['goals_involved']}")
    _hdr("Q4b - Top 10 time-aware multiplier (ep_timed / ep_untimed)")
    for r in ed["q4_efficiency"]["q4b"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<28}  "
              f"mult={r['multiplier']:.3f}  "
              f"timed={r['ep_timed']:.2f}/untimed={r['ep_untimed']:.2f}  "
              f"credits={r['goals_involved']}")
    print(f"\n  [Q4c]  {ed['q4_efficiency']['q4c_note']}")

    _hdr("Q5 - Position-adjusted top 5 per panel")
    for pos, entry in ed["q5_position"]["panels"].items():
        rows = entry["rows"]
        flag = ""
        if pos == "GK" and entry.get("structural_zero"):
            flag = "  [STRUCTURAL ZERO - empty-state callout]"
        print(f"  {pos}{flag}")
        if not rows:
            print(f"    (no players cleared {ed['q5_position']['min_minutes']}-min threshold)")
        for r in rows:
            print(f"    {r['rank']}. {r['player']:<26}  "
                  f"ep90={r['ep_per_90']:.3f}  mins={r['minutes']}  "
                  f"credits={r['goals_involved']}")

    _hdr("Q6 - Top 10 SCA2 EP (absolute)")
    for r in ed["q6_architects"]["abs_top"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<28}  ({r['primary_team']:<22})  "
              f"ep_sca2={r['ep_timed']:.2f}  events={r['goals_involved']}")
    _hdr("Q6 - Top 10 SCA2 EP/90 (Top-5, >=1000 min)")
    for r in ed["q6_architects"]["per_90_top"]["rows"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<28}  ({r['primary_team']:<22})  "
              f"ep90_sca2={r['ep_per_90']:.3f}  mins={r['minutes']}  "
              f"pos={r['pos']}")
    _hdr("Q6 - Layer breakdown top 5 (stacked-bar preview)")
    for r in ed["q6_architects"]["layer_breakdown"][:5]:
        total = r["ep_total"] or 1.0
        ps = 100 * r["ep_scorer"] / total
        p1 = 100 * r["ep_sca1"] / total
        p2 = 100 * r["ep_sca2"] / total
        print(f"  {r['player']:<28}  total={total:.2f}  "
              f"scorer={ps:.0f}%  sca1={p1:.0f}%  sca2={p2:.0f}%")

    _hdr("Q7 - Top 10 young players (age <=23, >=500 min, Top-5)")
    for r in ed["q7_young"]["rows"][:10]:
        print(f"  {r['rank']:>2}  {r['player']:<26}  age={r['age']:.1f}  "
              f"ep90={r['ep_per_90']:.3f}  mins={r['minutes']}  "
              f"credits={r['goals_involved']}  ({r['primary_team']})")

    print("\n" + "=" * 72)
    print("Done. Review the numbers above before Phase 2 (analysis.html).")
    print("=" * 72)


if __name__ == "__main__":
    main()
