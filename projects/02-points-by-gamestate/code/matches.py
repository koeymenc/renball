"""
matches.py — one pass over the match pickles: matches, goals, appearances
==========================================================================

For every match in match_data_final_<league>.pkl this extracts

  matches      one row per match: official score (FBref match_details), the
               score rebuilt from the shot table, load status
  goals        one row per goal in the shot table: minute, side, running score,
               scorer / SCA1 / SCA2 (cleaned names)
  apps         one row per player per match: team side, minutes, birth date
               (match date minus FBref's "years-days" age) — the identity key
               that separates namesakes

The shot table has no own goals, so a match whose rebuilt score falls short
of the official score is flagged (`og_affected`): its running score is wrong
from the missing goal on, and own-goal minutes are not in the data.

Extraction reads one league pickle at a time (they are large) and caches the
result under data/.cache/, keyed on each pickle's size + modification time
and EXTRACT_VERSION. Delete the folder or bump the version to force a re-read.
"""
from __future__ import annotations

import glob
import os
import pickle
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import DATA_DIR
from extraction import _clean_player_name, _normalize_cols, _parse_minute, _pick_col, _pick_exact, assign_bin

EXTRACT_VERSION = 3
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / ".cache"

LEAGUE_LABELS = {
    "Premier-League": "Premier League",
    "La-Liga": "La Liga",
    "Serie-A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Ligue-1": "Ligue 1",
    "Eredivisie": "Eredivisie",
}
TOP5 = ("Premier-League", "La-Liga", "Serie-A", "Bundesliga", "Ligue-1")


def league_files(data_dir: str = DATA_DIR) -> dict[str, Path]:
    files = sorted(f for f in glob.glob(os.path.join(data_dir, "match_data_final_*.pkl"))
                   if "CHECK" not in os.path.basename(f).upper())
    return {os.path.basename(f).replace("match_data_final_", "").replace(".pkl", ""): Path(f) for f in files}


# ── helpers ─────────────────────────────────────────────────────────────
def _score(s) -> tuple[int, int] | None:
    m = re.findall(r"\d+", str(s or ""))
    return (int(m[0]), int(m[1])) if len(m) >= 2 else None


def _birth(match_day: date | None, age) -> date | None:
    """FBref per-match age is 'YY-DDD' (years-days on the match date)."""
    m = re.match(r"^\s*(\d+)-(\d+)\s*$", str(age or ""))
    if match_day is None or not m:
        return None
    years, days = int(m.group(1)), int(m.group(2))
    try:
        anniversary = match_day.replace(year=match_day.year - years)
    except ValueError:                                   # 29 February
        anniversary = match_day.replace(year=match_day.year - years, day=28)
    return anniversary - timedelta(days=days)


def state_minute(minute_int, minute_raw) -> float:
    """Minute used for the team-minute panel: first-half stoppage counts as 45,
    anything after 90 as 90. NaN when the minute can't be parsed."""
    if minute_int is None or (isinstance(minute_int, float) and np.isnan(minute_int)):
        return np.nan
    if str(minute_raw).strip().startswith("45+"):
        return 45.0
    return float(min(int(minute_int), 90))


def _summary_tables(mobj: dict) -> dict[str, pd.DataFrame]:
    out = {}
    for k, v in mobj.items():
        if k.startswith("player_stats_") and isinstance(v, dict):
            tid = k[len("player_stats_"):]
            df = v.get(f"stats_{tid}_summary")
            if isinstance(df, pd.DataFrame) and not df.empty:
                out[tid] = _normalize_cols(df)
    return out


# ── one match ───────────────────────────────────────────────────────────
def extract_match(league: str, season: str, mkey: str, mobj) -> tuple[dict, list[dict], list[dict]]:
    mid = (re.search(r"/matches/([0-9a-f]{8})/", mkey) or [None, mkey])[1]
    row = {"league": league, "season": season, "match_id": mid, "match_url": mkey, "status": "ok"}
    if not isinstance(mobj, dict):
        row["status"] = "not loaded"
        return row, [], []
    if mobj.get("error"):
        row["status"] = "scrape failed"
        return row, [], []
    md = mobj.get("match_details") if isinstance(mobj.get("match_details"), dict) else {}
    shots = mobj.get("shots")
    df = shots.get("shots_all") if isinstance(shots, dict) else None
    if df is None or not hasattr(df, "loc"):
        row["status"] = "no shot table"
        return row, [], []

    try:
        day = pd.to_datetime(str(md.get("date")), format="%Y%m%d").date()
    except (ValueError, TypeError):
        day = None
    home, away = md.get("home_team_name"), md.get("away_team_name")
    hid, aid = md.get("home_team_id"), md.get("away_team_id")
    off = _score(md.get("score"))
    row.update(date=day.isoformat() if day else None, home=home, away=away, home_id=hid, away_id=aid,
               home_goals=off[0] if off else None, away_goals=off[1] if off else None)
    if not home or not away or off is None:
        row["status"] = "no match details"
        return row, [], []

    # squad name -> side, from match_details names and each side's own shot table
    side_of = {home: "home", away: "away"}
    for tid, side in ((hid, "home"), (aid, "away")):
        t = shots.get(f"shots_{tid}") if isinstance(shots, dict) else None
        if isinstance(t, pd.DataFrame) and not t.empty:
            tc = _normalize_cols(t)
            sc = _pick_col(tc.columns, "__Squad", prefer_prefix="unnamed")
            if sc:
                for s in tc[sc].dropna().astype(str).unique():
                    side_of.setdefault(s, side)

    # appearances: minutes + birth date per player, by side
    apps = []
    sums = _summary_tables(mobj)
    born_by_side: dict[str, dict[str, date | None]] = {"home": {}, "away": {}}
    for tid, sdf in sums.items():
        side = "home" if tid == hid else ("away" if tid == aid else None)
        if side is None:
            continue
        pc = _pick_col(sdf.columns, "__Player", prefer_prefix="unnamed")
        ac = _pick_col(sdf.columns, "__Age", prefer_prefix="unnamed")
        mc = _pick_col(sdf.columns, "__Min", prefer_prefix="unnamed")
        if pc is None:
            continue
        players = sdf[pc].map(_clean_player_name)
        mins = pd.to_numeric(sdf[mc], errors="coerce").fillna(0) if mc else pd.Series(0, index=sdf.index)
        ages = sdf[ac] if ac else pd.Series(None, index=sdf.index)
        for p, mn, ag in zip(players, mins, ages):
            if not isinstance(p, str) or p.lower().endswith(" players"):      # FBref's "16 Players" total row
                continue
            b = _birth(day, ag)
            born_by_side[side][p] = b
            apps.append({"match_id": mid, "side": side, "team": home if side == "home" else away,
                         "player": p, "born": b.isoformat() if b else None, "minutes": int(mn)})

    dfx = _normalize_cols(df)
    minute_col = _pick_col(dfx.columns, "__Minute", prefer_prefix="unnamed")
    squad_col = _pick_col(dfx.columns, "__Squad", prefer_prefix="unnamed")
    outcome_col = _pick_col(dfx.columns, "__Outcome", prefer_prefix="unnamed")
    player_col = _pick_col(dfx.columns, "__Player", prefer_prefix="unnamed")
    sca1_col = _pick_exact(dfx.columns, "SCA 1__Player")
    sca2_col = _pick_exact(dfx.columns, "SCA 2__Player")
    if outcome_col is None or squad_col is None or player_col is None:
        row["status"] = "no shot table"
        return row, [], apps

    g = dfx.loc[dfx[outcome_col].astype(str).str.lower().eq("goal")].copy()
    g["_raw"] = g[minute_col] if minute_col else np.nan
    g["_int"] = g["_raw"].apply(_parse_minute) if minute_col else np.nan
    g = g.sort_values("_int", kind="mergesort")

    goals, sh, sa, unmapped, unknown_minute = [], 0, 0, 0, 0
    for r in g.itertuples(index=False):
        rd = dict(zip(g.columns, r))
        side = side_of.get(str(rd[squad_col]))
        if side is None:
            unmapped += 1
            continue
        gd_before = sh - sa if side == "home" else sa - sh
        if side == "home":
            sh += 1
        else:
            sa += 1
        mi, mr = rd["_int"], rd["_raw"]
        if mi is None or (isinstance(mi, float) and np.isnan(mi)):
            unknown_minute += 1
        scorer = _clean_player_name(rd[player_col])
        sca1 = _clean_player_name(rd[sca1_col]) if sca1_col else np.nan
        sca2 = _clean_player_name(rd[sca2_col]) if sca2_col else np.nan
        bs = born_by_side[side]
        goals.append({
            "match_id": mid, "event_idx": len(goals) + 1, "side": side,
            "scoring_team": home if side == "home" else away,
            "opponent_team": away if side == "home" else home,
            "minute_raw": str(mr), "minute_int": mi, "minute_bin": assign_bin(mi, mr),
            "minute_state": state_minute(mi, mr),
            "gd_before": gd_before, "gd_after": gd_before + 1,
            "goalscorer": scorer, "sca1_creator": sca1, "sca2_creator": sca2,
            "goalscorer_born": (bs.get(scorer).isoformat() if isinstance(scorer, str) and bs.get(scorer) else None),
            "sca1_born": (bs.get(sca1).isoformat() if isinstance(sca1, str) and bs.get(sca1) else None),
            "sca2_born": (bs.get(sca2).isoformat() if isinstance(sca2, str) and bs.get(sca2) else None),
        })
    row.update(shot_home_goals=sh, shot_away_goals=sa, unmapped_goals=unmapped, unknown_minute_goals=unknown_minute)
    return row, goals, apps


# ── one league (cached) ─────────────────────────────────────────────────
def _cache_path(league: str, src: Path) -> Path:
    st = src.stat()
    return CACHE_DIR / f"{league}_v{EXTRACT_VERSION}_{st.st_size}_{st.st_mtime_ns}.pkl"


def extract_league(league: str, src: Path, *, verbose: bool = True) -> dict[str, pd.DataFrame]:
    cp = _cache_path(league, src)
    if cp.exists():
        return pd.read_pickle(cp)
    with open(src, "rb") as fh:
        data = pickle.load(fh)
    M, G, A = [], [], []
    for season, sobj in data.items():
        if not isinstance(sobj, dict):
            continue
        for mkey, mobj in sobj.items():
            row, goals, apps = extract_match(league, str(season), mkey, mobj)
            M.append(row)
            for x in goals + apps:
                x["league"], x["season"] = league, str(season)
            G += goals
            A += apps
    del data
    out = {"matches": pd.DataFrame(M), "goals": pd.DataFrame(G), "apps": pd.DataFrame(A)}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in CACHE_DIR.glob(f"{league}_v*.pkl"):
        old.unlink()
    pd.to_pickle(out, cp)
    if verbose:
        ok = (out["matches"]["status"] == "ok").sum()
        print(f"  {league:<15} matches ok={ok:>5} of {len(out['matches']):>5}  goals={len(out['goals']):>6}")
    return out


def load_all(data_dir: str = DATA_DIR, *, verbose: bool = True) -> dict[str, pd.DataFrame]:
    parts = {"matches": [], "goals": [], "apps": []}
    for league, src in league_files(data_dir).items():
        out = extract_league(league, src, verbose=verbose)
        for k in parts:
            parts[k].append(out[k])
    res = {k: pd.concat(v, ignore_index=True) for k, v in parts.items()}
    M = res["matches"]
    ok = M["status"] == "ok"
    M["og_affected"] = ok & ((M["shot_home_goals"] != M["home_goals"]) | (M["shot_away_goals"] != M["away_goals"]))
    M["shot_short"] = ok & ((M["shot_home_goals"] < M["home_goals"]) | (M["shot_away_goals"] < M["away_goals"]))
    M["shot_over"] = ok & ((M["shot_home_goals"] > M["home_goals"]) | (M["shot_away_goals"] > M["away_goals"]))
    return res
