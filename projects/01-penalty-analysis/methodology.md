# Should the Fouled Player Take the Penalty Himself? — Conversion After a Goalkeeper Foul on the Taker

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** May 2026

---

## Abstract

When a goalkeeper fouls a player in the box, the fouled player frequently takes the resulting penalty himself. The practical question for the bench is whether he should — the just-fouled player is theoretically jarred and agitated, the goalkeeper across from him locked in. This study isolates that exact decision point across the top 5 European leagues, linking every penalty to its own taker, fouled player and conceder (treatment n = 79 penalties), and compares its conversion rate against every other linked penalty (control n = 3,456) using a one-tailed two-proportion z-test. The point estimate moves in the predicted direction (75.95% vs 78.96%, a 3.01 percentage-point drop) but the difference is not statistically detectable at α = 0.05 (z = −0.65, p = 0.258 one-tailed); the 95% interval for the difference runs from −13.6 to +5.2 pp. The conclusion is constrained by power: with 79 treatment penalties the design only reliably detects a drop of about 12.6 pp or more.

---

## 1. Research Question

> When a goalkeeper fouls a player to give away a penalty, should that fouled player take the penalty himself, or should the team hand the ball to a designated specialist? Equivalently: does conversion drop when the fouled player takes the kick, relative to all other penalties?

### Hypotheses

- **H₀:** conversion_treatment = conversion_control
- **H₁:** conversion_treatment < conversion_control &nbsp;&nbsp; *(one-tailed)*

### Why one-tailed

The theory underpinning the test is directional. The taker has just been fouled — typically a body collision that left them on the ground — and is presumed physically jarred and emotionally agitated. The goalkeeper, having committed the foul that elevated their save into a high-leverage situation, is presumed maximally focused. Both mechanisms point the same way: conversion *down*. A two-tailed test would split α between an upward effect (which the theory does not predict) and the downward effect (which it does), reducing power against the prediction of interest. A one-tailed test directs the entire α=0.05 region to the predicted side.

---

## 2. Data

**Sources:**
- FBref player-match data, consolidated into the local `FULL_DICT_ROWS` pickle (per-competition / per-season dictionaries of `ROWS_DICTS_SPECIALS` and `ROWS_DICTS_SUMMARY` DataFrames).

**Competitions:** Premier League (PL), La Liga (LALIGA), Serie A (SERIEA), Bundesliga (BUNDESLIGA), Ligue 1 (LIGUE1).

**Unit of analysis:** one penalty.

**Sample size (used for the test):** 3,535 linked penalties in 3,249 matches — 86.0% of the 4,110 penalties in the 3,492 matches with any penalty event. 79 are in treatment, 3,456 in control. The seasons in scope and counts are written to `data/data.json` by `code/build.py` and surfaced in the dashboard.

**Variables used:**
- `Performance_PKatt` — penalty attempted by this player in this match
- `Performance_PK` — penalty scored by this player in this match
- `Performance_PKwon` — penalty foul won by this player in this match (i.e. the fouled player)
- `Performance_PKcon` — penalty foul conceded by this player in this match
- `Pos` — playing position (GK / DF / MF / FW)
- `match_id`, `team_id` — used to tie the taker, the fouled player and the conceder to the same penalty

**Cleaning & filtering decisions:**

1. **SPECIALS + SUMMARY merge.** For each competition, the per-season `ROWS_DICTS_SPECIALS` (contains `PKwon`, `PKcon`) and `ROWS_DICTS_SUMMARY` (contains `PK`, `PKatt`) DataFrames are concatenated across seasons and merged on the identification + match-context columns (`match_id`, `Player`, `team_id`, `Season`, etc.) with an outer join, producing one combined DataFrame per competition where every player–match row carries all four penalty fields.

2. **Loose penalty filter (descriptive only).** Matches are retained if any row has a non-zero value in any of `{PK, PKatt, PKwon, PKcon}`. This pool drives the dashboard's *Overall* / *Per-league* / *Per-season* charts.

3. **Penalty-level linkage (used for the test).** The penalty columns are per player per match, so a penalty has to be reassembled from three rows: the taker (`PKatt`) and the fouled player (`PKwon`) on one team, the conceder (`PKcon`) on the other. Whenever a team took **exactly one penalty in a match**, those three are unambiguous — even if the opponent also had a penalty — and the penalty is linked. Attempts that cannot be linked are excluded:
    - 573 attempts where one team took two or more penalties in the match (which taker belongs to which foul is not recorded);
    - 1 attempt with no conceder recorded, and 1 where the opponent recorded two conceded penalties against one taken.

4. **Treatment construction.** A linked penalty is in the *treatment* group if **both** hold for that penalty:
    - its conceder has `Pos = GK` (the goalkeeper conceded the foul); and
    - its taker is also the player credited with `PKwon = 1` (the fouled player took it himself).

5. **Control construction.** Every other linked penalty — the GK conceded but someone else took it, an outfielder conceded (any taker), or no `PKwon` was recorded on the attacking team (handballs and unrecorded fouls). This pools three of the four cells in the GK × taker 2×2 matrix (see §4 below).

---

## 3. Methodology

**Test.** Two-proportion z-test, one-tailed (alternative: treatment proportion smaller).

For p̂₁ = k₁/n₁ (treatment) and p̂₂ = k₂/n₂ (control), pooled p̂ = (k₁ + k₂) / (n₁ + n₂):

$$
Z \;=\; \frac{\hat{p}_1 - \hat{p}_2}{\sqrt{\hat{p}(1-\hat{p})\left(\tfrac{1}{n_1}+\tfrac{1}{n_2}\right)}}
$$

P-value: P(Z ≤ z_obs). Reject H₀ if p < 0.05.

Implementation: `statsmodels.stats.proportion.proportions_ztest([k_t, k_c], [n_t, n_c], alternative='smaller')`.

**Confidence intervals.** 95% Wilson intervals on each proportion (`statsmodels.stats.proportion.proportion_confint(..., method='wilson')`) — chosen over the normal approximation because the treatment cell is small (n = 79) and Wilson is well-behaved at moderate n. The difference treatment − control gets a 95% Newcombe (hybrid Wilson) interval (`confint_proportions_2indep(..., method='newcomb')`).

**Minimum detectable effect.** The smallest drop below the control rate that the one-tailed test at α = 0.05 detects with 80% power, given the observed cell sizes (Cohen's *h* via `proportion_effectsize`, `NormalIndPower`).

**Per-league replication.** The same test is applied within each of the five leagues, partitioning treatment / control identically but restricting to a single league at a time. Treatment-cell sample sizes within a single league are 10–23 — these tests are reported for transparency but are severely underpowered and any individual league's verdict should be read with that caveat.

**Assumptions and how they are met:**
- *Independence within and between groups.* Each linked penalty is a distinct (match, team) pair — a team contributes at most one penalty per match, and treatment and control are disjoint by construction. Two linked penalties can come from the same match (one per team), and the same taker can appear in many matches; the test does not model taker effects (see §5).
- *Approximate normality of the sampling distribution.* The rule of thumb (n·p̂ ≥ 10 and n·(1−p̂) ≥ 10) holds for the treatment cell (60 conversions, 19 misses) — the test is well-conditioned, but the small n caps achievable power.
- *Same underlying population.* All penalties are in-game (non-shootout) top-5-league penalties, from a single consolidated FBref-derived dataset.

**Software stack.**
- Python 3.12 (project venv at repo root)
- `pandas` — data wrangling, penalty linkage
- `statsmodels` — `proportions_ztest`, `proportion_confint`, `confint_proportions_2indep`, `NormalIndPower`
- Output: JSON to `data/data.json`; Chart.js dashboard at `analysis.html`

---

## 4. Results

> All numbers in this section come from `code/build.py` → `data/data.json` and are surfaced live in the dashboard.

### 4.1 Primary test (pooled across leagues)

| Group | n (penalties) | Conversions | Rate | 95% CI (Wilson) |
|---|---:|---:|---:|---|
| Treatment — GK fouled the taker | 79 | 60 | 75.95% | [65.46%, 84.03%] |
| Control — all other penalties   | 3,456 | 2,729 | 78.96% | [77.57%, 80.29%] |

- Difference: **−3.01 pp** (treatment − control), 95% CI **[−13.6, +5.2] pp** (Newcombe)
- z = **−0.649**
- p = **0.258** (one-tailed)
- Minimum detectable effect (80% power): **12.6 pp**
- **Verdict: fail to reject H₀ at α = 0.05.**

The point estimate moves in the predicted direction, but the interval for the difference runs from a large drop to a modest gain. The data is consistent with anything from a meaningful negative effect to no effect at all.

### 4.2 Per-league replication

Per-league treatment cells (n = 10–23) leave each test severely underpowered, and individual verdicts are noisy:

| League | Treatment rate (n) | Control rate (n) | Z | p (one-tailed) |
|---|---:|---:|---:|---:|
| Premier League | 91.30% (23) | 79.63% (599) | +1.375 | 0.915 |
| La Liga        | 55.56% (18) | 77.37% (716) | −2.167 | 0.015 |
| Serie A        | 80.00% (15) | 78.57% (812) | +0.134 | 0.553 |
| Bundesliga     | 60.00% (10) | 79.83% (575) | −1.539 | 0.062 |
| Ligue 1        | 84.62% (13) | 79.71% (754) | +0.437 | 0.669 |

La Liga clears p < 0.05 in the predicted direction; Bundesliga is marginal in the same direction; the Premier League, Serie A and Ligue 1 swing the other way. These are five uncorrected tests on cells in the teens — at a Bonferroni threshold of p < 0.01 none clears, and one nominally significant league in five is not unusual under pure noise. The pooled test is the only inference to take seriously.

### 4.3 2×2 matrix (context)

The treatment is one of the four cells in a 2×2 of (GK conceded the foul) × (taker was the fouled player):

|                                  | GK conceded the foul | Outfielder conceded the foul |
|----------------------------------|---|---|
| Taker = the player who was fouled | **75.95% (n=79)** ◀ treatment | 79.02% (n=491) |
| Taker = not the fouled player (incl. handballs) | 78.33% (n=203) | 79.00% (n=2,762) |

Visual inspection: the three control cells cluster tightly around 79%; the treatment cell sits ~3 pp below. The 2×2 makes the comparison transparent but does not change the inference — only the single primary test does.

---

## 5. Limitations

- **Power is the binding constraint.** At a treatment-cell n of 79 and a control rate around 79%, the minimum detectable effect at α=0.05 one-tailed and 80% power is about 12.6 percentage points. A real 3–5 pp effect would usually fail to reject under this design. A null result here is not strong evidence *against* the theory — it is consistent with both no effect and a moderate effect the data cannot resolve.
- **Penalties only, no shootouts.** All analysis is restricted to in-game penalties.
- **No score-state / time controls.** Conversion rates might vary by minute or scoreline; this analysis pools across all in-game situations.
- **No taker effect.** Who takes the kick is chosen, not random. If fouled players who take their own penalty are usually the designated taker anyway, the comparison is "designated taker after a GK foul" against a mixed pool — a bias that could run either way. Untested in this version.
- **Heterogeneous control.** The control pools penalties with no recorded fouled player (handballs, unrecorded fouls), which are not the same bench decision.
- **Unlinked penalties.** 575 of the 4,110 penalties cannot be tied to one taker, fouled player and conceder — almost all because one team took two or more in the match. If those penalties differ systematically, the linked sample is not fully representative.
- **No injury observation.** "Hurt taker" is the theoretical mechanism, but the dataset does not record whether the fouled player was actually injured or merely fouled. The treatment cell is therefore an *intent-to-treat* approximation of the mechanism.
- **FBref attribution edge cases.** Some `PKcon` allocations in goal-mouth scrambles depend on FBref's labelling and could carry small measurement error.

---

## 6. Conclusion

The bench-decision question — *should the fouled player take the penalty himself?* — does not get a clean answer from the available data. The point estimate moves the way the theory predicts (−3.01 pp), the per-league pattern is mixed, and the binding constraint is the size of the treatment cell, not the test design. A follow-up that pools additional seasons (or extends to other leagues with comparable data) would change the conclusion only by changing n — the analytical framing is in place.

For now, the practical takeaway is conservative: there is no clear data warrant either to override the fouled player who wants to take it himself, or to insist that he does. The verdict is "not yet detectable", not "false".

---

## References

1. FBref — *Player-match penalty statistics by league and season.* https://fbref.com
2. statsmodels — *proportions_ztest* documentation. https://www.statsmodels.org/
3. Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference.* JASA.
4. Newcombe, R. G. (1998). *Interval estimation for the difference between independent proportions: comparison of eleven methods.* Statistics in Medicine.

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Source code: [`code/build.py`](code/build.py).*
