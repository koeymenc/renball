# Not All Goals Are Equal: A Time-Aware Expected-Points Framework for Goal Valuation

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** May 2026

---

## Abstract

The standard scoreboard treats every goal as one unit of contribution, indifferent to the gamestate it altered or the minute it landed. A consolation goal at 4–0 down is filed under the same column as a 90th-minute equaliser. This project builds a time-aware expected-points (EP) framework that prices every goal by both dimensions: the `(gd_before, minute_bin)` pre-goal state it transitioned out of and the `(gd_after, minute_bin)` post-goal state it transitioned into. Across **39,381 goals** in six top-flight European leagues over seven seasons, the time-aware model produces a substantively different player ranking from the time-blind baseline. The most valuable single transition observed is the **0→1 in the 75–90 minute bin (1.68 expected points collected, 2.14× the same transition in 0–15 minutes)**. Mário Rui (Napoli, 28 G+A) is the model's biggest gainer at **+3.43 ΔEP** between the timed and untimed rankings — a late-equaliser specialist the time-blind model materially underrates.

---

## 1. Research Question

> Does conditioning a goal's expected-points value on the minute it was scored — in addition to the goal-difference transition it produced — yield a materially different ranking of players from the time-blind baseline, and does that difference cleanly identify players whose contributions cluster in high-leverage minutes?

This is not a hypothesis test. The framework rests on two evaluable claims:

1. **Estimation:** the empirical state-value table `EP(gd, minute_bin)` is well-conditioned given the sample size in each cell.
2. **Interpretability:** the timed-vs-untimed delta on the player leaderboards reshuffles in directions a domain expert would predict (late equalisers ↑, garbage-time goals ↓).

Both are addressed in §4.

---

## 2. Data

**Sources:** Per-match shot-event tables, FBref-derived, consolidated into one pickle per league. Files named `match_data_final_<league>.pkl` in `RENBALL_MATCH_DATA_PATH`. Files containing `CHECK` in the basename are excluded.

**Leagues (6):** Premier League, Serie A, Bundesliga, La Liga, Ligue 1, Eredivisie.

**Seasons (7):** 2017-2018 through 2023-2024.

**Sample:** 39,381 goal events across the 6 × 7 league-season cells.

**Per-event variables used:**

| Field | Source column (after `_normalize_cols`) | Notes |
|---|---|---|
| Scoring team | `…__Squad` | Disambiguated against the inferred home/away pair |
| Outcome | `…__Outcome` | Filtered to `"goal"` |
| Goalscorer | `…__Player` | Cleaned by `_clean_player_name` (strips `"(pen)"` etc.) |
| SCA1 (assist) | `SCA 1__Player` | Same cleaning |
| Minute (raw) | `…__Minute` | May include stoppage suffix `45+1`, `90+3` |

**Cleaning decisions:**

1. Drop matches with `error == "Failed to retrieve data after repeated attempts."`
2. Drop matches where the shot table (`shots.shots_all`) is missing or empty
3. Drop goal events where the scoring team cannot be matched to the inferred home/away team pair (rare; ~0.1% of events)
4. **Parse minute strings:** `"45+1"` → 46, `"90+3"` → 93. **Stoppage-time rules:** any `"45+X"` falls in the `30-45` bin; any `"90+X"` (or `minute > 90`) falls in the `75-90` bin
5. Goal events with unparseable minutes are assigned to an `unknown` bin and excluded from all timed analyses
6. The editorial leaderboards drop `"Unknown"` contributors — FBref shot rows where the goalscorer/SCA1 string couldn't be parsed (mostly own goals and fragmented entries). They aggregate to a fake "player" who would otherwise top the time-aware leaderboard with ~2,250 events. The Tabulator dashboard retains them for transparency.

---

## 3. Methodology

### 3.1 State space

- **Goal differences (15 states):** integer in `[−7, +7]` from the scoring team's perspective
- **Minute bins (6 states):** `0-15`, `15-30`, `30-45`, `45-60`, `60-75`, `75-90`
- **Pre-goal state space size:** 15 × 6 = **90 theoretical states; 82 observed empirically** (8 extreme `(gd, bin)` combinations had no events)
- **One-step transitions kept:** `{(gd, gd+1) for gd in [−7, +7]}` (15 transitions, scoring team's perspective)

### 3.2 Time-bin rationale

A continuous-time model (minute-by-minute) would over-fit at the seam minutes 45 and 90, where stoppage muddies the assignment. 15-minute bins are **coarse enough** to keep each cell well-populated (median bin n ≫ 1,000 in the central GD rows) and **fine enough** to detect the late-game value premium — the headline result is that the 0–15 vs 75–90 difference for 0→1 is 2.14×, which a 2-bin (early/late) cut would still surface but more granular phases (e.g. how 30–45 differs from 45–60) would not.

### 3.3 State value function (`EP(state)`)

For each pre-goal state `(gd, minute_bin)`:

1. **Symmetric expansion of events.** Each goal event in the dataset produces two pre-goal-state rows: the scoring team gets a row with `(gd_before, minute_bin)`, the conceding team gets a row with `(−gd_before, minute_bin)`. Each row carries the **owning team's** final result — scorer rows use the scoring team's `final_points`, conceder rows use the conceder's (W↔L / 3↔0 flip applied; draws stay D / 1 point). This is critical: without the flip, both rows would carry the scoring team's outcome and the table would alias the two sides together, so `EP(gd=+7)` and `EP(gd=−7)` would come out equal instead of mirror images.
2. **Empirical distribution of final results.** Group by `(gd, minute_bin)`, compute `pW`, `pD`, `pL` as the value-counts normalised across that cell's rows.
3. **Expected final points:** `EP(gd, minute_bin) = 3·pW + 1·pD`. Implementation uses the mean of `final_points` over the group, which is mathematically identical and numerically more stable.

The time-agnostic state value `EP_untimed(gd)` is computed identically except the grouping drops `minute_bin`.

The state-value table on the editorial page shows `EP(gd, minute_bin)` for `gd ∈ [−4, +4]` (the populated rows). Numerically the table runs from ≈ 0 along the bottom-most row (team trailing badly with little time left) up to ≈ 3 along the top-most (team leading comfortably late), with the level-score row `gd = 0` settling near the long-run home/away mean of ~1.5 expected points.

### 3.4 Goal value (EP credit per event)

For a goal event producing transition `gd_before → gd_after` in minute bin `b` (scoring team's perspective):

- **Timed credit:** `EP(gd_after, b) − EP(gd_before, b)`
- **Untimed credit:** `EP_untimed(gd_after) − EP_untimed(gd_before)`

The conceding team gets the negation of the same number. Only one-step transitions in the `[−7, +7]` GD range are retained; multi-step transitions (impossible in football without intervening events) and out-of-range states are dropped.

The full value map `val_map_timed[(gd_before, gd_after, b)] → ep_collected` and its untimed counterpart `val_map_untimed[(gd_before, gd_after)] → ep_collected` are the canonical lookup tables used downstream.

### 3.5 Attribution

Goals are credited to three different roles, producing three parallel contributor tables:

- **`Goalscorer`** — credit to the player who scored
- **`Assist`** — credit to the FBref SCA1 (first shot-creating action) for that shot
- **`Goals+Assists`** — additive pooling of both, the editorial-page default

Each table is built per `(scoring_team, contributor)` for every league-season, then rolled up into four views:

| View | Aggregation |
|---|---|
| `Per League & Season` | Raw per-season tables (42 sub-tables = 6 leagues × 7 seasons) |
| `Totals by League` | Sum across seasons within a league |
| `Totals by Season` | Sum across leagues within a season |
| `All` | Sum across both axes |

The editorial-page leaderboards pool further to one row per `contributor`, picking the team where the player has the most goals_involved as the `primary_team` label. The Tabulator dashboard exposes the per-`(scoring_team, contributor)` rows for users who want to inspect transfers and joint affiliations.

Each contributor row also stores transition-resolved breakdowns: `cnt_<gd_before>_to_<gd_after>` for every kept transition, `cnt_bin_X` per time bin, and `ep_bin_X` per time bin (the slice of `exp_points_collected_timed` that came from goals in bin X).

### 3.6 Per-90 normalisation

Total EP rewards volume of involvement; **EP per 90 minutes** rewards rate. Total minutes played per player are pooled across all leagues and seasons in scope from the per-match player tables (FBref `ROWS_DICTS_SUMMARY` inside `FULL_DICT_ROWS.pkl`, top-5 leagues only — Eredivisie is not in this source and Eredivisie-only players are excluded from the per-90 leaderboard). For each pooled contributor row the build computes:

```
ep_per_90 = (exp_points_collected_timed / minutes_played) × 90
```

The editorial-page leaderboard applies a `minutes_played ≥ 900` filter (≈ ten full matches) to keep the ranking meaningful. The Tabulator dashboard surfaces `minutes_played` and `ep_per_90` as additional columns on every Goalscorer / Assist / Goals+Assists view; sorting by `ep_per_90` with the smart filter (e.g. `>0.4`) lets the reader apply their own threshold.

### 3.7 Pooled vs per-league treatment

The editorial page (`analysis.html`) uses pooled value functions — a single `EP(gd, minute_bin)` table built from all six leagues combined. The Tabulator dashboard (`dashboard.html`) exposes both pooled and per-league state-value and transition tables. Per-league tables share most of the qualitative features of the pooled table (the late equaliser ranks high in every league) but vary in magnitude at the extremes — a function of sample size more than league effect. The pooled choice for the editorial page is deliberate: the headline narrative is about the universal shape of the value function, not league-specific calibration.

### 3.8 Software stack

- Python 3.12 (project venv at repo root)
- `pandas` — data wrangling, group-by aggregation
- `numpy` — numeric primitives
- `openpyxl` — Excel sheet writing (local-only, not committed)
- Output: `data/data.json` (editorial payload) and `data/dashboard/` (18 per-`(dataset, view)` JSONs + manifest, sparse-encoded, each ≤ 4 MB)

---

## 4. Results

> All numbers in this section come from `code/build.py` → `data/data.json` and are surfaced live in the editorial page.

### 4.1 Headline numbers

| Metric | Value |
|---|---:|
| Total goal events | 39,381 |
| Modelled `(gd, minute_bin)` states | 82 of 90 |
| Best transition (most EP collected per event) | **0→1 @ 75–90: 1.68 EP** |
| Worst observed transition | −2→−1 @ 0–15: 0.00 EP (n=1) |
| Early-vs-late opener ratio | **2.14×** (1.68 / 0.79) |

### 4.2 0→1 by minute bin (the cleanest single-transition story)

| Bin | EP collected | n |
|---|---:|---:|
| 0–15 | 0.79 | 4,359 |
| 15–30 | 0.74 | 3,539 |
| 30–45 | 0.84 | 2,998 |
| 45–60 | 1.05 | 2,367 |
| 60–75 | 1.22 | 1,934 |
| 75–90 | **1.68** | 2,300 |

### 4.3 Top 10 EP collectors (Goals + Assists, pooled)

| # | Player | Primary team | G+A | EP collected (timed) |
|--:|---|---|--:|--:|
| 1 | Lionel Messi | Barcelona | 267 | 157.75 |
| 2 | Mohamed Salah | Liverpool | 251 | 154.78 |
| 3 | Kylian Mbappé | Paris S-G | 274 | 154.53 |
| 4 | Harry Kane | Tottenham | 240 | 150.72 |
| 5 | Robert Lewandowski | Bayern Munich | 270 | 149.10 |
| 6 | Ciro Immobile | Lazio | 208 | 128.34 |
| 7 | Iago Aspas | Celta Vigo | 179 | 120.56 |
| 8 | Cristiano Ronaldo | Juventus | 174 | 119.25 |
| 9 | Wissam Ben Yedder | Monaco | 182 | 116.41 |
| 10 | Karim Benzema | Real Madrid | 174 | 110.76 |

### 4.4 Top 10 timed upgrades (largest positive ΔEP, min 5 G+A)

| # | Player | Primary team | G+A | ΔEP (timed − untimed) |
|--:|---|---|--:|--:|
| 1 | **Mário Rui** | **Napoli** | 28 | **+3.43** |
| 2 | Evann Guessand | Nice | 19 | +3.34 |
| 3 | Cristian Tello | Betis | 36 | +2.82 |
| 4 | Adama Traoré | Wolves | 43 | +2.69 |
| 5 | Youssoufa Moukoko | Dortmund | 22 | +2.58 |
| 6 | Viktor Kovalenko | Spezia | 7 | +2.53 |
| 7 | Sasa Kalajdzic | Stuttgart | 37 | +2.50 |
| 8 | Mario Hermoso | Atlético Madrid | 20 | +2.33 |
| 9 | Leo Dubois | Lyon | 26 | +2.27 |
| 10 | Lee Kang-in | Mallorca | 31 | +2.20 |

The upgrade leaderboard reads as a domain expert would predict: a cluster of defenders and super-subs whose goal records are dominated by late, score-tied moments the time-blind model materially underrates.

---

## 5. Limitations

1. **No expected-goal weighting.** Every goal is treated as 1.0 — a 2-yard tap-in and a 30-yard volley contribute identically. An xG-weighted version would price by chance creation rather than chance conversion.
2. **Penalties and own goals are not separated.** Penalty goals trigger the same transition value as any other; own goals are credited to the scoring team and (when present) the SCA1, even when the actual scorer was an opposition defender. Both effects would be cleaned in a v4.
3. **Assist credit caps at SCA1.** FBref's SCA2 is recorded but unused. Build-up sequences distribute credit further upstream than the framework captures.
4. **Observational, not causal.** The state-value function is computed empirically against final results. It is a value table, not a causal model — it does not isolate the goal's effect from concurrent factors (red cards, substitutions, fatigue) that also influence the final outcome. The "value of a goal" is "the EP gap between the two states the goal connects" — readers should not interpret it as "the EP this goal added," which would require a counterfactual the data does not provide.
5. **Pooled value function across leagues and seasons.** The editorial-page rankings use the pooled values. Differences between, say, Eredivisie defensive trends and Premier League ones would mean a "0→1 at minute 80" goal carries slightly different empirical EP in each league. The dashboard surfaces league-specific tables for users who want to inspect this.
6. **Stoppage-time goals fold into the 75–90 bin.** A 95th-minute goal and a 78th-minute goal contribute to the same cell. A finer split would separate them but at the cost of sample size at the extremes.
7. **Player attribution does not track transfers within a season.** A player who scored 10 goals at one club and 5 at another in the same season appears as one row per `(team, player)` in the raw tables. The editorial leaderboards pool further to one row per player by picking the primary team; this loses the transfer signal that the dashboard retains.
8. **The model rewards proximity to the threshold, not the goal itself.** A late equaliser is worth nearly a full point because the team it credits was about to win zero. A goal valuation framework grounded in counterfactual reasoning (e.g. permutation tests against alternative goal-minute distributions for the same player) would distinguish the player's contribution from the situation's leverage. Future work.

---

## 6. References

- **Source data:** FBref ([fbref.com](https://fbref.com)). Match shot tables consolidated locally into `match_data_final_<league>.pkl`.
- **Interactive dashboard:** [`dashboard.html`](dashboard.html) in this project folder
- **Editorial summary:** [`analysis.html`](analysis.html) in this project folder
- **Project page:** [renball.com/projects/02-points-by-gamestate/](https://renball.com/projects/02-points-by-gamestate/)
- **Source code:** `code/` directory — `config.py`, `extraction.py`, `analysis.py`, `dashboard.py`, `main.py`, `build.py`
