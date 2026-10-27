"""
build.py — Renball Project 03 (The True Contributors)
=====================================================

Who adds the most expected points (EP) per 90 minutes, once every goal is
priced by the scoreline it changed and the minute it came (Project 02's
team-minute model) and shared with the players who made it?

  data/data.json          editorial payload (analysis.html, slides, X)
  data/dashboard/         Tabulator dashboard: manifest + one JSON per (dataset, view)

Pipeline
  1. Project 02's extraction (matches.load_all) and value model, unchanged:
     goal values V(gd + 1, bin) − V(gd, bin) from every team-minute of the
     model sample, 1,000 match-bootstrap resamples within league (seed 2026)
  2. Credits (players.py): one credit per player per goal at the goal's full
     value for every per-90 board; roles counted separately for the SCA2
     board; the old rule (each role a credit) and a 40/35/25 split as checks
  3. Minutes, positions and birth dates from the same matches (FBref match
     sheets); scope: the top 5 leagues
  4. Empirical Bayes rates (shrink.py): each EP per 90 pulled toward its
     position's average by its own noise; rank intervals from the posterior
  5. Repeatability: season-to-season correlation of each rate
  6. Award check: the model's pick per league-season against the actual
     player-of-the-season award (data/static/actual_mvps.json, with sources),
     against chance and against a goals + assists count
  7. Takeaways composed from the computed values

Units: the goal (credits), the player over 2017-18 to 2023-24 (boards), the
player-league-season (award check), the consecutive-season pair
(repeatability).

Run:
    python code/build.py

Env: RENBALL_MATCH_DATA_PATH → folder with match_data_final_<league>.pkl
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_DIR.parents[1]
P02_DIR = REPO_ROOT / "projects" / "02-points-by-gamestate"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(1, str(P02_DIR / "code"))

from config import MIN_GD, TIME_BINS  # noqa: E402  (Project 02)
import matches as X                   # noqa: E402  (Project 02)
import value_model as VM              # noqa: E402  (Project 02)
import dashboard_files as DF          # noqa: E402  (Project 02)
import players as PL                  # noqa: E402
import shrink as SH                   # noqa: E402

try:                                  # player names in the summary print (cp1252 console)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

DATA_DIR_OUT = PROJECT_DIR / "data"
DATA_JSON = DATA_DIR_OUT / "data.json"
DASHBOARD_DIR = DATA_DIR_OUT / "dashboard"
ACTUAL_MVPS = DATA_DIR_OUT / "static" / "actual_mvps.json"
P02_DATA = P02_DIR / "data" / "data.json"
CACHE_DIR = DATA_DIR_OUT / ".cache"

SEED = 2026
N_BOOT = 1000                # value-model resamples (same weights as Project 02)
N_DRAWS = 4000               # posterior draws for rank intervals
MIN_MINUTES = 900            # boards and priors: ten full matches
MIN_MINUTES_DASH = 450       # dashboard rows
MIN_EFF_INVOLVEMENTS = 50    # decisive-goals board
MIN_SCA2_SHARE_CREDITS = 100 # SCA2 share board: role credits needed
MIN_PAIR_INVOLVEMENTS = 10   # repeatability of EP per involvement: per season
MIN_PAIR_CREDITS = 20        # repeatability of the SCA2 share: role credits per season
YOUNG_MAX_AGE = 23           # "23 or under" at the end of the data
DATA_END = date(2024, 6, 30)
WEIGHTS = {"goal": 0.40, "sca1": 0.35, "sca2": 0.25}
TOP_N = 20
LATE, EARLY = len(TIME_BINS) - 1, 0
GI = lambda g: g - MIN_GD    # noqa: E731


def r(x, n=3):
    if x is None:
        return None
    x = float(x)
    return None if np.isnan(x) else round(x, n)


def fx(x, d: int = 2) -> str:
    """Half-up on the shortest decimal form, the way the page's Intl.NumberFormat rounds."""
    return str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def season_label(s: str) -> str:
    return f"{s[:4]}-{s[-2:]}"


def strip_born(name: str) -> str:
    return name.split(" (b. ")[0]


# ════════════════════════════════════════════════════════════════════════
# 1. Data and Project 02's value model
# ════════════════════════════════════════════════════════════════════════
def load() -> dict:
    R = X.load_all()
    M, G, A = R["matches"], R["goals"], R["apps"]
    ok = M[M["status"] == "ok"].reset_index(drop=True)
    usable = ok[ok["unknown_minute_goals"] == 0].reset_index(drop=True)
    model_mask = ~usable["og_affected"].to_numpy()
    G = G[G["match_id"].isin(usable["match_id"])].copy()
    G["goal_uid"] = G["match_id"] + ":" + G["event_idx"].astype(str)
    A = A[A["match_id"].isin(usable["match_id"])].copy()
    return {"M": M, "usable": usable, "model_mask": model_mask, "G": G, "A": A,
            "match_index": {m: i for i, m in enumerate(usable["match_id"])}}


def value_model(d: dict) -> dict:
    """Project 02's model on the same sample; the bootstrap is cached by a hash of its inputs."""
    usable, G, mask = d["usable"], d["G"], d["model_mask"]
    h = hashlib.sha256(repr((list(usable["match_id"]), mask.tolist(), list(G["goal_uid"]), list(G["minute_state"]),
                             N_BOOT, SEED, X.EXTRACT_VERSION)).encode()).hexdigest()[:16]
    cp = CACHE_DIR / f"value_model_{h}.pkl"
    if cp.exists():
        return pickle.loads(cp.read_bytes())
    C = VM.panel_counts(usable, G) * mask[:, None, None, None]
    vals = VM.values(C.sum(0))
    gt, gu, _ = VM.goal_value_lookup(vals)
    gt, gu = np.nan_to_num(gt), np.nan_to_num(gu)
    C2 = C.reshape(len(C), -1).astype(float)
    W, GT, GU = [], [], []
    for w in VM.boot_weights(usable["league"].to_numpy(), N_BOOT, SEED):
        v = VM.values((w @ C2).reshape(C.shape[1:]))
        W.append(w.astype(np.int16)); GT.append(v["goal_t"]); GU.append(v["goal_u"])
    out = {"vals": vals, "gt": gt, "gu": gu, "W": np.array(W), "GT": np.array(GT), "GU": np.array(GU),
           "matches_model": int(mask.sum()), "team_minutes": int(C.sum())}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in CACHE_DIR.glob("value_model_*.pkl"):
        old.unlink()
    cp.write_bytes(pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL))
    return out


def framework_block(vm: dict) -> dict:
    """The goal prices this project uses, checked against Project 02's published numbers."""
    gt = vm["vals"]["goal_t"]
    out = {"opener_early": r(gt[GI(0), EARLY]), "opener_late": r(gt[GI(0), LATE]),
           "opener_ratio": r(gt[GI(0), LATE] / gt[GI(0), EARLY], 2),
           "cushion_late": r(gt[GI(1), LATE]), "equaliser_late": r(gt[GI(-1), LATE]),
           "matches_model": vm["matches_model"], "team_minutes": vm["team_minutes"]}
    p02 = json.loads(P02_DATA.read_text(encoding="utf-8"))
    h = p02["headline"]
    same = (abs(h["opener_ratio"]["late"]["ep"] - out["opener_late"]) < 1e-9
            and abs(h["opener_ratio"]["early"]["ep"] - out["opener_early"]) < 1e-9
            and p02["sample"]["matches_model"] == out["matches_model"])
    if not same:
        raise SystemExit("goal values differ from Project 02's data.json: rebuild Project 02 first")
    out["matches_p02"] = p02["sample"]["matches_model"]
    return out


def price_goals(G: pd.DataFrame, vm: dict) -> pd.DataFrame:
    G = G.copy()
    G["gi"] = VM.gd_index(G["gd_before"])
    G["bi"] = G["minute_bin"].map(VM.BIN_INDEX)
    assert G["bi"].notna().all(), "usable matches have no goals without a minute"
    G["bi"] = G["bi"].astype(int)
    G["e"] = vm["gt"][G["gi"], G["bi"]]
    G["e_u"] = vm["gu"][G["gi"]]
    return G


# ════════════════════════════════════════════════════════════════════════
# 2. Players: pooled table over the seven seasons (top 5 leagues)
# ════════════════════════════════════════════════════════════════════════
def per_match(credits: pd.DataFrame, value: str, apps: pd.DataFrame) -> pd.DataFrame:
    """EP and minutes per (player, match), from the appearances (matches without credits count as 0)."""
    e = credits.groupby(["key", "match_id"])[value].sum().rename("e")
    m = apps.groupby(["key", "match_id"])["minutes"].sum().rename("m")
    pm = pd.concat([m, e], axis=1).dropna(subset=["m"]).fillna({"e": 0.0}).reset_index()
    return pm


def phi_by_pos(pm: pd.DataFrame, pos: pd.Series) -> dict:
    pm = pm.assign(pos=pm["key"].map(pos))
    out = {"_all": SH.dispersion(pm)}
    for p, sub in pm.groupby("pos"):
        out[p] = SH.dispersion(sub)
    return out


def player_table(inv, roles, apps, people, vm, d) -> pd.DataFrame:
    keys = pd.Index(sorted(set(apps.loc[apps["minutes"] > 0, "key"]) | set(inv["key"])))
    t = pd.DataFrame(index=keys)
    t["player"] = [PL.display(k, people) for k in keys]
    t["born"] = [k[1] for k in keys]
    g = inv.groupby("key")
    t["involvements"] = g.size()
    for role in ("goal", "sca1", "sca2"):
        t[f"inv_{role}"] = inv[inv["role"] == role].groupby("key").size()
    t["ep"] = g["e"].sum()
    t["ep_u"] = g["e_u"].sum()
    rg = roles.groupby(["key", "role"])
    rc, re = rg.size().unstack(fill_value=0), rg["e"].sum().unstack(fill_value=0.0)
    for role in ("goal", "sca1", "sca2"):
        t[f"n_{role}"] = rc.get(role)
        t[f"ep_{role}"] = re.get(role)
    t["ep_roles"] = roles.groupby("key")["e"].sum()
    t["ep_w"] = roles.groupby("key")["e_w"].sum()
    t = t.fillna({c: 0 for c in t.columns if c not in ("player", "born")})
    ap = apps[apps["minutes"] > 0]
    t["minutes"] = ap.groupby("key")["minutes"].sum().reindex(keys).fillna(0)
    t["apps"] = ap.groupby("key").size().reindex(keys).fillna(0)
    t["pos"] = PL.positions(apps).reindex(keys)
    t["team"] = PL.modal(ap, "key", "team", "minutes").reindex(keys)
    t["league"] = PL.modal(ap, "key", "league", "minutes").reindex(keys)
    t["age_end"] = [PL.age_on(b, DATA_END) for b in t["born"]]
    t["age_end"] = np.floor(t["age_end"].astype(float))           # completed years on 30 June 2024
    with np.errstate(invalid="ignore", divide="ignore"):
        m = t["minutes"].to_numpy(float)
        for col, src in (("p90", "ep"), ("p90_roles", "ep_roles"), ("p90_w", "ep_w"), ("inv_p90", "involvements")):
            t[col] = np.where(m > 0, t[src] / m * 90, np.nan)
        t["ep_per_inv"] = np.where(t["involvements"] > 0, t["ep"] / t["involvements"], np.nan)
        t["sca2_share"] = np.where(t["ep_roles"] > 0, t["ep_sca2"] / t["ep_roles"], np.nan)

    # team context: share of the team's goal value while he played (minutes as the exposure)
    team_ep = d["Gt"].groupby(["match_id", "side"])["e"].sum()
    ex = ap.join(team_ep.rename("team_ep"), on=["match_id", "side"]).fillna({"team_ep": 0.0})
    ex["exposure"] = ex["team_ep"] * ex["minutes"] / 90
    t["team_ep_on"] = ex.groupby("key")["exposure"].sum().reindex(keys).fillna(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        t["team_share"] = np.where(t["team_ep_on"] > 0, t["ep"] / t["team_ep_on"], np.nan)
    return t


def bootstrap_players(t, credits, value_rows, apps, vm, d) -> dict:
    mi = d["match_index"]
    s = PL.bootstrap_rates(
        t.index, credits["key"], credits["match_id"].map(mi).to_numpy(), credits["gi"].to_numpy(),
        credits["bi"].to_numpy(), apps["key"], apps["match_id"].map(mi).to_numpy(),
        apps["minutes"].to_numpy(float), vm["W"], vm["GT"], vm["GU"])
    return s


def add_intervals(t: pd.DataFrame, s: dict, prefix: str = "") -> None:
    ep_b, min_b = s["ep"], s["minutes"]
    t[f"{prefix}ep_lo"], t[f"{prefix}ep_hi"] = np.percentile(ep_b, [2.5, 97.5], axis=0)
    if not prefix:
        with np.errstate(invalid="ignore", divide="ignore"):
            p90_b = np.where(min_b > 0, ep_b / min_b * 90, np.nan)
        lo, hi = np.nanpercentile(p90_b, [2.5, 97.5], axis=0)
        t["p90_lo"], t["p90_hi"] = lo, hi


# ════════════════════════════════════════════════════════════════════════
# 3. Boards
# ════════════════════════════════════════════════════════════════════════
def row(t: pd.DataFrame, k, extra=()) -> dict:
    a = t.loc[k]
    out = {"player": a["player"], "team": a["team"], "league": X.LEAGUE_LABELS.get(a["league"], a["league"]),
           "pos": a["pos"] if isinstance(a["pos"], str) else None,
           "age_end": r(a["age_end"], 1), "minutes": int(a["minutes"]), "apps": int(a["apps"]),
           "involvements": int(a["involvements"]), "goals": int(a["inv_goal"]),
           "assists": int(a["inv_sca1"]), "pre_assists": int(a["inv_sca2"]),
           "ep": r(a["ep"], 2), "ep_lo": r(a["ep_lo"], 2), "ep_hi": r(a["ep_hi"], 2),
           "p90": r(a["p90"], 3), "p90_lo": r(a["p90_lo"], 3), "p90_hi": r(a["p90_hi"], 3),
           "theta": r(a["theta"], 3), "theta_lo": r(a["theta_lo"], 3), "theta_hi": r(a["theta_hi"], 3),
           "pull_pct": r(a["pull"] * 100, 1),
           "team_share_pct": r(a["team_share"] * 100, 1)}
    for c in ("rank", "rank_lo", "rank_hi"):
        if c in t.columns and pd.notna(a.get(c)):
            out[c] = int(a[c])
    if "p_top10" in t.columns and pd.notna(a.get("p_top10")):
        out["p_top10_pct"] = r(a["p_top10"] * 100, 0)
    for c in extra:
        out[c] = a[c] if not isinstance(a[c], (float, np.floating)) else r(a[c], 3)
    return out


def eb_pooled(t: pd.DataFrame, phi: dict, *, col: str = "p90") -> tuple[pd.DataFrame, dict]:
    base = t[t["minutes"] > 0].copy()
    base["grp"] = base["pos"].fillna("_all")
    x = base.rename(columns={col: "p90_x"})[["p90_x", "minutes", "grp"]].rename(columns={"p90_x": "p90"})
    shr, priors = SH.eb_block(x, phi, group="grp", floor=MIN_MINUTES)
    return shr, priors


def rank_block(t: pd.DataFrame) -> pd.DataFrame:
    el = t[t["minutes"] >= MIN_MINUTES].copy()
    ri = SH.rank_intervals(el["theta"].to_numpy(), el["theta_sd"].to_numpy(), draws=N_DRAWS, seed=SEED)
    el["rank"] = el["theta"].rank(ascending=False, method="first").astype(int)
    el["rank_lo"], el["rank_hi"], el["p_top10"] = ri["lo"], ri["hi"], ri["p_top"]
    return el


def credit_rule_block(t: pd.DataFrame, el: pd.DataFrame, phi_roles: dict, phi_w: dict) -> dict:
    """Old rule (each role a credit) and a 40/35/25 split, shrunk the same way; ranks compared."""
    out = {}
    base_rank = el["rank"]
    top = base_rank[base_rank <= TOP_N].index
    for name, col, phi in (("roles", "p90_roles", phi_roles), ("weighted", "p90_w", phi_w)):
        shr, _ = eb_pooled(t, phi, col=col)
        e2 = shr.loc[el.index]
        rk = e2["theta"].rank(ascending=False, method="first").astype(int)
        top_v = rk[rk <= 10].index
        out[name] = {
            "top10_overlap": int(len(set(top_v) & set(base_rank[base_rank <= 10].index))),
            "rank_corr": r(np.corrcoef(base_rank.rank(), rk.rank())[0, 1], 3),
            "leader": t.loc[rk.idxmin(), "player"],
            "shift": [{"player": t.loc[k, "player"], "rank_full": int(base_rank[k]), "rank_alt": int(rk[k])}
                      for k in sorted(set(top) | set(rk[rk <= TOP_N].index), key=lambda k: base_rank[k])],
        }
        el[f"rank_{name}"] = rk
    out["weights"] = {"scorer": WEIGHTS["goal"], "sca1": WEIGHTS["sca1"], "sca2": WEIGHTS["sca2"]}
    big = max(out["weighted"]["shift"], key=lambda x: x["rank_full"] - x["rank_alt"])
    drop = min(out["weighted"]["shift"], key=lambda x: x["rank_full"] - x["rank_alt"])
    out["weighted"]["biggest_riser"] = big
    out["weighted"]["biggest_faller"] = drop
    return out


# ════════════════════════════════════════════════════════════════════════
# 4. Repeatability: season to season
# ════════════════════════════════════════════════════════════════════════
def season_table(inv, roles, apps) -> pd.DataFrame:
    """Per (player, season), all top-5 leagues together."""
    g = inv.groupby(["key", "season"])
    s = pd.DataFrame({"ep": g["e"].sum(), "involvements": g.size()})
    rc = roles.groupby(["key", "season", "role"]).size().unstack(fill_value=0)
    s = s.join(rc, how="outer")
    s["minutes"] = apps[apps["minutes"] > 0].groupby(["key", "season"])["minutes"].sum()
    s = s.fillna(0)
    s = s[s["minutes"] > 0]
    s["p90"] = s["ep"] / s["minutes"] * 90
    s["inv_p90"] = s["involvements"] / s["minutes"] * 90
    s["ep_per_inv"] = np.where(s["involvements"] > 0, s["ep"] / s["involvements"].clip(lower=1), np.nan)
    rcred = s[["goal", "sca1", "sca2"]].sum(axis=1)
    s["role_credits"] = rcred
    s["sca2_share"] = np.where(rcred > 0, s["sca2"] / rcred.clip(lower=1), np.nan)
    return s.reset_index()


def pairs(s: pd.DataFrame, col: str, ok) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    seasons = sorted(s["season"].unique())
    nxt = {a: b for a, b in zip(seasons, seasons[1:])}
    a = s[ok(s)].copy()
    a["next"] = a["season"].map(nxt)
    b = a.merge(a[["key", "season", col]], left_on=["key", "next"], right_on=["key", "season"],
                suffixes=("", "_next"))
    return b[col].to_numpy(float), b[f"{col}_next"].to_numpy(float), b["key"].astype(str).to_numpy()


def repeatability_block(s: pd.DataFrame) -> dict:
    tests = {
        "p90": ("EP per 90", "p90", lambda x: x["minutes"] >= MIN_MINUTES),
        "inv_p90": ("Goal involvements per 90", "inv_p90", lambda x: x["minutes"] >= MIN_MINUTES),
        "ep_per_inv": ("EP per involvement", "ep_per_inv", lambda x: x["involvements"] >= MIN_PAIR_INVOLVEMENTS),
        "sca2_share": ("SCA2 share of credits", "sca2_share", lambda x: x["role_credits"] >= MIN_PAIR_CREDITS),
    }
    out = {}
    for i, (k, (label, col, ok)) in enumerate(tests.items()):
        a, b, cl = pairs(s, col, ok)
        res = SH.correlation_ci(a, b, cl, n_boot=N_BOOT, seed=SEED + i)
        out[k] = {"label": label, "r": r(res["r"], 2), "lo": r(res["lo"], 2), "hi": r(res["hi"], 2),
                  "pairs": res["pairs"], "players": res["players"]}
    out["min_minutes"] = MIN_MINUTES
    out["min_involvements"] = MIN_PAIR_INVOLVEMENTS
    out["min_role_credits"] = MIN_PAIR_CREDITS
    return out


# ════════════════════════════════════════════════════════════════════════
# 5. The award check
# ════════════════════════════════════════════════════════════════════════
def award_block(inv, apps, people, pos, phi) -> tuple[dict, list]:
    actual = json.loads(ACTUAL_MVPS.read_text(encoding="utf-8"))
    g = inv.groupby(["key", "league", "season"])
    s = pd.DataFrame({"ep": g["e"].sum(), "involvements": g.size(),
                      "ga": inv[inv["role"].isin(["goal", "sca1"])].groupby(["key", "league", "season"]).size()})
    s["minutes"] = apps[apps["minutes"] > 0].groupby(["key", "league", "season"])["minutes"].sum()
    s = s.reset_index()
    s = s.dropna(subset=["minutes"]).fillna({"ep": 0.0, "involvements": 0, "ga": 0})
    s["p90"] = s["ep"] / s["minutes"] * 90
    s["grp"] = s["key"].map(pos).fillna("_all")
    shr, priors = SH.eb_block(s[["p90", "minutes", "grp"]], phi, group="grp", floor=MIN_MINUTES)
    s["theta"] = shr["theta"].to_numpy()
    s["player"] = [PL.display(k, people) for k in s["key"]]
    s["pos"] = s["key"].map(pos)
    cells, n_win, exact, top3, top10, chance, chance3, ga_hits, ep_hits, ranks, ineligible =         [], 0, 0, 0, 0, 0.0, 0.0, 0, 0, [], []
    for lg in X.TOP5:
        for se in sorted(s["season"].unique()):
            c = s[(s["league"] == lg) & (s["season"] == se) & (s["minutes"] >= MIN_MINUTES)]
            c = c.sort_values("theta", ascending=False).reset_index(drop=True)
            if c.empty:
                continue
            pick = c.iloc[0]
            ga = c.sort_values(["ga", "minutes"], ascending=[False, True]).iloc[0]
            vol = c.sort_values("ep", ascending=False).iloc[0]
            aw = actual["by_league"].get(lg, {}).get(se, {})
            win = aw.get("winner")
            cell = {"league": X.LEAGUE_LABELS[lg], "code": lg, "season": se, "season_label": season_label(se),
                    "eligible": int(len(c)),
                    "pick": pick["player"], "pick_team": PL.modal(apps[(apps["key"] == pick["key"]) & (apps["league"] == lg) & (apps["season"] == se)], "key", "team", "minutes").iloc[0],
                    "pick_theta": r(pick["theta"], 3), "pick_p90": r(pick["p90"], 3), "pick_minutes": int(pick["minutes"]),
                    "ga_leader": ga["player"], "ga_leader_ga": int(ga["ga"]),
                    "ep_leader": vol["player"], "ep_leader_ep": r(vol["ep"], 2),
                    "winner": win, "award": aw.get("award"), "source": aw.get("source"), "note": aw.get("note")}
            if win:
                n_win += 1
                want = PL.norm_name(win)
                year = aw.get("born_year")
                hit = c[[PL.norm_name(strip_born(p)) == want and (year is None or k[1][:4] == str(year))
                         for p, k in zip(c["player"], c["key"])]]
                is_gk = (not hit.empty and hit.iloc[0]["pos"] == "GK") or aw.get("position") == "GK"
                if hit.empty or is_gk:
                    cell["winner_rank"] = None
                    cell["winner_status"] = "goalkeeper: the credits never reach him" if is_gk else "not eligible"
                    ineligible.append({"league": cell["league"], "season": cell["season_label"], "winner": win,
                                       "reason": "goalkeeper" if is_gk else "under the minutes floor"})
                    cells.append(cell)
                    continue
                else:
                    rk = int(hit.index[0]) + 1
                    cell["winner_rank"] = rk
                    cell["winner_theta"] = r(hit.iloc[0]["theta"], 3)
                    cell["winner_status"] = "eligible"
                    ranks.append(rk)
                    exact += rk == 1
                    top3 += rk <= 3
                    top10 += rk <= 10
                chance += 1 / len(c)
                chance3 += min(3, len(c)) / len(c)
                ga_hits += PL.norm_name(strip_born(ga["player"])) == want
                ep_hits += PL.norm_name(strip_born(vol["player"])) == want
            cells.append(cell)
    out = {
        "min_minutes": MIN_MINUTES, "cells": len(cells), "cells_with_winner": n_win,
        "exact": int(exact), "top3": int(top3), "top10": int(top10),
        "eligible_winners": len(ranks), "ineligible": ineligible, "missed": len(ranks) - int(top10),
        "median_rank": r(float(np.median(ranks)), 1) if ranks else None,
        "chance_exact": r(chance, 1), "chance_top3": r(chance3, 1),
        "ga_exact": int(ga_hits), "ep_total_exact": int(ep_hits),
        "eligible_min": int(min(x["eligible"] for x in cells)), "eligible_max": int(max(x["eligible"] for x in cells)),
        "grid": cells,
        "priors": {k: {kk: r(vv, 4) for kk, vv in v.items()} for k, v in priors.items()},
        "awards_by_league": {X.LEAGUE_LABELS[lg]: sorted({v.get("award") for v in actual["by_league"][lg].values()
                                                          if v.get("award")}) for lg in X.TOP5},
    }
    season_rows = s
    return out, season_rows


# ════════════════════════════════════════════════════════════════════════
# 6. SCA2 and decisive goals
# ════════════════════════════════════════════════════════════════════════
def sca2_block(t: pd.DataFrame, s2: dict, roles: pd.DataFrame) -> dict:
    ep_b = s2["ep"]
    lo, hi = np.percentile(ep_b, [2.5, 97.5], axis=0)
    t = t.assign(sca2_lo=lo, sca2_hi=hi)
    ranks = (-ep_b).argsort(axis=1).argsort(axis=1) + 1
    t["sca2_rank_lo"], t["sca2_rank_hi"] = np.percentile(ranks, [2.5, 97.5], axis=0)
    top = t.sort_values("ep_sca2", ascending=False).head(TOP_N)

    def srow(k, i):
        a = t.loc[k]
        return {"rank": i + 1, "player": a["player"], "team": a["team"],
                "league": X.LEAGUE_LABELS.get(a["league"], a["league"]), "pos": a["pos"] if isinstance(a["pos"], str) else None,
                "sca2": int(a["n_sca2"]), "ep_sca2": r(a["ep_sca2"], 2), "ep_sca2_lo": r(a["sca2_lo"], 2),
                "ep_sca2_hi": r(a["sca2_hi"], 2), "rank_lo": int(np.floor(a["sca2_rank_lo"])),
                "rank_hi": int(np.ceil(a["sca2_rank_hi"])),
                "ep_goal": r(a["ep_goal"], 2), "ep_sca1": r(a["ep_sca1"], 2), "ep_roles": r(a["ep_roles"], 2),
                "share_goal_pct": r(a["ep_goal"] / a["ep_roles"] * 100, 1),
                "share_sca1_pct": r(a["ep_sca1"] / a["ep_roles"] * 100, 1),
                "share_sca2_pct": r(a["sca2_share"] * 100, 1),
                "minutes": int(a["minutes"])}

    rows = [srow(k, i) for i, k in enumerate(top.index)]
    rc = t["n_goal"] + t["n_sca1"] + t["n_sca2"]
    sh = t[rc >= MIN_SCA2_SHARE_CREDITS].sort_values("sca2_share", ascending=False).head(10)
    share_rows = [srow(k, i) for i, k in enumerate(sh.index)]
    goals_n = roles["goal_uid"].nunique()
    leader = rows[0]
    return {"top": rows, "top_share": share_rows, "min_share_credits": MIN_SCA2_SHARE_CREDITS,
            "share_median_pct": r(t.loc[rc >= MIN_SCA2_SHARE_CREDITS, "sca2_share"].median() * 100, 1),
            "share_players": int((rc >= MIN_SCA2_SHARE_CREDITS).sum()),
            "top2_overlap": bool(rows[1]["ep_sca2_hi"] >= rows[0]["ep_sca2_lo"]),
            "second_rank_lo": rows[1]["rank_lo"], "second_rank_hi": rows[1]["rank_hi"],
            "leader": leader["player"], "goals": int(goals_n)}


def efficiency_block(t: pd.DataFrame, s: dict, inv: pd.DataFrame, d: dict) -> dict:
    """EP per involvement: how decisive the average goal a player is involved in is."""
    mi = d["match_index"]
    cp = t.index.get_indexer(inv["key"])
    cm = inv["match_id"].map(mi).to_numpy()
    W = d["vm"]["W"]
    cnt_b = np.stack([np.bincount(cp, W[k][cm].astype(float), len(t)) for k in range(len(W))])
    with np.errstate(invalid="ignore", divide="ignore"):
        epi_b = np.where(cnt_b > 0, s["ep"] / cnt_b, np.nan)
    lo, hi = np.nanpercentile(epi_b, [2.5, 97.5], axis=0)
    t = t.assign(epi_lo=lo, epi_hi=hi)
    avg = float(inv["e"].mean())
    el = t[t["involvements"] >= MIN_EFF_INVOLVEMENTS]
    above, below = el[el["epi_lo"] > avg], el[el["epi_hi"] < avg]

    def erow(k, i):
        a = t.loc[k]
        return {"rank": i + 1, "player": a["player"], "team": a["team"], "involvements": int(a["involvements"]),
                "ep": r(a["ep"], 2), "ep_per_inv": r(a["ep_per_inv"], 3), "lo": r(a["epi_lo"], 3),
                "hi": r(a["epi_hi"], 3), "time_blind": r(a["ep_u"] / a["involvements"], 3)}

    return {"avg": r(avg, 3), "min_involvements": MIN_EFF_INVOLVEMENTS, "eligible": int(len(el)),
            "above": int(len(above)), "below": int(len(below)),
            "chance_each_side": int(round(len(el) * 0.025)),
            "top": [erow(k, i) for i, k in enumerate(el.sort_values("ep_per_inv", ascending=False).head(10).index)],
            "bottom": [erow(k, i) for i, k in enumerate(el.sort_values("ep_per_inv").head(5).index)],
            "bottom_teams": sorted({t.loc[k, "team"] for k in el.sort_values("ep_per_inv").head(5).index}),
            "t": t}


# ════════════════════════════════════════════════════════════════════════
# 7. Data quality and provenance
# ════════════════════════════════════════════════════════════════════════
def data_quality(d: dict, roles: pd.DataFrame, inv: pd.DataFrame, apps: pd.DataFrame, people: dict, t) -> dict:
    Gt = d["Gt"]
    n = len(Gt)
    self1 = Gt["goalscorer"].eq(Gt["sca1_creator"])
    has1, has2 = Gt["sca1_creator"].notna(), Gt["sca2_creator"].notna()
    app_pairs = set(zip(apps["key"], apps["match_id"]))
    no_app = sum((k, m) not in app_pairs for k, m in zip(inv["key"], inv["match_id"]))
    by_season = (Gt.groupby("season").agg(goals=("goal_uid", "size"),
                                          sca2=("sca2_creator", lambda x: x.notna().mean() * 100))
                   .reset_index())
    ambiguous = sorted({k[0] for k, v in people.items() if v > 1})
    usable_t = d["usable"][d["usable"]["league"].isin(X.TOP5)]
    return {
        "matches": int(len(usable_t)), "goals": int(n), "seasons_n": int(Gt["season"].nunique()),
        "goals_og_matches": int(Gt["match_id"].isin(usable_t.loc[usable_t["og_affected"], "match_id"]).sum()),
        "goals_og_matches_pct": r(Gt["match_id"].isin(usable_t.loc[usable_t["og_affected"], "match_id"]).mean() * 100, 1),
        "sca1_pct": r(has1.mean() * 100, 1), "sca2_pct": r(has2.mean() * 100, 1),
        "sca2_missing_pct": r((1 - has2.mean()) * 100, 1),
        "sca2_pct_min": r(by_season["sca2"].min(), 1), "sca2_pct_max": r(by_season["sca2"].max(), 1),
        "self_sca1_pct": r(self1.mean() * 100, 1),
        "role_credits": int(len(roles)), "credits": int(len(inv)),
        "collapsed": int(len(roles) - len(inv)), "collapsed_pct": r((len(roles) - len(inv)) / len(roles) * 100, 1),
        "credits_without_appearance": int(no_app),
        "players": int((t["minutes"] > 0).sum()), "players_eligible": int((t["minutes"] >= MIN_MINUTES).sum()),
        "namesakes": len(ambiguous),
        "first_season": season_label(sorted(Gt["season"].unique())[0]),
        "last_season": season_label(sorted(Gt["season"].unique())[-1]),
    }


# ════════════════════════════════════════════════════════════════════════
# 8. Takeaways
# ════════════════════════════════════════════════════════════════════════
def takeaways_from(p: dict) -> dict:
    """Four audiences, evidence labels per CLAUDE.md §4.3. Every number comes from the payload."""
    b, rep, aw, sca2, cr = p["board"], p["repeatability"], p["awards"], p["sca2"], p["credit_rules"]
    top = b["top"][0]
    return {
        "intro": (f"Every goal from {p['quality']['matches']:,} top-5 matches priced by Project 02's model and "
                  f"shared with the players who made it. What it says for each audience:"),
        "clubs": [
            {"text": (f"Rank adjusted rates, not raw per-90s: **{b['raw_top10_dropped']}** of the raw top 10 are "
                      f"short careers that drop out."),
             "evidence": "strong",
             "basis": f"{p['quality']['players_eligible']:,} players · empirical Bayes by position"},
            {"text": (f"EP per 90 repeats (r = **{fx(rep['p90']['r'])}**); decisive-looking goals barely do "
                      f"(r = {fx(rep['ep_per_inv']['r'])}). Pay for involvement."),
             "evidence": "strong",
             "basis": (f"95% CI {fx(rep['p90']['lo'])}–{fx(rep['p90']['hi'])} and "
                       f"{fx(rep['ep_per_inv']['lo'])}–{fx(rep['ep_per_inv']['hi'])}")},
        ],
        "agents": [
            {"text": (f"A pre-assist habit is partly real: the SCA2 share repeats (r = **{fx(rep['sca2_share']['r'])}**). "
                      f"A fair line in a playmaker's case."),
             "evidence": "moderate",
             "basis": (f"{rep['sca2_share']['pairs']:,} season pairs · 95% CI {fx(rep['sca2_share']['lo'])}–"
                       f"{fx(rep['sca2_share']['hi'])} · SCA2 on {p['quality']['sca2_pct']:.0f}% of goals")},
            {"text": (f"Awards follow box scores: the goals + assists leader matched **{aw['ga_exact']}** of "
                      f"{aw['eligible_winners']} winners, the EP model {aw['exact']}."),
             "evidence": "exploratory",
             "basis": "five different awards · a count, not a test"},
        ],
        "managers": [],
        "coaches": [],
    }


# ════════════════════════════════════════════════════════════════════════
# 9. Dashboard
# ════════════════════════════════════════════════════════════════════════
DATASET_HELP = {
    "Players": ("One row per player over 2017-18 to 2023-24, top 5 leagues, at least 450 minutes. A goal credits "
                "its scorer, SCA1 and SCA2 once per player, at the goal's time-aware value from Project 02. "
                "theta is the rate pulled toward the position average (empirical Bayes); rank, rank_lo and "
                "rank_hi only for players with 900+ minutes."),
    "Player-seasons": ("One row per player, league and season (450+ minutes). theta_season is the season's rate "
                       "pulled toward the position average; it decides the model's pick in the award check."),
    "Award check": ("The model's pick per league-season (highest theta_season, 900+ minutes) next to the actual "
                    "award winner and the goals + assists leader. Sources link to the award pages."),
    "SCA2 (pre-assists)": ("Roles counted separately: every SCA2 credit counts, even when the same player also "
                           "scored or assisted. ep_sca2_lo / hi: 95% bootstrap interval. Players with 10+ SCA2 "
                           "credits."),
    "Decisive goals": ("EP per involvement: the average value of the goals a player was involved in. Players with "
                       "50+ involvements. lo / hi: 95% bootstrap interval."),
}
COLUMN_HELP = {
    "player": "Player (namesakes carry their birth year).",
    "team": "Team he played most minutes for in this scope.",
    "league": "League he played most minutes in.",
    "pos": "Position he played most minutes in: GK, DF, MF or FW (FBref match sheets).",
    "age_end": "Age on 30 June 2024, the end of the data.",
    "minutes": "Minutes played in the same matches as the goals.",
    "apps": "Matches with minutes.",
    "involvements": "Goals he was involved in as scorer, SCA1 or SCA2, one credit per goal.",
    "goals": "Involvements as the scorer.",
    "assists": "Involvements as SCA1 (the action right before the shot) without scoring.",
    "pre_assists": "Involvements as SCA2 (the action before that) only.",
    "ep": "Expected points from his involvements, each at the goal's time-aware value.",
    "ep_lo": "Lower end of the 95% bootstrap interval of ep.",
    "ep_hi": "Upper end of the 95% bootstrap interval of ep.",
    "p90": "EP per 90 minutes, as measured.",
    "p90_lo": "Lower end of the 95% bootstrap interval of p90.",
    "p90_hi": "Upper end of the 95% bootstrap interval of p90.",
    "theta": "EP per 90 pulled toward the average for his position, by more when his minutes are few.",
    "theta_lo": "Lower end of the 95% posterior interval of theta.",
    "theta_hi": "Upper end of the 95% posterior interval of theta.",
    "pull_pct": "How much of the gap to the position average the shrinkage removed (%).",
    "rank": "Rank by theta among players with 900+ minutes.",
    "rank_lo": "Best plausible rank (2.5th percentile of the posterior rank).",
    "rank_hi": "Worst plausible rank (97.5th percentile).",
    "p_top10_pct": "Chance (%) that his true rate is in the top 10.",
    "team_share_pct": "His EP as a share (%) of his team's goal value while he played (minutes as exposure).",
    "p90_roles": "EP per 90 under the old rule: every role a credit, so a self-assisted goal counts twice.",
    "p90_weighted": "EP per 90 with the goal split 40 / 35 / 25 between scorer, SCA1 and SCA2.",
    "season": "Season.",
    "theta_season": "The season's EP per 90 pulled toward the position average.",
    "ga": "Goals plus SCA1 assists in the season (one per goal).",
    "eligible": "Players with 900+ minutes in this league-season.",
    "pick": "The model's pick: highest theta_season.",
    "pick_theta": "The pick's theta_season.",
    "winner": "Actual award winner.",
    "award": "The award used for this league.",
    "winner_rank": "Where the winner ranks on the model's list (blank: goalkeeper or under the minutes floor).",
    "ga_leader": "Player with the most goals + assists in the league-season.",
    "source": "Where the award winner is documented.",
    "sca2": "SCA2 credits (roles counted separately).",
    "ep_sca2": "EP from SCA2 credits.",
    "ep_sca2_lo": "Lower end of the 95% bootstrap interval of ep_sca2.",
    "ep_sca2_hi": "Upper end of the 95% bootstrap interval of ep_sca2.",
    "share_sca2_pct": "SCA2 share (%) of his EP with roles counted separately.",
    "ep_per_inv": "EP per involvement: the average value of the goals he was involved in.",
    "lo": "Lower end of the 95% bootstrap interval.",
    "hi": "Upper end of the 95% bootstrap interval.",
    "time_blind": "The same with time-blind goal values (scoreline only).",
}
DASH_DIRS = {"Players": "players", "Player-seasons": "player_seasons", "Award check": "award_check",
             "SCA2 (pre-assists)": "sca2", "Decisive goals": "decisive_goals"}


def dashboard_payload(t, el, seasons, awards, eff_t, created_at) -> dict:
    dash = t[t["minutes"] >= MIN_MINUTES_DASH].copy()
    for c in ("rank", "rank_lo", "rank_hi", "p_top10"):
        dash[c] = el[c].reindex(dash.index)

    def prow(a):
        x = {"player": a["player"], "team": a["team"], "league": X.LEAGUE_LABELS.get(a["league"], a["league"]),
             "pos": a["pos"] if isinstance(a["pos"], str) else None, "age_end": r(a["age_end"], 1),
             "minutes": int(a["minutes"]), "apps": int(a["apps"]), "involvements": int(a["involvements"]),
             "goals": int(a["inv_goal"]), "assists": int(a["inv_sca1"]), "pre_assists": int(a["inv_sca2"]),
             "ep": r(a["ep"], 2), "ep_lo": r(a["ep_lo"], 2), "ep_hi": r(a["ep_hi"], 2),
             "p90": r(a["p90"]), "p90_lo": r(a["p90_lo"]), "p90_hi": r(a["p90_hi"]),
             "theta": r(a["theta"]), "theta_lo": r(a["theta_lo"]), "theta_hi": r(a["theta_hi"]),
             "pull_pct": r(a["pull"] * 100, 1), "rank": None if pd.isna(a["rank"]) else int(a["rank"]),
             "rank_lo": None if pd.isna(a["rank_lo"]) else int(a["rank_lo"]),
             "rank_hi": None if pd.isna(a["rank_hi"]) else int(a["rank_hi"]),
             "p_top10_pct": None if pd.isna(a["p_top10"]) else r(a["p_top10"] * 100, 0),
             "team_share_pct": r(a["team_share"] * 100, 1),
             "p90_roles": r(a["p90_roles"]), "p90_weighted": r(a["p90_w"])}
        return x

    rows = [prow(a) for _, a in dash.sort_values("theta", ascending=False).iterrows()]
    srows = seasons[seasons["minutes"] >= MIN_MINUTES_DASH].sort_values("theta", ascending=False)
    snest = {}
    for _, a in srows.iterrows():
        snest.setdefault(X.LEAGUE_LABELS[a["league"]], {}).setdefault(season_label(a["season"]), []).append(
            {"player": a["player"], "pos": a["pos"] if isinstance(a["pos"], str) else None,
             "season": season_label(a["season"]), "minutes": int(a["minutes"]),
             "involvements": int(a["involvements"]), "ga": int(a["ga"]), "ep": r(a["ep"], 2),
             "p90": r(a["p90"]), "theta_season": r(a["theta"])})
    grid = [{"league": c["league"], "season": c["season_label"], "eligible": c["eligible"], "pick": c["pick"],
             "pick_theta": c["pick_theta"], "winner": c["winner"], "award": c["award"],
             "winner_rank": c.get("winner_rank"), "ga_leader": c["ga_leader"], "source": c["source"]}
            for c in awards["grid"]]
    s2 = t[t["n_sca2"] >= 10].sort_values("ep_sca2", ascending=False)
    s2rows = [{"player": a["player"], "team": a["team"], "league": X.LEAGUE_LABELS.get(a["league"], a["league"]),
               "pos": a["pos"] if isinstance(a["pos"], str) else None, "sca2": int(a["n_sca2"]),
               "ep_sca2": r(a["ep_sca2"], 2), "ep_sca2_lo": r(a["sca2_lo"], 2), "ep_sca2_hi": r(a["sca2_hi"], 2),
               "share_sca2_pct": r(a["sca2_share"] * 100, 1), "minutes": int(a["minutes"])}
              for _, a in s2.iterrows()]
    ef = eff_t[eff_t["involvements"] >= MIN_EFF_INVOLVEMENTS].sort_values("ep_per_inv", ascending=False)
    efrows = [{"player": a["player"], "team": a["team"], "involvements": int(a["involvements"]),
               "ep": r(a["ep"], 2), "ep_per_inv": r(a["ep_per_inv"]), "lo": r(a["epi_lo"]), "hi": r(a["epi_hi"]),
               "time_blind": r(a["ep_u"] / a["involvements"])} for _, a in ef.iterrows()]
    return {"meta": {"created_at": created_at}, "columnHelp": COLUMN_HELP, "datasetHelp": DATASET_HELP,
            "datasets": {"Players": {"All leagues": {"All leagues": rows}},
                         "Player-seasons": {"Per League & Season": snest},
                         "Award check": {"All": {"All": grid}},
                         "SCA2 (pre-assists)": {"All": {"All": s2rows}},
                         "Decisive goals": {"All": {"All": efrows}}}}


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════
def main() -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    print("[1/8] Matches, goals, appearances (Project 02 extraction) ...")
    d = load()
    print(f"[2/8] Value model + {N_BOOT} bootstrap resamples (seed {SEED}) ...")
    vm = value_model(d)
    d["vm"] = vm
    fw = framework_block(vm)
    G = price_goals(d["G"], vm)
    d["Gt"] = Gt = G[G["league"].isin(X.TOP5)].copy()
    apps = d["A"][d["A"]["league"].isin(X.TOP5)].copy()

    print("[3/8] Credits ...")
    canon, people = PL.identities(G, d["A"])
    roles, inv = PL.credit_tables(Gt, canon, people)
    roles["e_w"] = PL.weighted_credit(roles, WEIGHTS)
    apps["key"] = PL.keyof(canon, apps["player"], apps["born"])
    for df in (roles, inv):
        df["gi"] = VM.gd_index(df["gd_before"])
        df["bi"] = df["minute_bin"].map(VM.BIN_INDEX).astype(int)

    print("[4/8] Players, bootstrap intervals ...")
    t = player_table(inv, roles, apps, people, vm, d)
    s_inv = bootstrap_players(t, inv, "e", apps, vm, d)
    add_intervals(t, s_inv)
    s_sca2 = bootstrap_players(t, roles[roles["role"] == "sca2"], "e", apps, vm, d)
    pos = t["pos"]

    print("[5/8] Empirical Bayes, rank intervals ...")
    pm = per_match(inv, "e", apps)
    phi = phi_by_pos(pm, pos)
    shr, priors = eb_pooled(t, phi)
    for c in ("theta", "theta_sd", "theta_lo", "theta_hi", "pull"):
        t[c] = shr[c].reindex(t.index)
    el = rank_block(t)
    for c in ("rank", "rank_lo", "rank_hi", "p_top10"):
        t[c] = el[c].reindex(t.index)
    raw10 = el.sort_values("p90", ascending=False).head(10).index
    eb10 = el.sort_values("theta", ascending=False).head(10).index
    phi_roles = phi_by_pos(per_match(roles, "e", apps), pos)
    phi_w = phi_by_pos(per_match(roles, "e_w", apps), pos)
    cr = credit_rule_block(t, el, phi_roles, phi_w)

    print("[6/8] Repeatability, award check ...")
    seasons = season_table(inv, roles, apps)
    rep = repeatability_block(seasons)
    awards, season_rows = award_block(inv, apps, people, pos, phi)

    print("[7/8] SCA2, decisive goals ...")
    sca2 = sca2_block(t, s_sca2, roles)
    t["sca2_lo"], t["sca2_hi"] = np.percentile(s_sca2["ep"], [2.5, 97.5], axis=0)
    eff = efficiency_block(t, s_inv, inv, d)
    eff_t = eff.pop("t")

    top = [row(t, k) for k in el.sort_values("rank").head(TOP_N).index]
    raw_top = [row(t, k) for k in raw10]
    positions = {p: [row(t, k) for k in el[el["pos"] == p].sort_values("theta", ascending=False).head(5).index]
                 for p in ("FW", "MF", "DF")}
    young_el = el[(el["age_end"] <= YOUNG_MAX_AGE)]
    young = [row(t, k) for k in young_el.sort_values("theta", ascending=False).head(10).index]
    gk = el[el["pos"] == "GK"]
    fw_el = el[el["pos"] == "FW"]
    board = {
        "min_minutes": MIN_MINUTES, "eligible": int(len(el)), "top": top, "raw_top": raw_top,
        "raw_top10_dropped": int(len(set(raw10) - set(eb10))),
        "raw_top10_dropped_names": [t.loc[k, "player"] for k in raw10 if k not in set(eb10)],
        "top10_rank_hi_max": int(max(x["rank_hi"] for x in top[:10])),
        "leader": top[0]["player"], "leader_p_top10_pct": top[0].get("p_top10_pct"),
        "top10_sure": int(sum((x.get("p_top10_pct") or 0) >= 95 for x in top[:10])),
        "priors": {k: {"mu": r(v["mu"], 3), "tau": r(np.sqrt(v["tau2"]), 3), "n": v["n"], "phi": r(v["phi"], 5)}
                   for k, v in priors.items()},
        "pull_at": [{"minutes": m,
                     "pull_pct": r(100 * (1 - priors["FW"]["tau2"] / (priors["FW"]["tau2"] + 8100 * phi["FW"] / m)), 0)}
                    for m in (1000, 3000, 10000)],
        "gk_max_theta": r(gk["theta"].max(), 3) if len(gk) else None,
        "fw_median_theta": r(fw_el["theta"].median(), 3),
        "team_share_top10_min": r(min(x["team_share_pct"] for x in top[:10]), 1),
        "team_share_top10_max": r(max(x["team_share_pct"] for x in top[:10]), 1),
    }
    quality = data_quality(d, roles, inv, apps, people, t)

    payload = {
        "generated_at": created_at,
        "meta": {"leagues": [{"code": lg, "label": X.LEAGUE_LABELS[lg]} for lg in X.TOP5],
                 "seasons": sorted(Gt["season"].unique()),
                 "params": {"boot_resamples": N_BOOT, "posterior_draws": N_DRAWS, "seed": SEED,
                            "min_minutes": MIN_MINUTES, "min_minutes_dashboard": MIN_MINUTES_DASH,
                            "min_eff_involvements": MIN_EFF_INVOLVEMENTS, "young_max_age": YOUNG_MAX_AGE,
                            "data_end": DATA_END.isoformat(), "weights": WEIGHTS,
                            "weights_pct": {k: int(round(v * 100)) for k, v in WEIGHTS.items()}}},
        "framework": fw,
        "quality": quality,
        "board": board,
        "positions": positions,
        "young": {"max_age": YOUNG_MAX_AGE, "rows": young, "eligible": int(len(young_el))},
        "credit_rules": cr,
        "repeatability": rep,
        "awards": awards,
        "sca2": sca2,
        "efficiency": eff,
    }
    payload["takeaways"] = takeaways_from(payload)

    print("[8/8] Writing data.json + dashboard ...")
    DATA_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"  wrote {DATA_JSON.relative_to(PROJECT_DIR)} ({DATA_JSON.stat().st_size / 1024:.0f} KB)")
    t["sca2_lo"], t["sca2_hi"] = np.percentile(s_sca2["ep"], [2.5, 97.5], axis=0)
    dash = dashboard_payload(t, el, season_rows, awards, eff_t, created_at)
    DF.DATASET_DIRS.clear()
    DF.DATASET_DIRS.update(DASH_DIRS)
    DF.CONTRIB_DATASETS.clear()
    DF.SPARSE_KEEP_KEYS.update(COLUMN_HELP.keys())
    oversize = DF.write(dash, DASHBOARD_DIR)
    for name, mb in oversize:
        print(f"  WARNING: {name} is {mb:.1f} MB (over 5 MB)")

    print("\n-- summary --")
    for x in top[:12]:
        print(f"  {x['rank']:>2} {x['player']:<26} {x['team']:<18} {x['pos']}  p90 {x['p90']:.3f} "
              f"[{x['p90_lo']:.3f},{x['p90_hi']:.3f}]  theta {x['theta']:.3f}  rank {x['rank_lo']}-{x['rank_hi']}  "
              f"ptop10 {x.get('p_top10_pct')}  share {x['team_share_pct']}%  min {x['minutes']}")
    print("  raw top10 dropped:", board["raw_top10_dropped"], board["raw_top10_dropped_names"])
    print("  priors:", board["priors"])
    print("  pull at minutes (FW):", board["pull_at"])
    print("  credit rules:", {k: {kk: vv for kk, vv in v.items() if kk != "shift"} for k, v in cr.items() if k != "weights"})
    print("  repeatability:", {k: v for k, v in rep.items() if isinstance(v, dict)})
    print("  awards: exact", awards["exact"], "top3", awards["top3"], "top10", awards["top10"], "of", awards["cells_with_winner"],
          "eligible winners", awards["eligible_winners"], "median rank", awards["median_rank"],
          "chance", awards["chance_exact"], "chance top3", awards["chance_top3"], "G+A exact", awards["ga_exact"],
          "EP total exact", awards["ep_total_exact"], "ineligible", awards["ineligible"])
    for c in awards["grid"]:
        print(f"    {c['code']:<15} {c['season_label']}  pick {c['pick']:<24} winner {str(c['winner']):<24} rank {c.get('winner_rank')}  ga {c['ga_leader']}")
    print("  sca2 top:", [(x["player"], x["ep_sca2"], x["ep_sca2_lo"], x["ep_sca2_hi"], x["rank_lo"], x["rank_hi"], x["share_sca2_pct"]) for x in sca2["top"][:8]])
    print("  sca2 share top:", [(x["player"], x["share_sca2_pct"]) for x in sca2["top_share"][:5]])
    print("  efficiency:", {k: v for k, v in eff.items() if k not in ("top", "bottom")})
    print("  eff top:", [(x["player"], x["ep_per_inv"], x["lo"], x["hi"]) for x in eff["top"][:5]])
    print("  young:", [(x["player"], x["age_end"], x["theta"]) for x in young[:6]])
    print("  positions:", {p: [(x["player"], x["theta"]) for x in v[:3]] for p, v in positions.items()})
    print("  quality:", quality)
    print("  framework:", fw)


if __name__ == "__main__":
    main()
