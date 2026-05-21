"""
Points by Gamestate (v3) — Data Loading & Goal Event Extraction
Now includes minute_bin assignment on every goal event.
"""
import os
import re
import glob
import pickle

import numpy as np
import pandas as pd

from config import BIN_UNKNOWN


# ═══════════════════════════════════════════════════════════════════════
#  Column helpers
# ═══════════════════════════════════════════════════════════════════════

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Turn MultiIndex columns into unique 'level0__level1' strings."""
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [f"{a}__{b}" for a, b in out.columns]
    out.columns = [str(c).strip() for c in out.columns]
    return out


def _pick_col(cols, suffix: str, prefer_prefix: str = None):
    items = list(cols)
    suf = suffix.lower()
    if prefer_prefix is not None:
        pref = prefer_prefix.lower()
        hits = [c for c in items if c.lower().endswith(suf) and c.lower().startswith(pref)]
        if hits:
            return hits[0]
    hits = [c for c in items if c.lower().endswith(suf)]
    return hits[0] if hits else None


def _pick_exact(cols, target: str):
    t = target.replace(" ", "").lower()
    for c in cols:
        if str(c).replace(" ", "").lower() == t:
            return c
    return None


def _parse_minute(x):
    """Convert minute strings like '45+2' into integer 47."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, np.integer, float, np.floating)):
        return int(x)
    s = str(x).strip()
    m = re.match(r"^(\d+)(?:\+(\d+))?$", s)
    if m:
        return int(m.group(1)) + (int(m.group(2)) if m.group(2) else 0)
    m2 = re.search(r"\d+", s)
    return int(m2.group(0)) if m2 else np.nan


def _clean_player_name(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = re.sub(r"\s*\([^)]*\)\s*$", "", str(x).strip()).strip()
    return s if s else np.nan


# ═══════════════════════════════════════════════════════════════════════
#  Time-bin assignment
# ═══════════════════════════════════════════════════════════════════════

def assign_bin(minute_int, minute_raw) -> str:
    """
    Assign a 15-minute time bin.

    Stoppage-time rules:
      - '45+X' (first-half stoppage) → '30-45'
      - '90+X' or minute_int > 90     → '75-90'
    """
    if minute_int is None or (isinstance(minute_int, float) and np.isnan(minute_int)):
        return BIN_UNKNOWN

    raw_str = str(minute_raw).strip()

    # First-half stoppage: '45+1', '45+2', etc.
    if raw_str.startswith("45+"):
        return "30-45"
    # Second-half / extra-time stoppage
    if raw_str.startswith("90+") or minute_int > 90:
        return "75-90"

    minute_int = int(minute_int)
    if minute_int <= 15:
        return "0-15"
    if minute_int <= 30:
        return "15-30"
    if minute_int <= 45:
        return "30-45"
    if minute_int <= 60:
        return "45-60"
    if minute_int <= 75:
        return "60-75"
    return "75-90"


# ═══════════════════════════════════════════════════════════════════════
#  Data loading
# ═══════════════════════════════════════════════════════════════════════

def load_leagues(data_dir: str) -> dict:
    files = sorted(
        f for f in glob.glob(os.path.join(data_dir, "match_data_final_*.pkl"))
        if "CHECK" not in os.path.basename(f).upper()
    )
    print(f"Files found: {len(files)}")
    for f in files:
        print(f"  - {os.path.basename(f)}")

    leagues = {}
    for fpath in files:
        name = os.path.basename(fpath).replace("match_data_final_", "").replace(".pkl", "")
        with open(fpath, "rb") as fh:
            leagues[name] = pickle.load(fh)

    print(f"Loaded leagues: {list(leagues.keys())}")
    return leagues


# ═══════════════════════════════════════════════════════════════════════
#  Per-match goal event extraction
# ═══════════════════════════════════════════════════════════════════════

def extract_match_goal_events(season_key: str, match_key: str, match_obj):
    """
    Extract goal events from a single match.

    Returns
    -------
    events_df : DataFrame — one row per goal (running score, GD, minute_bin)
    debug_df  : DataFrame — events_df + original shot-table columns
    meta      : dict      — teams, final score
    """
    if not isinstance(match_obj, dict):
        return None, None, None
    if match_obj.get("error") == "Failed to retrieve data after repeated attempts.":
        return None, None, None

    shots = match_obj.get("shots")
    if not isinstance(shots, dict):
        return None, None, None

    df = shots.get("shots_all")
    if df is None or not hasattr(df, "loc"):
        return None, None, None

    dfx = _normalize_cols(df)

    minute_col = _pick_col(dfx.columns, "__Minute", prefer_prefix="unnamed")
    squad_col = _pick_col(dfx.columns, "__Squad", prefer_prefix="unnamed")
    outcome_col = _pick_col(dfx.columns, "__Outcome", prefer_prefix="unnamed")
    goalscorer_col = _pick_col(dfx.columns, "__Player", prefer_prefix="unnamed")
    sca1_col = _pick_exact(dfx.columns, "SCA 1__Player")
    sca2_col = _pick_exact(dfx.columns, "SCA 2__Player")

    if outcome_col is None or squad_col is None or goalscorer_col is None:
        return None, None, None

    goals = dfx.loc[dfx[outcome_col].astype(str).str.lower().eq("goal")].copy()

    all_teams = pd.Series(dfx[squad_col]).dropna().astype(str).value_counts().index.tolist()
    teams = all_teams[:2]
    if len(teams) < 2 and not goals.empty:
        teams = goals[squad_col].dropna().astype(str).value_counts().index.tolist()[:2]

    team_a = teams[0] if len(teams) > 0 else None
    team_b = teams[1] if len(teams) > 1 else None

    meta = {"season": season_key, "match_key": match_key,
            "teams": [team_a, team_b], "final_goals": {}}

    if goals.empty or team_a is None or team_b is None:
        return pd.DataFrame(), pd.DataFrame(), meta

    # Parse minute
    if minute_col:
        goals["_minute_raw"] = goals[minute_col]
        goals["_minute_int"] = goals[minute_col].apply(_parse_minute)
    else:
        goals["_minute_raw"] = np.nan
        goals["_minute_int"] = np.nan

    goals["_scoring_team"] = goals[squad_col].astype(str)
    goals = goals.sort_values("_minute_int", kind="mergesort").reset_index(drop=True)

    # Build running score
    score_a = score_b = 0
    rows = []

    for _, row in goals.iterrows():
        scorer_team = row["_scoring_team"]
        sa_before, sb_before = score_a, score_b

        if scorer_team == team_a:
            score_a += 1
            opponent = team_b
            gd_before = sa_before - sb_before
            gd_after = score_a - score_b
        elif scorer_team == team_b:
            score_b += 1
            opponent = team_a
            gd_before = sb_before - sa_before
            gd_after = score_b - score_a
        else:
            continue

        minute_raw = row.get("_minute_raw", np.nan)
        minute_int = row.get("_minute_int", np.nan)

        rows.append({
            "season": season_key,
            "match_key": match_key,
            "event_idx": len(rows) + 1,
            "minute_raw": minute_raw,
            "minute_int": minute_int,
            "minute_bin": assign_bin(minute_int, minute_raw),
            "teamA": team_a,
            "teamB": team_b,
            "scoring_team": scorer_team,
            "opponent_team": opponent,
            "scoreA_before": sa_before,
            "scoreB_before": sb_before,
            "scoreA_after": score_a,
            "scoreB_after": score_b,
            "gd_before": gd_before,
            "gd_after": gd_after,
            "goalscorer": _clean_player_name(row.get(goalscorer_col, np.nan)),
            "sca1_creator": _clean_player_name(row.get(sca1_col, np.nan)) if sca1_col else np.nan,
            "sca2_creator": _clean_player_name(row.get(sca2_col, np.nan)) if sca2_col else np.nan,
        })

    events_df = pd.DataFrame(rows)
    if events_df.empty:
        return events_df, events_df.copy(), meta

    # Final score + result
    final_goals = {team_a: int(score_a), team_b: int(score_b)}
    meta["final_goals"] = final_goals

    events_df["final_goals_for"] = events_df["scoring_team"].map(final_goals)
    events_df["final_goals_against"] = events_df["opponent_team"].map(final_goals)

    gf = events_df["final_goals_for"]
    ga = events_df["final_goals_against"]
    events_df["final_result"] = np.where(gf > ga, "W", np.where(gf == ga, "D", "L"))
    events_df["final_points"] = events_df["final_result"].map({"W": 3, "D": 1, "L": 0}).astype(int)

    # Debug DF
    payload = (goals.drop(columns=["_minute_raw", "_minute_int", "_scoring_team"], errors="ignore")
                    .reset_index(drop=True))
    debug_df = pd.concat([events_df.reset_index(drop=True), payload], axis=1)

    return events_df, debug_df, meta


# ═══════════════════════════════════════════════════════════════════════
#  Build full dataset across all seasons
# ═══════════════════════════════════════════════════════════════════════

def build_goal_event_dataset(data: dict):
    all_events = []
    debug_store = {}

    for season_key, season_obj in data.items():
        if not isinstance(season_obj, dict):
            continue
        debug_store.setdefault(season_key, {})

        for match_key, match_obj in season_obj.items():
            events_df, debug_df, _ = extract_match_goal_events(season_key, match_key, match_obj)
            if events_df is None:
                continue
            debug_store[season_key][match_key] = debug_df
            if not events_df.empty:
                all_events.append(events_df)

    goal_events = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    return goal_events, debug_store
