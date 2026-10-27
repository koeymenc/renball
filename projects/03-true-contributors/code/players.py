"""
players.py — who was involved in each goal, how much each involvement is worth
==============================================================================

Identity: name + birth date (FBref's per-match age is "years-days", so the
birth date follows from the match date). Birth dates within 3 days of each
other are one person; one name with birth dates further apart is two people
(namesakes), shown as "Name (b. YYYY)".

Credits. Every goal has up to three recorded roles: the scorer, SCA1 (the
action right before the shot, usually the assist) and SCA2 (the action
before that). Two tables come out of a goal:

  roles    one row per (goal, role): the role-by-role view. A player who
           both creates and scores a goal appears twice. Used for the SCA2
           board and the role split, and as the old credit rule
           (sensitivity check).
  inv      one row per (goal, player): a player involved in a goal gets one
           credit at the goal's full value, whatever his roles. Used for
           every per-90 board.

Each credit is priced at the goal's time-aware value from Project 02's
team-minute model: V(gd + 1, bin) − V(gd, bin).
"""
from __future__ import annotations

import unicodedata
from datetime import date

import numpy as np
import pandas as pd

ROLES = (("goal", "goalscorer", "goalscorer_born"),
         ("sca1", "sca1_creator", "sca1_born"),
         ("sca2", "sca2_creator", "sca2_born"))
ROLE_ORDER = {"goal": 0, "sca1": 1, "sca2": 2}

# FBref position (first listed) -> GK / DF / MF / FW
POS_BUCKETS = {
    "GK": "GK",
    "DF": "DF", "CB": "DF", "LB": "DF", "RB": "DF", "WB": "DF", "LWB": "DF", "RWB": "DF", "FB": "DF",
    "MF": "MF", "CM": "MF", "DM": "MF", "AM": "MF", "LM": "MF", "RM": "MF",
    "FW": "FW", "LW": "FW", "RW": "FW", "CF": "FW", "ST": "FW",
}
POS_LABELS = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Forward"}


def norm_name(s: str) -> str:
    """Accent-free lower-case name for matching against award lists."""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def identities(goals: pd.DataFrame, apps: pd.DataFrame) -> tuple[dict, dict]:
    """(name, born) -> canonical key; namesakes = one name, birth dates more than 3 days apart."""
    parts = [apps[["player", "born"]]]
    for _, col, born in ROLES:
        parts.append(goals[[col, born]].set_axis(["player", "born"], axis=1))
    pairs = pd.concat(parts).dropna(subset=["player"]).drop_duplicates()
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
        if len(clusters) == 1:
            canon[(name, None)] = (name, clusters[0][0].date().isoformat())
        else:                                   # no birth date anywhere, or namesakes
            canon[(name, None)] = (name, None)
            if clusters:
                people[(name, None)] = len(clusters)
    return canon, people


def keyof(canon: dict, names, borns) -> list:
    return [canon.get((p, b), canon.get((p, None), (p, b))) for p, b in zip(names, borns)]


def display(key: tuple, people: dict) -> str:
    name, born = key
    return f"{name} (b. {born[:4]})" if people.get(key, 1) > 1 and born else name


def credit_tables(goals: pd.DataFrame, canon: dict, people: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(roles, inv): role-by-role credits and one-credit-per-player-per-goal involvements."""
    base = ["goal_uid", "match_id", "league", "season", "side", "scoring_team", "gd_before", "minute_bin", "e", "e_u"]
    parts = []
    for role, col, born in ROLES:
        part = goals[base + [col, born]].set_axis(base + ["player", "born"], axis=1).assign(role=role)
        parts.append(part)
    roles = pd.concat(parts, ignore_index=True).dropna(subset=["player"])
    roles = roles[roles["player"].astype(str).str.strip().str.lower() != "unknown"].copy()
    roles["key"] = keyof(canon, roles["player"], roles["born"])
    roles["rank"] = roles["role"].map(ROLE_ORDER)
    # roles held by the same player in the same goal (e.g. a one-two) stay separate rows here
    inv = (roles.sort_values(["goal_uid", "rank"])
                .drop_duplicates(["goal_uid", "key"], keep="first")
                .reset_index(drop=True))
    for df in (roles, inv):
        df["contributor"] = [display(k, people) for k in df["key"]]
    return roles.reset_index(drop=True), inv


def weighted_credit(roles: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Each goal's value split over its recorded roles by `weights`, renormalised over the roles
    that were recorded (a goal with no SCA2 splits between scorer and SCA1). Returns the weighted
    value of every row of `roles`."""
    w = roles["role"].map(weights)
    total = w.groupby(roles["goal_uid"]).transform("sum")
    return roles["e"] * w / total


def positions(apps: pd.DataFrame) -> pd.Series:
    """Minutes-weighted modal position bucket per player key."""
    a = apps[apps["minutes"] > 0].copy()
    a["bucket"] = a["pos"].fillna("").str.split(",").str[0].str.strip().str.upper().map(POS_BUCKETS)
    a = a.dropna(subset=["bucket"])
    m = a.groupby(["key", "bucket"])["minutes"].sum().reset_index()
    return m.sort_values("minutes", ascending=False).drop_duplicates("key").set_index("key")["bucket"]


def age_on(born, day: date) -> float | None:
    if not isinstance(born, str) or not born:
        return None
    b = date.fromisoformat(born)
    return (day - b).days / 365.25


def modal(df: pd.DataFrame, by: str, col: str, weight: str) -> pd.Series:
    """Per `by`, the value of `col` with the most `weight` (team or league a player played most for)."""
    m = df.groupby([by, col])[weight].sum().reset_index()
    return m.sort_values(weight, ascending=False).drop_duplicates(by).set_index(by)[col]


def bootstrap_rates(keys: pd.Index, credit_key, credit_match: np.ndarray, credit_gi: np.ndarray,
                    credit_bi: np.ndarray, app_key, app_match: np.ndarray, app_min: np.ndarray,
                    W: np.ndarray, GT: np.ndarray, GU: np.ndarray,
                    goal_gi: np.ndarray | None = None, goal_bi: np.ndarray | None = None,
                    goal_match: np.ndarray | None = None) -> dict:
    """Bootstrap over matches (the value model's own resample weights): every resample re-prices
    each credit with that resample's goal values and reweights the matches it came from.
    Returns per-key samples of EP, minutes and, if goal arrays are given, the timing premium
    (credit value minus the resample's average value of goals with the same scoreline change)."""
    n_p, n_b = len(keys), len(W)
    cp = keys.get_indexer(credit_key)
    ap = keys.get_indexer(app_key)
    ok_a = ap >= 0
    ap, app_match, app_min = ap[ok_a], app_match[ok_a], app_min[ok_a]
    ep = np.empty((n_b, n_p))
    mins = np.empty((n_b, n_p))
    prem = np.empty((n_b, n_p)) if goal_gi is not None else None
    n_gd = GT.shape[1]
    for k in range(n_b):
        gu = np.nan_to_num(GU[k])
        gt = np.nan_to_num(np.where(np.isnan(GT[k]), GU[k][:, None], GT[k]))
        e = gt[credit_gi, credit_bi]
        w = W[k][credit_match].astype(float)
        ep[k] = np.bincount(cp, w * e, n_p)
        mins[k] = np.bincount(ap, W[k][app_match] * app_min, n_p)
        if prem is not None:
            wg = W[k][goal_match].astype(float)
            eg = gt[goal_gi, goal_bi]
            mean_t = np.bincount(goal_gi, wg * eg, n_gd) / np.maximum(np.bincount(goal_gi, wg, n_gd), 1e-9)
            prem[k] = np.bincount(cp, w * (e - mean_t[credit_gi]), n_p)
    return {"ep": ep, "minutes": mins, "premium": prem}
