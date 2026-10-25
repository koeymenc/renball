# Not All Goals Are Equal: A Time-Aware Expected-Points Model for Goal Valuation

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** May 2026

---

## Abstract

A goal's worth depends on the scoreline it changes and on when it comes. This study prices every goal from a team-minute model of expected final points: for each goal difference and 15-minute window, the average points won by teams that spent a minute in that state, estimated from 2,377,080 team-minutes in 13,206 matches across six top-flight leagues (2017-2018 to 2023-2024). A goal's value is the state it creates minus the state it ends, in the same window. The go-ahead goal from level is worth 0.733 expected points in the first 15 minutes and 1.507 in the last 15: **2.05× (95% CI 1.94–2.18)**. The ratio holds in every league (1.85× to 2.31×), on seasons the model never saw, and when the matches with missing own goals are put back (2.03×). Out of sample, the time-aware model predicts results better than a time-blind one (Brier score 0.481 vs 0.496 on 2022-2023 and 2023-2024). Level in the last 15 minutes, a goal for is worth 1.58× what a goal against costs. Player rankings by expected points collected are led by Messi, Salah, Lewandowski, Kane and Mbappé in a statistical tie. A *timing premium* (the value gained from when a player's goals came, scorelines held fixed) is clearly above zero for only 17 of 1,090 players, fewer than chance alone would produce.

---

## 1. Research Question

> How much is a goal worth, given the goal difference it changes and the minute it is scored, and does accounting for the minute change how we should read matches and players?

Four evaluable claims:

1. **Estimation:** the value of each state (goal difference × 15-minute window) can be estimated precisely, with intervals.
2. **The clock matters:** the same scoreline change is worth materially more late than early (headline: the go-ahead goal from level, last 15 vs first 15 minutes).
3. **Prediction:** a model that knows the minute predicts held-out results better than one that doesn't.
4. **Players:** whether any player's goals systematically arrive at more valuable moments than the average goal with the same scoreline change.

---

## 2. Data

**Sources:** FBref match pages, stored locally as one pickle per league (`match_data_final_<league>.pkl` in `RENBALL_MATCH_DATA_PATH`; files with `CHECK` in the name are ignored). Per match: the shot table (minute, team, scorer, outcome, SCA1 and SCA2 players), `match_details` (official score, home and away team names and IDs, date) and each side's player summary table (minutes and age per player).

**Leagues (6):** Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie. **Seasons (7):** 2017-2018 to 2023-2024.

**Coverage:**

| League | Matches | Loaded | No usable data | Own-goal affected |
|---|---:|---:|---:|---:|
| Premier League | 2,660 | 2,658 | 2 | 251 (9.4%) |
| La Liga | 2,660 | 2,658 | 2 | 182 (6.8%) |
| Serie A | 2,660 | 2,659 | 1 | 219 (8.2%) |
| Bundesliga | 2,142 | 2,140 | 2 | 168 (7.9%) |
| Ligue 1 | 2,492 | 2,484 | 8 | 198 (8.0%) |
| Eredivisie | 2,068 | 1,761 | 307 (14.8%) | 136 (7.7%) |

In all, 14,360 of 14,682 matches load; 322 do not (308 have no shot table, 14 were never stored). Almost all failures are in the Eredivisie, which is therefore under-represented.

**Units of analysis:** the *team-minute* for state values (each match contributes both sides × 90 minutes); the *goal* for goal values; the *player* (all matches in scope) for leaderboards.

**Cleaning and construction:**

1. **Teams and sides** come from `match_details` (home/away names and IDs); each goal's team is matched to a side by name, using each side's own shot table to resolve name variants. No goal is left unmatched.
2. **Minutes.** `"45+2"` → 47, `"90+3"` → 93 for the goal's bin; first-half stoppage goals fall in 30–45 and anything after 90 in 75–90. For the team-minute panel a goal counts at minute 45 (first-half stoppage) or 90 (after 90), and changes the state from the next minute on.
3. **Official scores and own goals.** The shot table contains no own goals. In **1,154 matches (8.0% of those loaded)** the score rebuilt from it is lower than FBref's official score: 1,202 goals in all are missing, and it is never higher. In those matches the running score is wrong from the missing goal on, and own-goal minutes are not in the data. They are **excluded from the value model** (13,206 matches remain), with the inclusive version as a sensitivity check (§4.6); their IDs are written to `data/og_affected_matches.csv` for a later backfill from FBref's match reports. Final results always use the official score.
4. **Player identity.** FBref's per-match age (`years-days`) gives each player's birth date. Players are keyed by cleaned name + birth date, so different players with the same name (45 names in scope) are kept apart; a name shared by several players is shown with a birth year (e.g. "Adama Traoré (b. 1996)").
5. **Credit.** A goal credits its scorer and its SCA1 (FBref's first shot-creating action), once per player per goal. On 4,059 goals (10.3%) the scorer is his own SCA1 and receives one credit, not two. 2,251 goals have no SCA1 recorded. In the role-specific dashboard tables (Goalscorer, Assist) each role is counted on its own.
6. **Minutes played** come from the player summary tables of the same matches as the goals, in all six leagues, so a player's EP and minutes cover exactly the same games.

---

## 3. Methodology

### 3.1 State space

Goal difference from a team's own side, in [−7, +7] (15 values), × six 15-minute windows (0–15, 15–30, 30–45, 45–60, 60–75, 75–90): 90 states, of which 76 occur in the data. Scoring takes a team from `gd` to `gd + 1`.

### 3.2 State values from team-minutes

For each match in the model sample and each side, the goal difference at the start of every minute t = 1…90 is reconstructed from the goal minutes. Each team-minute carries the side's final result. For state (gd, b):

$$
V(gd, b) \;=\; \frac{1}{N_{gd,b}} \sum_{\text{team-minutes in }(gd,b)} \big(3\cdot\mathbb{1}[\text{won}] + 1\cdot\mathbb{1}[\text{drew}]\big)
$$

with \(N_{gd,b}\) the number of team-minutes in that state, and win/draw/loss shares \(p_W, p_D, p_L\) alongside. The time-blind value \(U(gd)\) pools the six windows. Every minute counts (goalless spells and 0–0 draws included), so the table describes a team *in* that state, not a team at the moment a goal is scored. (A table sampled only at goal moments mixes leaders about to score again with leaders about to concede, and flattens the late +1 row.)

**Implementation:** `code/value_model.py` stores per-match counts C[match, gd, bin, W/D/L] (`panel_counts`); every value is a function of their sum (`values`).

### 3.3 Goal values

A goal from gd to gd + 1 in window b is worth

$$
v(gd \to gd{+}1,\, b) \;=\; V(gd{+}1, b) - V(gd, b)
$$

and the time-blind value is \(U(gd+1) - U(gd)\). Conceding from gd to gd − 1 costs \(V(gd, b) - V(gd-1, b)\), the value of the goal gd − 1 → gd. Two goals in the data fall in a cell the panel never saw (an extreme scoreline early) and take the time-blind value; goals beyond +7 are worth nothing.

### 3.4 Game state: upside and downside of the next goal

For a team leading by one, level, or trailing by one, the ratio of the value of scoring the next goal to the cost of conceding it, per window. Level: \(v(0\to1, b) \,/\, v(-1\to0, b)\). Leading by one: \(v(1\to2, b) \,/\, v(0\to1, b)\). Trailing by one: \(v(-1\to0, b)\,/\,v(-2\to-1, b)\). These are prices of outcomes; they do not measure what any tactical change does to the chances of scoring or conceding.

### 3.5 Uncertainty: bootstrap over matches

Every interval is a 95% interval (percentile method) from 1,000 bootstrap resamples of whole matches, drawn within each league (fixed seed, so a rebuild reproduces every number). Each resample re-estimates all state values, goal values, ratios and player totals. Resampling matches (not team-minutes or goals) respects that minutes within a match are not independent. A state seen in fewer than 30 matches is flagged *sparse* and shown faded.

### 3.6 Held-out calibration

The model is re-fitted on 2017-2018 to 2021-2022 only and used to predict the final result (win/draw/loss) of every team-minute in 2022-2023 and 2023-2024 from its state. Three predictions are scored with the three-outcome Brier score (mean over team-minutes of \(\sum_k (p_k - o_k)^2\), lower is better): the time-aware state probabilities, the time-blind ones (goal difference only), and the base rate (no score information). Unseen training states fall back to the time-blind row, then to the base rate. The interval on the time-aware improvement resamples held-out matches. Calibration of the prices: held-out team-minutes are grouped into bands of predicted EP (0.25 EP wide; bands with fewer than 500 team-minutes dropped) and compared with the points those teams then won.

### 3.7 Player boards

- **EP collected:** the sum of a player's credits at their time-aware values.
- **Timing premium:** for each credit, its time-aware value minus the average time-aware value of all goals with the same scoreline change; summed per player. It measures what a player gained from *when* his goals came, holding the scorelines fixed. (Raw time-aware minus time-blind EP is not used for this: most goals from level come early, when they are worth less than the time-blind average, so the raw difference drifts below zero with volume and penalises prolific players.) Players with at least 20 goal involvements.
- **EP per 90:** EP collected ÷ minutes played × 90, at least 900 minutes.
- **Intervals** for all three come from the same match bootstrap: each resample re-weights the player's matches and re-prices every goal. Under no real differences in timing, about one player in forty would show an interval wholly above zero by chance, and as many below.

### 3.8 Robustness

The headline ratio is recomputed (a) with the own-goal matches included, using official results and the shot-table scoreline; (b) on the training and held-out seasons separately; (c) in each league separately, with intervals from the within-league resamples. Player boards are recomputed from model-sample matches only.

### 3.9 Software

Python 3.12; `pandas`, `numpy`. Code: `code/matches.py` (extraction, cached per league under `data/.cache/`), `code/value_model.py`, `code/build.py` (everything else, incl. takeaways), `code/dashboard_files.py`. Output: `data/data.json`, `data/dashboard/` (manifest + one file per dataset and view), `data/og_affected_matches.csv`.

---

## 4. Results

> Every number here comes from `code/build.py` → `data/data.json` and is shown live on the analysis page.

### 4.1 State values

Expected final points by goal difference and window, with 95% intervals (team-minutes in 13,206 matches):

| GD | 0–15 | 15–30 | 30–45 | 45–60 | 60–75 | 75–90 | Time-blind |
|---|---:|---:|---:|---:|---:|---:|---:|
| +2 | 2.644 | 2.673 | 2.751 | 2.821 | 2.894 | 2.966 | 2.861 |
| +1 | 2.103 | 2.137 | 2.171 | 2.291 | 2.425 | 2.658 | 2.328 |
| 0 | 1.369 | 1.354 | 1.334 | 1.297 | 1.244 | 1.151 | 1.317 |
| −1 | 0.687 | 0.656 | 0.611 | 0.491 | 0.368 | 0.196 | 0.472 |
| −2 | 0.249 | 0.227 | 0.171 | 0.117 | 0.066 | 0.019 | 0.091 |

Intervals in the central rows are narrow (e.g. +1 in 75–90: 2.658, 95% CI 2.639–2.677). Being level is worth less as time runs out (1.369 → 1.151): a draw is a point, a late winner three.

### 4.2 Goal values

| Goal | 0–15 | 15–30 | 30–45 | 45–60 | 60–75 | 75–90 | Time-blind |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1→2 | 0.542 | 0.536 | 0.580 | 0.530 | 0.468 | 0.308 | 0.532 |
| 0→1 | 0.733 | 0.783 | 0.836 | 0.994 | 1.181 | 1.507 | 1.011 |
| −1→0 | 0.682 | 0.698 | 0.724 | 0.806 | 0.876 | 0.955 | 0.845 |
| −2→−1 | 0.438 | 0.429 | 0.440 | 0.374 | 0.302 | 0.177 | 0.380 |

The most valuable goal is the go-ahead goal from level in 75–90 (1.507 EP, 95% CI 1.487–1.527, 2,113 goals). Goals that stretch a lead or pull one back from two down lose value with the clock; goals from level or one down gain it.

### 4.3 Headline: the go-ahead goal from level

| Window | EP per goal | 95% CI | Goals |
|---|---:|---|---:|
| 0–15 | 0.733 | 0.690–0.775 | 4,005 |
| 15–30 | 0.783 | 0.751–0.816 | 3,240 |
| 30–45 | 0.836 | 0.806–0.864 | 2,755 |
| 45–60 | 0.994 | 0.966–1.021 | 2,198 |
| 60–75 | 1.181 | 1.155–1.206 | 1,760 |
| 75–90 | 1.507 | 1.487–1.527 | 2,113 |

- **Last 15 vs first 15:** 2.05× (95% CI 1.94–2.18).
- **Late equaliser** (−1→0 in 75–90): 0.955 EP (0.941–0.969), 1.30× an early opener (1.23–1.39).
- **Late second goal when 1–0 up** (1→2 in 75–90): 0.308 EP (0.288–0.328).

### 4.4 Game state

| Score | 0–15 | 15–30 | 30–45 | 45–60 | 60–75 | 75–90 |
|---|---:|---:|---:|---:|---:|---:|
| Leading by one | 0.74× | 0.68× | 0.69× | 0.53× | 0.40× | 0.20× |
| Level | 1.08× | 1.12× | 1.16× | 1.23× | 1.35× | 1.58× |
| Trailing by one | 1.56× | 1.63× | 1.65× | 2.15× | 2.90× | 5.39× |

Value of scoring the next goal ÷ cost of conceding it. Level in 75–90: a goal for is worth 1.51 EP, a goal against costs 0.96, ratio 1.58× (95% CI 1.56–1.60). A draw splits the points, so going ahead gains more than falling behind costs, and increasingly so as time runs out.

### 4.5 Where the expected points are delivered

Every goal in the model sample at its own value, by window: 3,289.3 EP from 4,596 goals in 0–15 and 5,400.8 EP from 8,238 goals in 75–90: 1.64× (95% CI 1.54–1.76). The average late goal is not worth more (0.656 EP per goal vs 0.716): more goals are scored late, and the ones that break a level game are worth twice as much, but many late goals come in decided games.

### 4.6 Held-out calibration

Fit on 2017-2018 to 2021-2022; predict 3,838 matches (690,840 team-minutes) in 2022-2023 and 2023-2024.

| Window | Time-aware | Time-blind | No score info |
|---|---:|---:|---:|
| 0–15 | 0.6413 | 0.6565 | 0.6574 |
| 15–30 | 0.5947 | 0.6025 | 0.6574 |
| 30–45 | 0.5455 | 0.5492 | 0.6574 |
| 45–60 | 0.4683 | 0.4697 | 0.6574 |
| 60–75 | 0.3785 | 0.3905 | 0.6574 |
| 75–90 | 0.2576 | 0.3076 | 0.6574 |
| **All** | **0.481** | 0.496 | 0.6574 |

Improvement of the time-aware over the time-blind model: 0.015 (95% CI 0.0135–0.0166); skill relative to the base rate: 26.8% (25.7%–28.0%). The prices are calibrated out of sample: across EP bands, predicted and realised points differ by at most 0.05.

### 4.7 Robustness of the headline

| Version | Matches | Opener 75–90 | Opener 0–15 | Ratio | 95% CI |
|---|---:|---:|---:|---:|---|
| Primary | 13,206 | 1.507 | 0.733 | 2.05× | 1.94–2.18 |
| Own-goal matches included | 14,360 | 1.437 | 0.708 | 2.03× | n/a |
| Fit on 2017-2018 to 2021-2022 | 9,368 | 1.524 | 0.748 | 2.04× | n/a |
| Fit on 2022-2023 and 2023-2024 | 3,838 | 1.463 | 0.700 | 2.09× | n/a |
| Premier League | 2,407 | 1.515 | 0.718 | 2.11× | 1.82–2.47 |
| La Liga | 2,476 | 1.516 | 0.655 | 2.31× | 1.98–2.77 |
| Serie A | 2,440 | 1.491 | 0.786 | 1.90× | 1.67–2.21 |
| Bundesliga | 1,972 | 1.500 | 0.811 | 1.85× | 1.65–2.12 |
| Ligue 1 | 2,286 | 1.527 | 0.723 | 2.11× | 1.85–2.47 |
| Eredivisie | 1,625 | 1.479 | 0.700 | 2.11× | 1.78–2.59 |

**Excluded vs kept matches.** The own-goal matches average 3.82 goals against 2.74 in the kept matches (a missing own goal means at least one extra goal) and have fewer draws (19.3% vs 25.4%; home wins 48.7% vs 43.5%, away wins 32.0% vs 31.1%). Excluding them tilts the sample slightly towards tighter games; including them moves the headline from 2.05× to 2.03×. League differences within the 1.85×–2.31× range are not tested.

### 4.8 Players

**EP collected (goals + SCA1 credits, once per player per goal):**

| # | Player | Team | Goals | Assists | EP | 95% CI |
|--:|---|---|--:|--:|--:|---|
| 1 | Lionel Messi | Barcelona | 145 | 88 | 139.74 | 115.96–167.98 |
| 2 | Mohamed Salah | Liverpool | 155 | 72 | 138.73 | 115.68–164.76 |
| 3 | Robert Lewandowski | Bayern Munich | 203 | 47 | 138.38 | 115.43–166.20 |
| 4 | Harry Kane | Tottenham | 171 | 51 | 138.20 | 115.37–164.61 |
| 5 | Kylian Mbappé | Paris S-G | 175 | 71 | 137.08 | 111.69–163.79 |
| 6 | Ciro Immobile | Lazio | 146 | 39 | 115.92 | 94.04–139.38 |
| 7 | Wissam Ben Yedder | Monaco | 125 | 45 | 108.76 | 87.06–131.77 |
| 8 | Iago Aspas | Celta Vigo | 109 | 51 | 108.74 | 87.58–130.85 |
| 9 | Karim Benzema | Real Madrid | 116 | 50 | 107.50 | 84.97–130.74 |
| 10 | Cristiano Ronaldo | Juventus | 126 | 31 | 105.30 | 82.28–129.55 |

The top five are within 2.66 EP of each other with overlapping intervals: a statistical tie. Recomputed from model-sample matches only, the same ten names make the top ten.

**Timing premium (players with 20+ goal involvements):**

| # | Player | Team | Involvements | Premium | 95% CI |
|--:|---|---|--:|--:|---|
| 1 | Adama Traoré (b. 1996) | Wolves | 36 | +4.70 | +1.50 to +8.31 |
| 2 | Edin Džeko | Roma | 106 | +4.63 | +1.01 to +8.77 |
| 3 | Ángel Rodríguez | Getafe | 54 | +4.54 | +0.88 to +8.34 |
| 4 | Achraf Hakimi | Paris S-G | 69 | +4.52 | +0.82 to +8.34 |
| 5 | Cristian Tello | Betis | 34 | +4.16 | +1.11 to +7.76 |
| 6 | Mário Rui | Napoli | 28 | +3.95 | +1.19 to +7.30 |
| 7 | Mason Greenwood | Manchester Utd | 44 | +3.36 | +0.11 to +6.93 |
| 8 | Sasa Kalajdzic | Stuttgart | 36 | +3.34 | +0.90 to +6.41 |
| 9 | Jorge Molina | Getafe | 64 | +3.29 | +0.41 to +6.56 |
| 10 | Felipe Caicedo | Lazio | 40 | +3.10 | −0.22 to +6.55 |

Of 1,090 eligible players, **17** have an interval wholly above zero, fewer than the ~27 expected by chance alone, and 88 wholly below. The negative group's involvements come earlier than average (33.8% in the first 30 minutes vs 27.1% for all involvements), when goals are cheaper. The top ten's intervals overlap almost completely; recomputed from model-sample matches only, 8 of the ten remain. The premium describes a record; whether it repeats season to season is not tested.

**EP per 90 (at least 900 minutes; 4,300 players):**

| # | Player | Team | Minutes | EP per 90 | 95% CI |
|--:|---|---|--:|--:|---|
| 1 | Victor Boniface | Leverkusen | 1,546 | 0.804 | 0.525–1.073 |
| 2 | Cole Palmer | Chelsea | 3,111 | 0.765 | 0.540–0.996 |
| 3 | Lionel Messi | Barcelona | 16,516 | 0.761 | 0.668–0.867 |
| 4 | Kylian Mbappé | Paris S-G | 16,403 | 0.752 | 0.654–0.850 |
| 5 | Clinton N'Jie | Marseille | 1,238 | 0.750 | 0.303–1.304 |
| 6 | Robin van Persie | Feyenoord | 1,904 | 0.738 | 0.490–1.008 |
| 7 | Artem Dovbyk | Girona | 2,587 | 0.726 | 0.442–1.034 |
| 8 | Erling Haaland | Dortmund | 10,702 | 0.718 | 0.595–0.848 |
| 9 | Cristiano Ronaldo | Juventus | 13,704 | 0.692 | 0.582–0.804 |
| 10 | Neymar | Paris S-G | 9,354 | 0.690 | 0.566–0.801 |

Four of the top ten played under 3,000 minutes, and their intervals are the widest; a minutes filter does not stop short hot streaks from topping a rate board. Project 03 ranks per-90 rates with shrinkage towards the average.

---

## 5. Practical takeaways

### Evidence labels

- **Strong**: large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a pre-stated equivalence margin); survives the main controls; holds across leagues or seasons.
- **Moderate**: consistent direction and plausible size, with one gap: the interval touches zero, a single method or sample, or only partial replication.
- **Exploratory**: small samples, an interval that comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.

### Who should care

- **Managers (match-day decisions): Moderate.** Level after 75': a goal for is worth 1.51 EP, a goal against costs 0.96; the upside is 1.58× the downside (95% CI 1.56–1.60, every league). And 1–0 up after 75': conceding costs 1.51 EP, a second goal adds 0.31. The values themselves would rate Strong; the label is Moderate because the decision they suggest (take more risk when level late, less when ahead) depends on what a tactical change does to the chances of scoring and conceding, which these data don't measure.
- **Coaches (training & tactics): Exploratory.** The last 15 minutes deliver 1.64× the expected points of the first 15 (95% CI 1.54–1.76). Whether training time should follow is a question this study raises, not one it answers.
- **Clubs (recruitment): Moderate.** Don't pay for "clutch": only 17 of 1,090 players scored at clearly better-than-average times, fewer than chance (~27). One method on one dataset, and season-to-season repeatability is not tested, hence Moderate.
- **Agents: no defensible claim** from this study.

---

## 6. Limitations

1. **Prices, not causes.** A goal's value is the gap between two states measured on what teams in those states went on to do. It does not separate the goal from concurrent events (red cards, substitutions, tactical changes) that also shape the result.
2. **No team strength.** A one-goal lead is priced the same for a favourite and an underdog. Strong teams lead more often and hold leads better, so part of what the table attributes to the clock belongs to who is leading. A team-strength version is in the backlog.
3. **Own goals missing.** 1,154 matches are excluded from the value model because the shot table lacks their own goals; the inclusive version changes the headline from 2.05× to 2.03×. Players' goals in those matches still count on the boards, priced on the shot-table scoreline.
4. **Eredivisie coverage.** 307 of 2,068 Eredivisie matches have no usable data.
5. **Every goal counts as one.** No expected-goals weighting: a tap-in and a long-range strike move the score equally.
6. **"Assist" is SCA1.** FBref's first shot-creating action also counts dribbles, fouls drawn and the scorer's own actions; 2,251 goals have no SCA1. SCA2 is not credited here (Project 03 does).
7. **Fifteen-minute windows.** A 76th- and a 94th-minute goal share a window; stoppage time folds into minutes 45 and 90. League differences in the values are not tested.
8. **Players.** Timing premiums and per-90 rates are not tested for repeatability; per-90 rates are not shrunk. Identity relies on name + birth date from FBref's age field; a player whose name is spelled differently across matches would be split.

---

## 7. Conclusion

The clock changes what a goal is worth, and by a lot: the same go-ahead goal from level is worth 2.05× as much in the last 15 minutes as in the first, in every league, in seasons the model never saw, and whether or not the own-goal matches are included. The value table predicts held-out results better than a time-blind one and its prices are calibrated, which makes it usable for game management: level late, a goal for is worth 1.58× what a goal against costs. It does not single out "clutch" players: once goals are compared with the same scorelines at average times, almost nobody's timing stands out from chance.

---

## References

1. FBref: *Match reports: shot tables, match details, player summaries.* https://fbref.com
2. Efron, B. & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap.* Chapman & Hall.
3. Brier, G. W. (1950). *Verification of forecasts expressed in terms of probability.* Monthly Weather Review.
4. Interactive dashboard: [`dashboard.html`](dashboard.html) · editorial page: [`analysis.html`](analysis.html) · code: `code/`.

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Source code: [`code/build.py`](code/build.py).*
