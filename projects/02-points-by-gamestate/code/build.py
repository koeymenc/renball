"""
build.py — Renball Project 02 (Not All Goals Are Equal)
=======================================================

What a goal is worth depends on the score and the minute. This build prices
every goal from a team-minute model of expected final points and writes

  data/data.json                  editorial payload (analysis.html, slides, X)
  data/dashboard/                 Tabulator dashboard: manifest + one JSON per
                                  (dataset, view)
  data/og_affected_matches.csv    matches whose shot table is missing goals
                                  (own goals), for a later FBref backfill

Pipeline
  1. matches.load_all(): official scores, goals, appearances (cached per league)
  2. Model sample: loaded matches whose shot-table score equals the official
     score. Matches with missing goals (own goals: their running score is
     wrong) are excluded; including them is the sensitivity check.
  3. value_model: V(gd, bin) from team-minutes, goal values
     V(gd + 1, bin) − V(gd, bin), time-blind U(gd + 1) − U(gd)
  4. Bootstrap over matches (1,000 resamples within league, seed 2026):
     intervals on every cell, the headline ratios and every player total
  5. Held-out check: values from 2017-18 to 2021-22 predict 2022-23 and
     2023-24 results (Brier score vs a time-blind model and the base rate)
  6. Players: identity = name + birth date (from FBref's per-match age), so
     namesakes are kept apart; a goal credits its scorer and its SCA1, once
     per player; minutes come from the same matches as the goals
  7. Takeaways composed from the computed values

Unit of analysis: the team-minute for state values; the goal for goal values;
the player (all matches in scope) for the boards.

Run:
    python code/build.py

Env: RENBALL_MATCH_DATA_PATH → folder with match_data_final_<league>.pkl
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from config import KEEP_PAIRS, MAX_GD, MIN_GD, TIME_BINS  # noqa: E402
import matches as X                                         # noqa: E402
import value_model as VM                                    # noqa: E402
from analysis import _contributor_table, aggregate_tables   # noqa: E402
from dashboard import COLUMN_HELP                           # noqa: E402
import dashboard_files as DF                                # noqa: E402

DATA_DIR_OUT = PROJECT_DIR / "data"
DATA_JSON = DATA_DIR_OUT / "data.json"
DASHBOARD_DIR = DATA_DIR_OUT / "dashboard"
OG_CSV = DATA_DIR_OUT / "og_affected_matches.csv"

SEED = 2026
N_BOOT = 1000
SPARSE_MATCHES = 30          # a cell seen in fewer matches is shown muted
MIN_MINUTES_P90 = 900        # per-90 board: at least ten full matches
MIN_INVOLVEMENTS = 20        # timing-premium board: at least this many goal involvements
SHORT_MINUTES = 3000         # per-90 board: "short career" marker in the copy
N_TEST_SEASONS = 2           # held-out check: the last two seasons
BAND_WIDTH = 0.25            # reliability check: bands of predicted EP
BAND_MIN_MINUTES = 500       # ...dropped below this many held-out team-minutes
LATE, EARLY = len(TIME_BINS) - 1, 0
GI = lambda g: g - MIN_GD    # noqa: E731  goal difference -> row index


def r(x, n=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def fx(x, d: int = 2) -> str:
    """Half-up on the shortest decimal form, the way the page's Intl.NumberFormat rounds (0.955 -> 0.96)."""
    return str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def gd_label(g: int) -> str:
    return "0" if g == 0 else f"{'+' if g > 0 else '−'}{abs(g)}"


def tr_label(g: int) -> str:
    return f"{str(g).replace('-', '−')}→{str(g + 1).replace('-', '−')}"


# ════════════════════════════════════════════════════════════════════════
# Data quality
# ════════════════════════════════════════════════════════════════════════
def result_mix(m: pd.DataFrame) -> dict:
    hg, ag = m["home_goals"], m["away_goals"]
    return {"matches": int(len(m)),
            "goals_per_match": r((hg + ag).mean(), 2),
            "home_win_pct": r((hg > ag).mean() * 100, 1),
            "draw_pct": r((hg == ag).mean() * 100, 1),
            "away_win_pct": r((hg < ag).mean() * 100, 1)}


def data_quality(M: pd.DataFrame) -> dict:
    ok = M["status"] == "ok"
    rows = []
    for lg in X.LEAGUE_LABELS:
        m = M[M["league"] == lg]
        if m.empty:
            continue
        k = m["status"] == "ok"
        rows.append({"code": lg, "label": X.LEAGUE_LABELS[lg], "matches": int(len(m)), "loaded": int(k.sum()),
                     "failed": int((~k).sum()), "failed_pct": r((~k).mean() * 100, 1),
                     "og_affected": int(m["og_affected"].sum()),
                     "og_affected_pct": r(m.loc[k, "og_affected"].mean() * 100, 1)})
    okm = M[ok]
    missing = ((okm["home_goals"] - okm["shot_home_goals"]).clip(lower=0)
               + (okm["away_goals"] - okm["shot_away_goals"]).clip(lower=0))
    ere = next((x for x in rows if x["code"] == "Eredivisie"), None)
    return {
        "by_league": rows,
        "matches_total": int(len(M)),
        "matches_loaded": int(ok.sum()),
        "matches_failed": int((~ok).sum()),
        "failed_by_status": {k: int(v) for k, v in M.loc[~ok, "status"].value_counts().items()},
        "eredivisie_failed": ere["failed"] if ere else 0,
        "eredivisie_failed_pct": ere["failed_pct"] if ere else 0,
        "eredivisie_matches": ere["matches"] if ere else 0,
        "og_affected": int(okm["og_affected"].sum()),
        "og_affected_pct": r(okm["og_affected"].mean() * 100, 1),
        "og_missing_goals": int(missing.sum()),
        "shot_over": int(okm["shot_over"].sum()),
        "unknown_minute_matches": int((okm["unknown_minute_goals"] > 0).sum()),
        "unmapped_goals": int(okm["unmapped_goals"].sum()),
        "kept": result_mix(okm[~okm["og_affected"]]),
        "excluded": result_mix(okm[okm["og_affected"]]),
        "affected_file": f"data/{OG_CSV.name}",
    }


def write_og_csv(M: pd.DataFrame) -> None:
    a = M[M["og_affected"]].copy()
    a["official_score"] = a["home_goals"].astype(int).astype(str) + "–" + a["away_goals"].astype(int).astype(str)
    a["shot_table_score"] = (a["shot_home_goals"].astype(int).astype(str) + "–"
                             + a["shot_away_goals"].astype(int).astype(str))
    a["missing_home"] = (a["home_goals"] - a["shot_home_goals"]).astype(int)
    a["missing_away"] = (a["away_goals"] - a["shot_away_goals"]).astype(int)
    cols = ["league", "season", "date", "match_id", "home", "away", "official_score", "shot_table_score",
            "missing_home", "missing_away", "match_url"]
    a.sort_values(["league", "season", "date"])[cols].to_csv(OG_CSV, index=False, encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════
# Bootstrap of the value model
# ════════════════════════════════════════════════════════════════════════
def bootstrap_values(C: np.ndarray, strata: np.ndarray, leagues: list[str], league_of: np.ndarray) -> dict:
    """Resample matches within league; keep every cell's state and goal value, pooled and per league."""
    C2 = C.reshape(len(C), -1).astype(float)
    shape = C.shape[1:]
    lg_idx = {lg: np.flatnonzero(league_of == lg) for lg in leagues}
    out = {"V": [], "GT": [], "U": [], "GU": [], "W": [],
           "GT_lg": {lg: [] for lg in leagues}, "V_lg": {lg: [] for lg in leagues}}
    for w in VM.boot_weights(strata, N_BOOT, SEED):
        out["W"].append(w.astype(np.int16))
        v = VM.values((w @ C2).reshape(shape))
        out["V"].append(v["V"]); out["GT"].append(v["goal_t"])
        out["U"].append(v["U"]); out["GU"].append(v["goal_u"])
        for lg, idx in lg_idx.items():
            vl = VM.values((w[idx] @ C2[idx]).reshape(shape))
            out["GT_lg"][lg].append(vl["goal_t"]); out["V_lg"][lg].append(vl["V"])
    res = {k: np.array(out[k]) for k in ("V", "GT", "U", "GU", "W")}
    res["GT_lg"] = {lg: np.array(v) for lg, v in out["GT_lg"].items()}
    res["V_lg"] = {lg: np.array(v) for lg, v in out["V_lg"].items()}
    return res


def ci(samples: np.ndarray) -> tuple:
    lo, hi = VM.pct_ci(samples)
    return lo, hi


# ════════════════════════════════════════════════════════════════════════
# Tables for the page
# ════════════════════════════════════════════════════════════════════════
def state_value_block(C: np.ndarray, vals: dict, boots: dict) -> dict:
    n_matches = (C.sum(-1) > 0).sum(0)
    lo, hi = ci(boots["V"])
    ulo, uhi = ci(boots["U"])
    matrix = []
    for gi, g in enumerate(VM.GDS):
        row = []
        for b in range(VM.N_BIN):
            if vals["N"][gi, b] == 0:
                row.append(None)
                continue
            p = vals["P"][gi, b]
            row.append({"ep": r(vals["V"][gi, b]), "lo": r(lo[gi, b]), "hi": r(hi[gi, b]),
                        "minutes": int(vals["N"][gi, b]), "matches": int(n_matches[gi, b]),
                        "pW": r(p[VM.W]), "pD": r(p[VM.D]), "pL": r(p[VM.L]),
                        "sparse": bool(n_matches[gi, b] < SPARSE_MATCHES)})
        matrix.append(row)
    untimed = [{"gd": int(g), "label": gd_label(int(g)), "ep": r(vals["U"][gi]), "lo": r(ulo[gi]), "hi": r(uhi[gi]),
                "minutes": int(vals["N"][gi].sum())}
               for gi, g in enumerate(VM.GDS) if vals["N"][gi].sum() > 0]
    return {"gd_range": [int(g) for g in VM.GDS], "gd_labels": [gd_label(int(g)) for g in VM.GDS],
            "time_bins": list(TIME_BINS), "matrix": matrix, "untimed": untimed}


def goal_value_block(C: np.ndarray, vals: dict, boots: dict, goals: pd.DataFrame) -> dict:
    n_matches = (C.sum(-1) > 0).sum(0)
    lo, hi = ci(boots["GT"])
    ulo, uhi = ci(boots["GU"])
    counts = goals[goals["minute_bin"].isin(TIME_BINS)].groupby(["gd_before", "minute_bin"]).size()
    ucounts = goals.groupby("gd_before").size()
    rows, matrix, untimed = [], [], []
    for g in range(MIN_GD, MAX_GD):
        gi = GI(g)
        n_goals = [int(counts.get((g, b), 0)) for b in TIME_BINS]
        if not any(n_goals) and np.all(np.isnan(vals["goal_t"][gi])):
            continue
        rows.append({"gd_before": g, "gd_after": g + 1, "label": tr_label(g)})
        line = []
        for b in range(VM.N_BIN):
            v = vals["goal_t"][gi, b]
            if np.isnan(v):
                line.append(None if not n_goals[b] else {"ep": None, "goals": n_goals[b], "sparse": True})
                continue
            m = int(min(n_matches[gi, b], n_matches[gi + 1, b]))
            line.append({"ep": r(v), "lo": r(lo[gi, b]), "hi": r(hi[gi, b]), "goals": n_goals[b],
                         "matches": m, "sparse": bool(m < SPARSE_MATCHES)})
        matrix.append(line)
        if not np.isnan(vals["goal_u"][gi]):
            untimed.append({"gd_before": g, "gd_after": g + 1, "label": tr_label(g), "ep": r(vals["goal_u"][gi]),
                            "lo": r(ulo[gi]), "hi": r(uhi[gi]), "goals": int(ucounts.get(g, 0))})
    return {"time_bins": list(TIME_BINS), "transitions": rows, "matrix": matrix, "untimed": untimed}


def ratio_ci(num: np.ndarray, den: np.ndarray) -> dict:
    s = num / den
    lo, hi = np.nanpercentile(s, [2.5, 97.5])
    return {"lo": r(lo, 2), "hi": r(hi, 2)}


def headline_block(vals: dict, boots: dict, goals_model: pd.DataFrame, gt_lookup: np.ndarray) -> dict:
    GT, gt = boots["GT"], vals["goal_t"]
    counts = goals_model.groupby(["gd_before", "minute_bin"]).size()

    def cell(g, b):
        gi = GI(g)
        lo, hi = np.nanpercentile(GT[:, gi, b], [2.5, 97.5])
        return {"transition": tr_label(g), "bin": TIME_BINS[b], "ep": r(gt[gi, b]), "lo": r(lo), "hi": r(hi),
                "goals": int(counts.get((g, TIME_BINS[b]), 0))}

    opener = [cell(0, b) for b in range(VM.N_BIN)]
    ratio = gt[GI(0), LATE] / gt[GI(0), EARLY]
    eq_late = cell(-1, LATE)
    eq_ratio = gt[GI(-1), LATE] / gt[GI(0), EARLY]
    cushion_late = cell(1, LATE)

    # best goal among cells seen in enough matches
    best, best_v = None, -np.inf
    n_goal_cells = 0
    for g in range(MIN_GD, MAX_GD):
        for b in range(VM.N_BIN):
            v = gt[GI(g), b]
            if not np.isnan(v):
                n_goal_cells += 1
                if v > best_v and counts.get((g, TIME_BINS[b]), 0) >= 100:
                    best, best_v = (g, b), v

    # total EP delivered per bin: every goal in the model sample at its own value
    gm = goals_model[goals_model["minute_bin"].isin(TIME_BINS)]
    gv = gt_lookup[VM.gd_index(gm["gd_before"]), gm["minute_bin"].map(VM.BIN_INDEX).to_numpy()]
    by_bin = pd.DataFrame({"bin": gm["minute_bin"].to_numpy(), "ep": gv, "tr": gm["gd_before"].to_numpy()})
    ep_by_bin = []
    for b in TIME_BINS:
        x = by_bin[by_bin["bin"] == b]
        top = x.groupby("tr")["ep"].agg(["sum", "size"]).sort_values("sum", ascending=False).head(3)
        ep_by_bin.append({"bin": b, "total_ep": r(x["ep"].sum(), 1), "goals": int(len(x)),
                          "ep_per_goal": r(x["ep"].mean(), 3),
                          "top": [{"transition": tr_label(int(t)), "ep": r(s, 1), "goals": int(n)}
                                  for t, (s, n) in top.iterrows()]})
    tot_ratio = ep_by_bin[LATE]["total_ep"] / ep_by_bin[EARLY]["total_ep"]
    # interval: re-price and re-weight the goals in each resample
    gidx = VM.gd_index(gm["gd_before"])
    bidx = gm["minute_bin"].map(VM.BIN_INDEX).to_numpy()
    late_m, early_m = bidx == LATE, bidx == EARLY
    mi = gm["match_id"].map(boots["match_index"]).to_numpy()
    rt = []
    for k in range(len(boots["GT"])):
        gtk = np.nan_to_num(np.where(np.isnan(boots["GT"][k]), boots["GU"][k][:, None], boots["GT"][k]))
        e = gtk[gidx, bidx] * boots["W"][k][mi]
        rt.append(e[late_m].sum() / e[early_m].sum())
    tot_lo, tot_hi = np.percentile(rt, [2.5, 97.5])

    V = vals["V"]
    lead = {"lead_late": r(V[GI(1), LATE]), "level_late": r(V[GI(0), LATE]), "behind_late": r(V[GI(-1), LATE]),
            "lead_early": r(V[GI(1), EARLY]), "level_early": r(V[GI(0), EARLY]), "behind_early": r(V[GI(-1), EARLY])}
    return {
        "opener_by_bin": opener,
        "opener_ratio": {"value": r(ratio, 2), **ratio_ci(GT[:, GI(0), LATE], GT[:, GI(0), EARLY]),
                         "late": opener[LATE], "early": opener[EARLY]},
        "late_equaliser": {**eq_late, "ratio_vs_early_opener": r(eq_ratio, 2),
                           **{f"ratio_{k}": v for k, v in ratio_ci(GT[:, GI(-1), LATE], GT[:, GI(0), EARLY]).items()}},
        "late_cushion": cushion_late,
        "late_opener_vs_equaliser": {"value": r(gt[GI(0), LATE] / gt[GI(-1), LATE], 2),
                                     **ratio_ci(GT[:, GI(0), LATE], GT[:, GI(-1), LATE])},
        "best_cell": cell(*best) if best else None,
        "goal_cells_with_value": n_goal_cells,
        "ep_by_bin": ep_by_bin,
        "ep_last_vs_first_bin": {"value": r(tot_ratio, 2), "lo": r(tot_lo, 2), "hi": r(tot_hi, 2)},
        "states": lead,
    }


# ════════════════════════════════════════════════════════════════════════
# Held-out calibration
# ════════════════════════════════════════════════════════════════════════
def calibration_block(C: np.ndarray, seasons: np.ndarray, strata: np.ndarray) -> dict:
    all_seasons = sorted(pd.unique(seasons))
    test_s = all_seasons[-N_TEST_SEASONS:]
    train = ~np.isin(seasons, test_s)
    test = ~train
    Ctr, Cte = C[train].sum(0), C[test]
    Pt = VM.predictions(Ctr, timed=True)
    Pu = VM.predictions(Ctr, timed=False)
    base = Ctr.sum((0, 1)) / Ctr.sum()
    Pb = np.broadcast_to(base, Pt.shape).copy()
    bt, bu, bb = (VM.brier_per_match(Cte, P) for P in (Pt, Pu, Pb))
    n_min = Cte.sum((1, 2, 3)).astype(float)
    tot = n_min.sum()
    rng = np.random.default_rng(SEED)
    st = strata[test]
    groups = [np.flatnonzero(st == s) for s in pd.unique(st)]
    diffs, skills = [], []
    for _ in range(N_BOOT):
        idx = np.concatenate([rng.choice(g, g.size) for g in groups])
        n = n_min[idx].sum()
        diffs.append((bu[idx].sum() - bt[idx].sum()) / n)
        skills.append(1 - bt[idx].sum() / bb[idx].sum())
    d_lo, d_hi = np.percentile(diffs, [2.5, 97.5])
    s_lo, s_hi = np.percentile(skills, [2.5, 97.5])

    by_bin = []
    for b in range(VM.N_BIN):
        Cb = np.zeros_like(Cte)
        Cb[:, :, b] = Cte[:, :, b]
        nb = Cb.sum()
        by_bin.append({"bin": TIME_BINS[b],
                       "timed": r(VM.brier_per_match(Cb, Pt).sum() / nb, 4),
                       "untimed": r(VM.brier_per_match(Cb, Pu).sum() / nb, 4),
                       "base": r(VM.brier_per_match(Cb, Pb).sum() / nb, 4)})

    # reliability of expected points: predicted EP (training values) vs points actually won
    ep_pred = 3 * Pt[..., VM.W] + Pt[..., VM.D]
    Ct = Cte.sum(0)
    N = Ct.sum(-1)
    pts = 3 * Ct[..., VM.W] + Ct[..., VM.D]
    edges = np.arange(0, 3.01, BAND_WIDTH)
    rel = []
    for a, z in zip(edges[:-1], edges[1:]):
        m = (ep_pred >= a) & (ep_pred < z if z < 3 else ep_pred <= z) & (N > 0)
        if N[m].sum() < BAND_MIN_MINUTES:
            continue
        rel.append({"from": r(a, 2), "to": r(z, 2), "predicted": r((ep_pred[m] * N[m]).sum() / N[m].sum()),
                    "observed": r(pts[m].sum() / N[m].sum()), "minutes": int(N[m].sum())})
    worst = max(abs(x["predicted"] - x["observed"]) for x in rel)
    return {
        "train_seasons": [s for s in all_seasons if s not in test_s], "test_seasons": list(test_s),
        "test_matches": int(test.sum()), "test_minutes": int(tot),
        "brier": {"timed": r(bt.sum() / tot, 4), "untimed": r(bu.sum() / tot, 4), "base": r(bb.sum() / tot, 4)},
        "improvement": {"value": r((bu.sum() - bt.sum()) / tot, 4), "lo": r(d_lo, 4), "hi": r(d_hi, 4)},
        "skill_vs_base": {"value": r((1 - bt.sum() / bb.sum()) * 100, 1), "lo": r(s_lo * 100, 1),
                          "hi": r(s_hi * 100, 1)},
        "by_bin": by_bin,
        "reliability": rel,
        "reliability_max_gap": r(worst, 2),
        "band_width": BAND_WIDTH, "band_min_minutes": BAND_MIN_MINUTES,
    }


# ════════════════════════════════════════════════════════════════════════
# Players
# ════════════════════════════════════════════════════════════════════════
def identities(goals: pd.DataFrame, apps: pd.DataFrame) -> tuple[dict, dict]:
    """(name, born) -> canonical key; namesakes = one name, birth dates more than 3 days apart."""
    pairs = pd.concat([
        apps[["player", "born"]],
        goals[["goalscorer", "goalscorer_born"]].set_axis(["player", "born"], axis=1),
        goals[["sca1_creator", "sca1_born"]].set_axis(["player", "born"], axis=1),
    ]).dropna(subset=["player"]).drop_duplicates()
    canon, people = {}, {}
    for name, grp in pairs.groupby("player"):
        dates = sorted(pd.to_datetime(grp["born"].dropna()).unique())
        clusters = []
        for d in dates:
            if clusters and (d - clusters[-1][-1]).days <= 3:
                clusters[-1].append(d)
            else:
                clusters.append([d])
        for cl in clusters:
            key = (name, cl[0].date().isoformat())
            for d in cl:
                canon[(name, pd.Timestamp(d).date().isoformat())] = key
            people[key] = len(clusters)
        canon[(name, None)] = (name, clusters[0][0].date().isoformat()) if len(clusters) == 1 else (name, None)
        if len(clusters) != 1:
            people[(name, None)] = len(clusters)
    return canon, people


def display(key: tuple, people: dict) -> str:
    name, born = key
    return f"{name} (b. {born[:4]})" if people.get(key, 1) > 1 and born else name


def involvements(goals: pd.DataFrame, canon: dict, people: dict) -> pd.DataFrame:
    """One row per (goal, player) over {scorer, SCA1}: a player who is both gets one credit."""
    base = ["match_id", "league", "season", "gd_before", "gd_after", "minute_bin", "scoring_team", "goal_uid"]
    sc = goals[base + ["goalscorer", "goalscorer_born"]].set_axis(base + ["player", "born"], axis=1).assign(role="goal")
    a1 = goals[base + ["sca1_creator", "sca1_born"]].set_axis(base + ["player", "born"], axis=1).assign(role="sca1")
    inv = pd.concat([sc, a1], ignore_index=True).dropna(subset=["player"])
    inv = inv[inv["player"].astype(str).str.lower() != "unknown"]
    inv["key"] = [canon.get((p, b), canon.get((p, None), (p, b))) for p, b in zip(inv["player"], inv["born"])]
    inv = inv.sort_values("role").drop_duplicates(["goal_uid", "key"], keep="first")   # 'goal' sorts before 'sca1'
    inv["contributor"] = [display(k, people) for k in inv["key"]]
    return inv.reset_index(drop=True)


def player_boards(inv: pd.DataFrame, goals: pd.DataFrame, apps: pd.DataFrame, canon: dict, people: dict,
                  gt_lookup: np.ndarray, gu: np.ndarray, boots: dict, match_index: dict,
                  model_ids: set) -> dict:
    """Leaderboards with bootstrap intervals.

    timing premium  a credit's time-aware value minus the average time-aware value
                    of all goals with the same scoreline change: what a player
                    gained from *when* his goals came, scorelines held fixed. (Raw
                    time-aware minus time-blind EP drifts below zero with volume,
                    because most goals from level come early, when they are worth
                    less than the time-blind average.)
    """
    def prices(df):
        b = df["minute_bin"].map(VM.BIN_INDEX)
        return VM.gd_index(df["gd_before"]), b.fillna(0).astype(int).to_numpy(), b.notna().to_numpy()

    gi, bi, tok = prices(inv)
    ggi, gbi, gtok = prices(goals)
    e_goal = np.where(gtok, gt_lookup[ggi, gbi], gu[ggi])
    mean_t = np.bincount(ggi, e_goal, VM.N_GD) / np.maximum(np.bincount(ggi, minlength=VM.N_GD), 1)
    inv = inv.assign(ep=np.where(tok, gt_lookup[gi, bi], gu[gi]), ep_u=gu[gi])
    inv["premium"] = inv["ep"] - mean_t[gi]

    keys = pd.Index(inv["key"].unique())
    pidx = keys.get_indexer(inv["key"])
    midx = inv["match_id"].map(match_index).to_numpy()
    gmidx = goals["match_id"].map(match_index).to_numpy()
    n_p = len(keys)

    agg = inv.groupby("key").agg(involvements=("goal_uid", "size"), goals=("role", lambda s: int((s == "goal").sum())),
                                 ep=("ep", "sum"), ep_u=("ep_u", "sum"), premium=("premium", "sum")).reindex(keys)
    team = (inv.groupby(["key", "scoring_team"]).size().reset_index(name="n")
            .sort_values("n", ascending=False).drop_duplicates("key").set_index("key")["scoring_team"])
    agg["team"] = team.reindex(keys).to_numpy()
    agg["player"] = [display(k, people) for k in keys]
    ep_bins = inv.pivot_table(index="key", columns="minute_bin", values="ep", aggfunc="sum", fill_value=0.0)

    # minutes from the same matches, keyed like the goals
    ap = apps.copy()
    ap["key"] = [canon.get((p, b), canon.get((p, None), (p, b))) for p, b in zip(ap["player"], ap["born"])]
    ap = ap[ap["key"].isin(keys) & ap["match_id"].isin(match_index)]
    agg["minutes"] = ap.groupby("key")["minutes"].sum().reindex(keys).fillna(0).to_numpy()

    # bootstrap: the value model's match weights; each resample re-prices every goal
    W, GTb, GUb = boots["W"], boots["GT"], boots["GU"]
    ep_b, pr_b, min_b = (np.empty((N_BOOT, n_p)) for _ in range(3))
    a_p = keys.get_indexer(ap["key"])
    a_m = ap["match_id"].map(match_index).to_numpy()
    a_min = ap["minutes"].to_numpy(dtype=float)
    for k in range(N_BOOT):
        guk = np.nan_to_num(GUb[k])
        gtk = np.nan_to_num(np.where(np.isnan(GTb[k]), GUb[k][:, None], GTb[k]))
        eg = np.where(gtok, gtk[ggi, gbi], guk[ggi])
        wg = W[k][gmidx]
        mk = np.bincount(ggi, wg * eg, VM.N_GD) / np.maximum(np.bincount(ggi, wg, VM.N_GD), 1e-9)
        e = np.where(tok, gtk[gi, bi], guk[gi])
        w = W[k][midx]
        ep_b[k] = np.bincount(pidx, w * e, n_p)
        pr_b[k] = np.bincount(pidx, w * (e - mk[gi]), n_p)
        min_b[k] = np.bincount(a_p, W[k][a_m] * a_min, n_p)
    agg["ep_lo"], agg["ep_hi"] = np.percentile(ep_b, [2.5, 97.5], axis=0)
    agg["pr_lo"], agg["pr_hi"] = np.percentile(pr_b, [2.5, 97.5], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        p90_b = np.where(min_b > 0, ep_b / min_b * 90, np.nan)
        agg["p90"] = np.where(agg["minutes"] > 0, agg["ep"] / agg["minutes"] * 90, np.nan)
        lo, hi = np.nanpercentile(p90_b, [2.5, 97.5], axis=0)
    agg["p90_lo"], agg["p90_hi"] = lo, hi

    def row(k):
        a = agg.loc[[k]].iloc[0]
        return {"player": a["player"], "team": a["team"], "involvements": int(a["involvements"]),
                "goals": int(a["goals"]), "assists": int(a["involvements"] - a["goals"]),
                "ep": r(a["ep"], 2), "ep_lo": r(a["ep_lo"], 2), "ep_hi": r(a["ep_hi"], 2),
                "ep_untimed": r(a["ep_u"], 2),
                "premium": r(a["premium"], 2), "premium_lo": r(a["pr_lo"], 2), "premium_hi": r(a["pr_hi"], 2),
                "minutes": int(a["minutes"]) if a["minutes"] else None,
                "p90": r(a["p90"], 3), "p90_lo": r(a["p90_lo"], 3), "p90_hi": r(a["p90_hi"], 3)}

    top_ep_idx = agg.sort_values("ep", ascending=False).head(10).index
    top_ep = []
    for k in top_ep_idx:
        x = row(k)
        x["ep_bins"] = {b: r(ep_bins.loc[[k]].iloc[0].get(b, 0.0), 2) for b in TIME_BINS}
        top_ep.append(x)
    elig = agg[agg["involvements"] >= MIN_INVOLVEMENTS]
    top_pr = elig.sort_values("premium", ascending=False).head(10)
    premium = [row(k) for k in top_pr.index]
    bottom = [row(k) for k in elig.sort_values("premium").head(10).index]
    # where the clearly negative premiums come from: share of involvements in the opening half hour
    neg = elig[elig["pr_hi"] < 0].index
    first30 = inv["minute_bin"].isin(TIME_BINS[:2])
    share_neg = first30[inv["key"].isin(neg)].mean()
    share_all = first30.mean()
    p90 = agg[agg["minutes"] >= MIN_MINUTES_P90].sort_values("p90", ascending=False).head(10)
    per90 = [row(k) for k in p90.index]

    # sensitivity: boards from goals in the model sample only (own-goal matches out)
    sub = inv[inv["match_id"].isin(model_ids)]
    s_ep = sub.groupby("key")["ep"].sum().sort_values(ascending=False).head(10)
    s_cnt = sub.groupby("key").size()
    s_pr = (sub.groupby("key")["premium"].sum()[s_cnt >= MIN_INVOLVEMENTS]
            .sort_values(ascending=False).head(10))

    ambiguous = sorted({k[0] for k, n in people.items() if n > 1})
    on_boards = sorted({x["player"] for x in top_ep + premium + per90 if "(b." in x["player"]})
    self_sca1 = goals["goalscorer"].eq(goals["sca1_creator"])
    return {
        "inv": inv, "agg": agg,
        "top_ep": top_ep, "top_premium": premium, "bottom_premium": bottom, "top_per90": per90,
        "negative_premium_first30_pct": r(share_neg * 100, 1), "all_first30_pct": r(share_all * 100, 1),
        "premium_summary": {
            "eligible": int(len(elig)), "min_involvements": MIN_INVOLVEMENTS,
            "ci_above_zero": int((elig["pr_lo"] > 0).sum()), "ci_below_zero": int((elig["pr_hi"] < 0).sum()),
            "expected_by_chance_each_side": int(round(len(elig) * 0.025)),
            "leader": premium[0]["player"], "leader_premium": premium[0]["premium"],
            "top10_ci_include_zero": int(((top_pr["pr_lo"] <= 0) & (top_pr["pr_hi"] >= 0)).sum()),
        },
        "top_ep_summary": {
            "top5_spread": r(top_ep[0]["ep"] - top_ep[4]["ep"], 2),
            "top5_overlap_leader": int(sum(x["ep_hi"] >= top_ep[0]["ep_lo"] for x in top_ep[:5])),
        },
        "per90_summary": {"min_minutes": MIN_MINUTES_P90, "eligible": int((agg["minutes"] >= MIN_MINUTES_P90).sum()),
                          "short_minutes": SHORT_MINUTES,
                          "short_in_top10": int(sum((x["minutes"] or 0) < SHORT_MINUTES for x in per90))},
        "sensitivity_model_matches_only": {
            "top10_ep_overlap": int(len(set(s_ep.index) & set(top_ep_idx))),
            "top10_premium_overlap": int(len(set(s_pr.index) & set(top_pr.index))),
        },
        "attribution": {"involvements": int(len(inv)), "goals": int(len(goals)),
                        "goals_with_sca1": int(goals["sca1_creator"].notna().sum()),
                        "self_sca1": int(self_sca1.sum()), "self_sca1_pct": r(self_sca1.mean() * 100, 1),
                        "unassisted": int(goals["sca1_creator"].isna().sum())},
        "namesakes": {"names": len(ambiguous), "on_boards": on_boards},
        "players": int(n_p),
    }


# ════════════════════════════════════════════════════════════════════════
# Dashboard
# ════════════════════════════════════════════════════════════════════════
DATASET_HELP = {
    "Goals+Assists": "One row per player and team. A goal credits its scorer and its SCA1 (FBref's first "
                     "shot-creating action), once per player, so a self-created goal counts once. EP is summed "
                     "at the time-aware value of each goal.",
    "Goalscorer": "Goals only, credited to the scorer.",
    "Assist": "SCA1 credits only. '(unassisted)' collects goals with no recorded shot-creating action.",
    "State values": "Expected final points of a team at that goal difference during a minute in that bin, from "
                    "every team-minute of the model sample. ci_lo / ci_hi: 95% bootstrap interval over matches. "
                    "Cells seen in fewer than 30 matches are flagged sparse.",
    "Goal values": "What a goal from gd_before to gd_after is worth in that bin: the gap between the two state "
                   "values. minute_bin 'all' is the time-blind value.",
}
DASH_HELP = {
    **COLUMN_HELP,
    "exp_points_collected_timed": "EP collected: each goal or SCA1 credit at its time-aware value "
                                  "V(gd + 1, bin) − V(gd, bin).",
    "exp_points_collected_untimed": "The same goals at their time-blind value U(gd + 1) − U(gd).",
    "delta_ep_timed_vs_untimed": "Time-aware minus time-blind EP. It drifts below zero with volume (most goals from "
                                 "level come early, when they are worth less than the time-blind average), so it is "
                                 "not a clutch measure; the editorial page's timing premium corrects for that.",
    "minutes_played": "Minutes played in the same matches and scope as the goals (all six leagues).",
    "ep_per_90": "Time-aware EP per 90 minutes played in this scope.",
    "gd": "Goal difference of the team, from its own side.",
    "team_minutes": "Team-minutes observed in this state (each match contributes both sides).",
    "matches": "Matches in which the state occurred.",
    "exp_points": "Expected final points: 3·pW + 1·pD.",
    "exp_points_collected": "Value of the goal: state value after minus state value before.",
    "goals": "Goals scored in this transition and bin (model sample).",
    "ci_lo": "Lower end of the 95% bootstrap interval.",
    "ci_hi": "Upper end of the 95% bootstrap interval.",
    "sparse": "Seen in fewer than 30 matches: read with care.",
    "pW": "Share of team-minutes in this state whose team went on to win.",
    "pD": "… to draw.",
    "pL": "… to lose.",
}


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = []
    for row in df.to_dict(orient="records"):
        out.append({k: (None if isinstance(v, float) and np.isnan(v) else
                        (int(v) if isinstance(v, (np.integer,)) else
                         (float(v) if isinstance(v, np.floating) else v))) for k, v in row.items()})
    return out


def contributor_views(events: pd.DataFrame, minutes: pd.DataFrame, vmap_u: dict, vmap_t: dict) -> dict:
    """{view: container} in the shapes dashboard.html understands; minutes joined per scope."""
    def attach(df: pd.DataFrame, mins: pd.Series) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["minutes_played"] = df["contributor"].map(mins).fillna(0).astype(int)
        df["ep_per_90"] = np.where(df["minutes_played"] > 0,
                                   df["exp_points_collected_timed"] / df["minutes_played"].clip(lower=1) * 90, 0.0)
        return df

    tables = {}
    for (lg, se), ev in events.groupby(["league", "season"]):
        t = _contributor_table(ev, "contributor", vmap_u, vmap_t)
        m = minutes[(minutes["league"] == lg) & (minutes["season"] == se)].groupby("contributor")["minutes"].sum()
        tables.setdefault(lg, {})[se] = attach(t, m)
    by_lg, by_se, all_ = aggregate_tables(tables)
    by_lg = {lg: attach(df, minutes[minutes["league"] == lg].groupby("contributor")["minutes"].sum())
             for lg, df in by_lg.items()}
    by_se = {se: attach(df, minutes[minutes["season"] == se].groupby("contributor")["minutes"].sum())
             for se, df in by_se.items()}
    all_ = attach(all_, minutes.groupby("contributor")["minutes"].sum())
    return {
        "Per League & Season": {X.LEAGUE_LABELS[lg]: {se: _records(df) for se, df in s.items()} for lg, s in tables.items()},
        "Totals by League": {X.LEAGUE_LABELS[lg]: _records(df) for lg, df in by_lg.items()},
        "Totals by Season": {se: _records(df) for se, df in by_se.items()},
        "All": {"All": _records(all_)},
    }


def value_rows(Csum: np.ndarray, Vb: np.ndarray, GTb: np.ndarray, goals: pd.DataFrame, n_matches: np.ndarray):
    v = VM.values(Csum)
    vlo, vhi = VM.pct_ci(Vb)
    glo, ghi = VM.pct_ci(GTb)
    counts = goals.groupby(["gd_before", "minute_bin"]).size()
    srows, grows = [], []
    for gi, g in enumerate(VM.GDS):
        for b, bn in enumerate(TIME_BINS):
            if v["N"][gi, b] > 0:
                p = v["P"][gi, b]
                srows.append({"gd": int(g), "minute_bin": bn, "team_minutes": int(v["N"][gi, b]),
                              "matches": int(n_matches[gi, b]), "pW": r(p[0]), "pD": r(p[1]), "pL": r(p[2]),
                              "exp_points": r(v["V"][gi, b]), "ci_lo": r(vlo[gi, b]), "ci_hi": r(vhi[gi, b]),
                              "sparse": bool(n_matches[gi, b] < SPARSE_MATCHES)})
            if gi < VM.N_GD - 1 and not np.isnan(v["goal_t"][gi, b]):
                m = int(min(n_matches[gi, b], n_matches[gi + 1, b]))
                grows.append({"gd_before": int(g), "gd_after": int(g) + 1, "minute_bin": bn,
                              "goals": int(counts.get((int(g), bn), 0)), "exp_points_collected": r(v["goal_t"][gi, b]),
                              "ci_lo": r(glo[gi, b]), "ci_hi": r(ghi[gi, b]), "matches": m,
                              "sparse": bool(m < SPARSE_MATCHES)})
        if gi < VM.N_GD - 1 and not np.isnan(v["goal_u"][gi]):
            grows.append({"gd_before": int(g), "gd_after": int(g) + 1, "minute_bin": "all",
                          "goals": int(goals[goals["gd_before"] == g].shape[0]),
                          "exp_points_collected": r(v["goal_u"][gi]), "ci_lo": None, "ci_hi": None,
                          "matches": None, "sparse": False})
    return srows, grows


def dashboard_payload(G: pd.DataFrame, inv: pd.DataFrame, A: pd.DataFrame, canon: dict, people: dict,
                      usable: pd.DataFrame, C: np.ndarray, boots: dict, gt_lookup: np.ndarray, gu: np.ndarray,
                      model_mask: np.ndarray, created_at: str) -> dict:
    vmap_t = {(int(g), int(g) + 1, b): float(gt_lookup[gi, bi])
              for gi, g in enumerate(VM.GDS) for bi, b in enumerate(TIME_BINS) if not np.isnan(gt_lookup[gi, bi])}
    vmap_u = {(int(g), int(g) + 1): float(gu[gi]) for gi, g in enumerate(VM.GDS) if not np.isnan(gu[gi])}

    def disp(names, borns):
        return [display(canon.get((p, b), canon.get((p, None), (p, b))), people) if isinstance(p, str) else None
                for p, b in zip(names, borns)]

    base = ["league", "season", "gd_before", "gd_after", "minute_bin", "scoring_team"]
    scorer = G[base].assign(contributor=disp(G["goalscorer"], G["goalscorer_born"]))
    sca1 = G[base].assign(contributor=disp(G["sca1_creator"], G["sca1_born"]))
    sca1["contributor"] = sca1["contributor"].fillna("(unassisted)")
    ga = inv[base + ["contributor"]]

    ap = A[A["match_id"].isin(usable["match_id"])].copy()
    ap["contributor"] = disp(ap["player"], ap["born"])

    datasets = {
        "Goals+Assists": contributor_views(ga, ap, vmap_u, vmap_t),
        "Goalscorer": contributor_views(scorer.dropna(subset=["contributor"]), ap, vmap_u, vmap_t),
        "Assist": contributor_views(sca1, ap, vmap_u, vmap_t),
    }
    gm = G[G["match_id"].isin(usable.loc[model_mask, "match_id"])]
    n_m = (C.sum(-1) > 0).sum(0)
    s_pool, g_pool = value_rows(C.sum(0), boots["V"], boots["GT"], gm, n_m)
    s_lg, g_lg = {}, {}
    for lg in boots["V_lg"]:
        idx = (usable["league"] == lg).to_numpy()
        s_lg[X.LEAGUE_LABELS[lg]], g_lg[X.LEAGUE_LABELS[lg]] = value_rows(
            C[idx].sum(0), boots["V_lg"][lg], boots["GT_lg"][lg], gm[gm["league"] == lg], (C[idx].sum(-1) > 0).sum(0))
    datasets["State values"] = {"Pooled": {"Pooled": s_pool}, "By League": s_lg}
    datasets["Goal values"] = {"Pooled": {"Pooled": g_pool}, "By League": g_lg}
    return {"meta": {"created_at": created_at}, "columnHelp": DASH_HELP, "datasetHelp": DATASET_HELP,
            "datasets": datasets}


# ════════════════════════════════════════════════════════════════════════
# Game management: what the next goal is worth for and against
# ════════════════════════════════════════════════════════════════════════
def game_state_block(vals: dict, boots: dict) -> dict:
    """For a team leading by one, level, or trailing by one: the value of scoring the next goal
    (upside) and the cost of conceding it (downside), by bin. Conceding from gd to gd − 1 costs
    V(gd) − V(gd − 1), the value of the goal gd − 1 → gd."""
    gt, GT = vals["goal_t"], boots["GT"]
    rows = []
    for g, label in ((1, "Leading by one"), (0, "Level"), (-1, "Trailing by one")):
        line = []
        for b in range(VM.N_BIN):
            up, down = gt[GI(g), b], gt[GI(g - 1), b]
            ratio = GT[:, GI(g), b] / GT[:, GI(g - 1), b]
            lo, hi = np.nanpercentile(ratio, [2.5, 97.5])
            line.append({"bin": TIME_BINS[b], "up": r(up), "down": r(down), "ratio": r(up / down, 2),
                         "lo": r(lo, 2), "hi": r(hi, 2)})
        rows.append({"gd": g, "label": label, "bins": line})
    level = rows[1]["bins"]
    return {"rows": rows, "level_early_ratio": level[EARLY]["ratio"], "level_late_ratio": level[LATE]["ratio"],
            "level_late": level[LATE], "lead_late": rows[0]["bins"][LATE], "trail_late": rows[2]["bins"][LATE]}


# ════════════════════════════════════════════════════════════════════════
# Robustness
# ════════════════════════════════════════════════════════════════════════
def robustness_block(C: np.ndarray, C_all: np.ndarray, usable: pd.DataFrame, model_mask: np.ndarray,
                     vals: dict, boots: dict, leagues: list[str]) -> dict:
    def key_numbers(v):
        gt = v["goal_t"]
        return {"opener_late": r(gt[GI(0), LATE]), "opener_early": r(gt[GI(0), EARLY]),
                "ratio": r(gt[GI(0), LATE] / gt[GI(0), EARLY], 2),
                "equaliser_late": r(gt[GI(-1), LATE]),
                "level_late_ratio": r(gt[GI(0), LATE] / gt[GI(-1), LATE], 2)}

    base = key_numbers(vals)
    inclusive = key_numbers(VM.values(C_all.sum(0)))
    by_league = []
    for lg in leagues:
        idx = (usable["league"] == lg).to_numpy() & model_mask
        v = VM.values(C[idx].sum(0))
        GT = boots["GT_lg"][lg]
        lo, hi = np.nanpercentile(GT[:, GI(0), LATE] / GT[:, GI(0), EARLY], [2.5, 97.5])
        by_league.append({"code": lg, "label": X.LEAGUE_LABELS[lg], "matches": int(idx.sum()),
                          **key_numbers(v), "lo": r(lo, 2), "hi": r(hi, 2)})
    seasons = usable["season"].to_numpy()
    all_s = sorted(pd.unique(seasons))
    test_s = all_s[-N_TEST_SEASONS:]
    tr = ~np.isin(seasons, test_s) & model_mask
    te = np.isin(seasons, test_s) & model_mask
    return {
        "primary": base,
        "inclusive": {**inclusive, "matches": int(len(usable))},
        "by_league": by_league,
        "leagues_ratio_above_1_5": int(sum(x["ratio"] > 1.5 for x in by_league)),
        "league_ratio_min": min(x["ratio"] for x in by_league),
        "league_ratio_max": max(x["ratio"] for x in by_league),
        "train": {**key_numbers(VM.values(C[tr].sum(0))), "seasons": [s for s in all_s if s not in test_s],
                  "matches": int(tr.sum())},
        "test": {**key_numbers(VM.values(C[te].sum(0))), "seasons": list(test_s), "matches": int(te.sum())},
    }


# ════════════════════════════════════════════════════════════════════════
# Takeaways
# ════════════════════════════════════════════════════════════════════════
def takeaways_from(p: dict) -> dict:
    """Four audiences, evidence labels per CLAUDE.md §4.3. Every number comes from the payload."""
    gs, h, pl, s = p["game_state"], p["headline"], p["players"], p["sample"]
    lv, ld = gs["level_late"], gs["lead_late"]
    ps, tot = pl["premium_summary"], h["ep_last_vs_first_bin"]
    n_lg = len(p["meta"]["leagues"])
    return {
        "intro": (f"Goal prices from {s['matches_model']:,} matches and {s['team_minutes']:,} team-minutes. "
                  f"What they say for each audience:"),
        "managers": [
            {"text": (f"Level after 75': a goal for is worth **{fx(lv['up'])} EP**, a goal against costs "
                      f"{fx(lv['down'])}. The upside is {fx(lv['ratio'])}× the downside."),
             "evidence": "moderate",
             "basis": (f"95% CI {fx(lv['lo'])}–{fx(lv['hi'])}× · all {n_lg} leagues · prices outcomes, "
                       f"not tactics")},
            {"text": (f"1–0 up after 75': conceding costs **{fx(ld['down'])} EP**, a second goal adds only "
                      f"{fx(ld['up'])}."),
             "evidence": "moderate",
             "basis": f"ratio 95% CI {fx(ld['lo'])}–{fx(ld['hi'])} · values, not the effect of sitting deeper"},
        ],
        "coaches": [
            {"text": (f"The last 15 minutes deliver **{fx(tot['value'])}×** the expected points of the first 15: "
                      f"more goals, higher stakes."),
             "evidence": "exploratory",
             "basis": (f"{s['goals_model']:,} goals · 95% CI {fx(tot['lo'])}–{fx(tot['hi'])}× · "
                       f"training implication untested")},
        ],
        "clubs": [
            {"text": (f"Don't pay for 'clutch': only **{ps['ci_above_zero']}** of {ps['eligible']:,} players scored at "
                      f"clearly better-than-average times, fewer than chance (~{ps['expected_by_chance_each_side']})."),
             "evidence": "moderate",
             "basis": (f"{ps['min_involvements']}+ goal involvements · bootstrap intervals · "
                       f"repeatability not tested")},
        ],
        "agents": [],
    }


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════
def main() -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    print("[1/7] Matches, goals, appearances ...")
    R = X.load_all()
    M, G, A = R["matches"], R["goals"], R["apps"]
    ok = M[M["status"] == "ok"].reset_index(drop=True)
    write_og_csv(ok)
    dq = data_quality(M)
    usable = ok[ok["unknown_minute_goals"] == 0].reset_index(drop=True)
    model_mask = ~usable["og_affected"].to_numpy()
    model_ids = set(usable.loc[model_mask, "match_id"])
    G = G[G["match_id"].isin(usable["match_id"])].copy()
    G["goal_uid"] = G["match_id"] + ":" + G["event_idx"].astype(str)
    match_index = {m: i for i, m in enumerate(usable["match_id"])}
    leagues = [lg for lg in X.LEAGUE_LABELS if lg in set(usable["league"])]
    print(f"  loaded {dq['matches_loaded']:,} of {dq['matches_total']:,}; own-goal affected {dq['og_affected']:,}; "
          f"model sample {int(model_mask.sum()):,} matches")

    print("[2/7] Team-minute panel ...")
    C_all = VM.panel_counts(usable, G)
    C = C_all * model_mask[:, None, None, None]
    vals = VM.values(C.sum(0))
    gt_lookup, gu, filled = VM.goal_value_lookup(vals)
    gt_lookup, gu = np.nan_to_num(gt_lookup), np.nan_to_num(gu)     # beyond ±7: worth nothing
    goals_model = G[G["match_id"].isin(model_ids)]

    print(f"[3/7] Bootstrap ({N_BOOT} resamples within league, seed {SEED}) ...")
    boots = bootstrap_values(C, usable["league"].to_numpy(), leagues, usable["league"].to_numpy())
    boots["match_index"] = match_index

    print("[4/7] Held-out calibration ...")
    model = usable[model_mask].reset_index(drop=True)
    calib = calibration_block(C[model_mask], model["season"].to_numpy(), model["league"].to_numpy())

    print("[5/7] Players ...")
    canon, people = identities(G, A)
    inv = involvements(G, canon, people)
    pb = player_boards(inv, G, A, canon, people, gt_lookup, gu, boots, match_index, model_ids)

    print("[6/7] Dashboard ...")
    dash = dashboard_payload(G, inv, A, canon, people, usable, C, boots, gt_lookup, gu, model_mask, created_at)
    oversize = DF.write(dash, DASHBOARD_DIR)
    for name, mb in oversize:
        print(f"  WARNING: {name} is {mb:.1f} MB (over 5 MB)")

    print("[7/7] data.json ...")
    n_cells = int((vals["N"] > 0).sum())
    payload = {
        "generated_at": created_at,
        "meta": {
            "leagues": [{"code": lg, "label": X.LEAGUE_LABELS[lg]} for lg in leagues],
            "seasons": sorted(pd.unique(usable["season"])),
            "time_bins": list(TIME_BINS),
            "gd_range": [int(g) for g in VM.GDS],
            "params": {"boot_resamples": N_BOOT, "seed": SEED, "sparse_matches": SPARSE_MATCHES,
                       "min_minutes_per90": MIN_MINUTES_P90, "min_involvements": MIN_INVOLVEMENTS,
                       "test_seasons": N_TEST_SEASONS, "minutes_per_match": 90, "bin_minutes": 15},
        },
        "data_quality": dq,
        "sample": {
            "matches_model": int(model_mask.sum()), "matches_usable": int(len(usable)),
            "goals_all": int(len(G)), "goals_model": int(len(goals_model)),
            "team_minutes": int(C.sum()), "cells_with_data": n_cells, "cells_total": VM.N_GD * VM.N_BIN,
            "goals_filled_untimed": int(filled[VM.gd_index(G["gd_before"]),
                                              G["minute_bin"].map(VM.BIN_INDEX).fillna(0).astype(int)].sum()),
        },
        "state_values": state_value_block(C, vals, boots),
        "goal_values": goal_value_block(C, vals, boots, goals_model),
        "headline": headline_block(vals, boots, goals_model, gt_lookup),
        "game_state": game_state_block(vals, boots),
        "calibration": calib,
        "robustness": robustness_block(C, C_all, usable, model_mask, vals, boots, leagues),
        "players": {k: v for k, v in pb.items() if k not in ("inv", "agg")},
    }
    payload["takeaways"] = takeaways_from(payload)
    DATA_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  wrote {DATA_JSON.relative_to(PROJECT_DIR)} ({DATA_JSON.stat().st_size / 1024:.0f} KB)")

    h, c, gs = payload["headline"], calib, payload["game_state"]
    print(f"\n0->1 late / early: {h['opener_ratio']['value']}x [{h['opener_ratio']['lo']}, {h['opener_ratio']['hi']}]"
          f"   late equaliser {h['late_equaliser']['ep']} ({h['late_equaliser']['ratio_vs_early_opener']}x early opener)")
    print(f"level late: up {gs['level_late']['up']} / down {gs['level_late']['down']} = {gs['level_late_ratio']}x"
          f"   (early {gs['level_early_ratio']}x)")
    print(f"held-out Brier: timed {c['brier']['timed']}  untimed {c['brier']['untimed']}  base {c['brier']['base']}")
    ps = payload["players"]["premium_summary"]
    print(f"timing premium: {ps['ci_above_zero']} above / {ps['ci_below_zero']} below zero of {ps['eligible']} "
          f"(chance ~{ps['expected_by_chance_each_side']} each side); leader {ps['leader']} {ps['leader_premium']}")


if __name__ == "__main__":
    main()
