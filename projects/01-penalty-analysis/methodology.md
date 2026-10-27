# Should the Fouled Player Take the Penalty Himself?: Conversion After a Goalkeeper Foul on the Taker

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** October 2026

---

## Abstract

When a goalkeeper fouls a player in the box, the fouled player frequently takes the resulting penalty himself. The practical question for the bench is whether he should: the just-fouled player is theoretically jarred and agitated, the goalkeeper across from him locked in. This study isolates that exact decision point across the top 5 European leagues, linking every penalty to its own taker, fouled player and conceder (treatment n = 79 penalties), and compares its conversion rate against every other linked penalty (control n = 3,456) using a one-tailed two-proportion z-test. The point estimate moves in the predicted direction (75.95% vs 78.96%, a 3.01 percentage-point drop) but the difference is not statistically detectable at α = 0.05 (z = −0.65, p = 0.258 one-tailed); the 95% interval for the difference runs from −13.6 to +5.2 pp. The result survives every check: three alternative control groups, two sensitivity samples and a logistic regression that accounts for the taker's status, record and experience, home/away, league and season (−3.25 pp, 95% CI −12.60 to +5.63). The design only reliably detects a drop of about 12.6 pp, an equivalence test cannot establish "no difference" within ±5 pp or within a looser ±10 pp, and a Bayesian version puts a 76.8% probability on the fouled taker converting less. Two side findings: defined from kicks before the match, a team's established taker converts only 1.74 pp more than other takers, and takers' conversion rates show no split-half repeatability (−0.08).

---

## 1. Research Question

> When a goalkeeper fouls a player to give away a penalty, should that fouled player take the penalty himself, or should the team hand the ball to a designated specialist? Equivalently: does conversion drop when the fouled player takes the kick, relative to all other penalties?

### Hypotheses

- **H₀:** conversion_treatment = conversion_control
- **H₁:** conversion_treatment < conversion_control &nbsp;&nbsp; *(one-tailed)*

### Why one-tailed

The theory underpinning the test is directional. The taker has just been fouled (typically a body collision that left them on the ground) and is presumed physically jarred and emotionally agitated. The goalkeeper, having committed the foul that elevated their save into a high-leverage situation, is presumed maximally focused. Both mechanisms point the same way: conversion *down*. A two-tailed test would split α between an upward effect (which the theory does not predict) and the downward effect (which it does), reducing power against the prediction of interest. A one-tailed test directs the entire α=0.05 region to the predicted side. The two-tailed p-value is reported alongside (§4.1).

---

## 2. Data

**Sources:**
- FBref player-match data, consolidated into the local `FULL_DICT_ROWS` pickle (per-competition / per-season dictionaries of `ROWS_DICTS_SPECIALS` and `ROWS_DICTS_SUMMARY` DataFrames).

**Competitions:** Premier League (PL), La Liga (LALIGA), Serie A (SERIEA), Bundesliga (BUNDESLIGA), Ligue 1 (LIGUE1).

**Seasons:** 2017-2018 through 2023-2024.

**Unit of analysis:** one penalty.

**Sample size (used for the test):** 3,535 linked penalties in 3,249 matches: 86.0% of the 4,110 penalties in the 3,492 matches with any penalty event. 79 are in treatment, 3,456 in control. Shoot-outs are not included.

**Variables used:**
- `Performance_PKatt`: penalty attempted by this player in this match
- `Performance_PK`: penalty scored by this player in this match
- `Performance_PKwon`: penalty foul won by this player in this match (i.e. the fouled player)
- `Performance_PKcon`: penalty foul conceded by this player in this match
- `Pos`: playing position (GK / DF / MF / FW)
- `match_id`, `team_id`: used to tie the taker, the fouled player and the conceder to the same penalty
- `date`, `site`: the match date (for the taker's history before each kick) and home/away

**Cleaning & filtering decisions:**

1. **SPECIALS + SUMMARY merge.** For each competition, the per-season `ROWS_DICTS_SPECIALS` (contains `PKwon`, `PKcon`) and `ROWS_DICTS_SUMMARY` (contains `PK`, `PKatt`) DataFrames are concatenated across seasons and merged on the identification + match-context columns (`match_id`, `Player`, `team_id`, `Season`, etc.) with an outer join, producing one combined DataFrame per competition where every player–match row carries all four penalty fields.

2. **Loose penalty filter (descriptive only).** Matches are retained if any row has a non-zero value in any of `{PK, PKatt, PKwon, PKcon}`. This pool drives the page's *by league* and *by season* charts.

3. **Penalty-level linkage (used for the test).** The penalty columns are per player per match, so a penalty has to be reassembled from three rows: the taker (`PKatt`) and the fouled player (`PKwon`) on one team, the conceder (`PKcon`) on the other. Whenever a team took **exactly one penalty in a match**, those three are unambiguous (even if the opponent also had a penalty) and the penalty is linked. Attempts that cannot be linked are excluded:
    - 573 attempts where one team took two or more penalties in the match (which taker belongs to which foul is not recorded);
    - 1 attempt with no conceder recorded, and 1 where the opponent recorded two conceded penalties against one taken.

4. **Treatment construction.** A linked penalty is in the *treatment* group if **both** hold for that penalty:
    - its conceder has `Pos = GK` (the goalkeeper conceded the foul); and
    - its taker is also the player credited with `PKwon = 1` (the fouled player took it himself).

5. **Control construction.** Every other linked penalty: the GK conceded but someone else took it, an outfielder conceded (any taker), or no `PKwon` was recorded on the attacking team (handballs and unrecorded fouls). This pools three of the four cells in the GK × taker 2×2 matrix (§4.7).

6. **The taker before the kick.** For every attempt in the data (linked or not), sorted by date: the taker's earlier attempts and conversions (any club), and the team's *established taker*, the player who had taken the most penalties for that team before this match. 1,085 linked penalties were taken by the established taker and 1,908 by someone else; in 404 the team's history was tied and in 138 the team had no earlier penalty in the data.

---

## 3. Methodology

### 3.1 Primary test

Two-proportion z-test, one-tailed (alternative: treatment proportion smaller). For p̂₁ = k₁/n₁ (treatment) and p̂₂ = k₂/n₂ (control), pooled p̂ = (k₁ + k₂) / (n₁ + n₂):

$$
Z \;=\; \frac{\hat{p}_1 - \hat{p}_2}{\sqrt{\hat{p}(1-\hat{p})\left(\tfrac{1}{n_1}+\tfrac{1}{n_2}\right)}}
$$

P-value: P(Z ≤ z_obs). Reject H₀ if p < 0.05. Implementation: `statsmodels.stats.proportion.proportions_ztest([k_t, k_c], [n_t, n_c], alternative='smaller')`.

### 3.2 Intervals and power

95% Wilson intervals on each proportion (`proportion_confint(..., method='wilson')`), chosen over the normal approximation because the treatment cell is small and Wilson is well-behaved at moderate n. The difference treatment − control gets a 95% Newcombe (hybrid Wilson) interval (`confint_proportions_2indep(..., method='newcomb')`).

**Minimum detectable effect.** The smallest drop below the control rate that the one-tailed test at α = 0.05 detects with 80% power, given the observed cell sizes (Cohen's *h* via `proportion_effectsize`, `NormalIndPower`).

### 3.3 Equivalence test (TOST)

"Not significant" does not mean "no difference". To test for *no practical difference*, two one-sided z-tests (unpooled standard error) check whether the gap lies inside a margin. Equivalence holds when both one-sided tests reject at α = 0.05, i.e. when the 90% interval for the gap (Newcombe, α = 0.10) lies entirely inside the margin. The smallest margin for which equivalence would hold is the larger absolute bound of that 90% interval.

**The margins.** The primary margin is ±5 pp, about one extra miss in every twenty penalties, with a looser ±10 pp as the secondary margin. The ±5 pp margin is set by the decision the study informs: it is larger than the edge a team's established taker has over other takers when the role is defined from kicks before the match (+1.74 pp, §4.5), so a drop that big would be reason to switch takers. Both margins were chosen after the analysis, not before; they were not pre-registered.

### 3.4 Bayesian check

Each conversion rate gets a flat Beta(1, 1) prior; the posteriors are Beta(1 + k, 1 + n − k). The posterior of the gap is simulated with 400,000 draws (fixed seed) and summarised as the probability that the treatment rate is lower, the probability that the drop exceeds each margin (±5 pp and the looser ±10 pp), and a 95% credible interval (equal-tailed).

### 3.5 Adjusted model

Who takes the kick is chosen, not random. A logistic regression accounts for what was known about the taker before he stepped up, plus the match context:

```
scored ~ treat + established + record + experience + home + C(league) + C(season)
```

- `established`: he had taken the most penalties for this team before this match (§2, step 6). Defining the role from the whole season instead would leak the outcome: a taker who misses can lose the job, so his misses get filed under "someone else" (§4.5).
- `record`: his earlier conversion rate, shrunk toward the overall rate with 20 pseudo-attempts (empirical-Bayes style, so three kicks don't count as a track record), on the logit scale. Only kicks before this match count; a leave-one-out career rate would correlate negatively with the outcome by construction.
- `experience`: log(1 + earlier attempts).
- `home`, league and season fixed effects.

Standard errors are clustered by taker (822 takers). The gap is reported in percentage points as the average marginal effect of `treat` (predicted conversion with the flag set to 1 minus with it set to 0, averaged over all 3,535 penalties), with a 95% interval from 1,000 cluster-bootstrap resamples of takers.

### 3.6 Alternative controls and sensitivity samples

The pooled control mixes three different situations. Each is also tested on its own, and the sample is cut two ways:

- **Same goalkeeper foul, someone else took it**: isolates *who takes it*: the foul is the same.
- **Fouled player took it, but an outfielder fouled him**: isolates *the goalkeeper*: the taker was fouled in both groups.
- **Excluding penalties with no fouled player recorded**: drops handballs and unrecorded fouls from the control.
- **Without 2017-2018**: the season with the lowest conversion in the descriptive data (§4.8).
- **Established takers only / other takers only**: both groups restricted to the same taker status.

### 3.7 Per-league tests and multiple comparisons

The primary test is repeated within each league. Treatment cells of 10–23 per league leave each test severely underpowered; the five p-values are adjusted with Holm's step-down procedure (`statsmodels.stats.multitest.multipletests(method='holm')`).

### 3.8 Taker repeatability

If penalty conversion were a stable skill, a taker's record would be a confounder worth more than a shrunk rate. For the 126 players with at least 10 kicks in the data, kicks are ordered by date and split into alternate halves; the correlation between the two halves' conversion rates, stepped up with the Spearman-Brown formula, estimates the reliability of a full record. The 95% interval comes from 1,000 bootstrap resamples of takers. Where a player took two penalties in one match and scored one, the order within the match is unknown; the scored kick is assumed first.

### 3.9 Assumptions and how they are met

- *Independence within and between groups.* Each linked penalty is a distinct (match, team) pair: a team contributes at most one penalty per match, and treatment and control are disjoint by construction. The same taker can appear in many matches; the adjusted model clusters by taker.
- *Approximate normality of the sampling distribution.* The rule of thumb (n·p̂ ≥ 10 and n·(1−p̂) ≥ 10) holds for the treatment cell (60 conversions, 19 misses): the test is well-conditioned, but the small n caps achievable power.
- *Same underlying population.* All penalties are in-game (non-shootout) top-5-league penalties, from a single consolidated FBref-derived dataset.

### 3.10 Software

- Python 3.12 (project venv at repo root)
- `pandas`, `numpy`: data wrangling, penalty linkage, taker histories
- `statsmodels`: `proportions_ztest`, `proportion_confint`, `confint_proportions_2indep`, `NormalIndPower`, `glm` (Binomial), `multipletests`
- `scipy`: normal tail probabilities for the equivalence test
- Output: JSON to `data/data.json`; Chart.js page at `analysis.html`

---

## 4. Results

> All numbers in this section come from `code/build.py` → `data/data.json` and are surfaced live on the analysis page.

### 4.1 Primary test (pooled across leagues)

| Group | n (penalties) | Conversions | Rate | 95% CI (Wilson) |
|---|---:|---:|---:|---|
| Treatment: GK fouled the taker | 79 | 60 | 75.95% | [65.46%, 84.03%] |
| Control: all other penalties   | 3,456 | 2,729 | 78.96% | [77.57%, 80.29%] |

- Difference: **−3.01 pp** (treatment − control), 95% CI **[−13.6, +5.2] pp** (Newcombe)
- z = **−0.649**
- p = **0.258** (one-tailed); two-tailed p = 0.516
- Minimum detectable effect (80% power): **12.6 pp**
- **Verdict: fail to reject H₀ at α = 0.05.**

The point estimate moves in the predicted direction, but the interval for the difference runs from a large drop to a modest gain.

### 4.2 Bounding the null

- **Equivalence, primary margin (±5 pp):** 90% CI for the gap [−11.77, +4.05] pp; TOST p = 0.341. Equivalence is **not** established.
- **Equivalence, looser ±10 pp margin:** TOST p = 0.075; not established either. The smallest margin for which equivalence would hold is 11.8 pp. The data rule out a drop larger than that, and little else.
- **Bayesian (Beta(1, 1) priors):** probability that the fouled taker converts less = 76.8%; probability that the drop exceeds 5 pp = 37.4%, and that it exceeds the looser ±10 pp = 9.8%; probability that the gap lies within ±5 pp = 59.8%. Posterior median −3.42 pp, 95% credible interval [−13.65, +5.16] pp.

Both views agree: the data lean towards a drop, cannot rule out a large one, and cannot rule out none.

### 4.3 Adjusted model

Average marginal effect of the treatment: **−3.25 pp, 95% CI [−12.60, +5.63]** (cluster bootstrap, 1,000 resamples; n = 3,535 penalties, 822 takers).

| Term | Odds ratio | 95% CI | p (two-tailed) |
|---|---:|---|---:|
| GK fouled the taker (treatment) | 0.83 | [0.50, 1.38] | 0.474 |
| Team's established taker at kick time | 1.07 | [0.86, 1.34] | 0.535 |
| Prior conversion record (shrunk, logit) | 0.76 | [0.47, 1.25] | 0.279 |
| Prior penalties taken (log) | 1.10 | [0.99, 1.22] | 0.086 |
| Home side | 1.07 | [0.91, 1.26] | 0.418 |

Accounting for the taker and the context moves the gap by a quarter of a point. None of the taker covariates is clearly predictive, consistent with §4.5.

### 4.4 Alternative controls and sensitivity samples

| Check | Treatment | Comparison | Gap (pp) | 95% CI | p (one-tailed) |
|---|---:|---:|---:|---|---:|
| All other penalties (primary) | 75.95% (79) | 78.96% (3,456) | −3.01 | [−13.58, +5.18] | 0.258 |
| Same goalkeeper foul, someone else took it | 75.95% (79) | 78.33% (203) | −2.38 | [−14.04, +7.79] | 0.334 |
| Fouled player took it, but an outfielder fouled him | 75.95% (79) | 79.02% (491) | −3.07 | [−14.09, +5.86] | 0.268 |
| Excluding penalties with no fouled player recorded | 75.95% (79) | 79.15% (2,590) | −3.20 | [−13.80, +5.04] | 0.245 |
| Without 2017-2018 | 78.26% (69) | 79.83% (2,999) | −1.57 | [−12.73, +6.67] | 0.374 |
| Established takers only, both groups | 82.14% (28) | 80.42% (1,057) | +1.72 | [−16.15, +12.01] | 0.590 |
| Other takers only, both groups | 72.73% (44) | 78.86% (1,864) | −6.13 | [−20.82, +4.96] | 0.163 |

Every control choice gives a gap of −2.4 to −3.2 pp. Dropping 2017-2018 halves the gap; splitting by taker status leaves cells of 28 and 44 that point in opposite directions with very wide intervals.

### 4.5 The taker

**Who takes it.** 35.4% of treatment penalties (28 of 79) were taken by the team's established taker, against 30.6% of control penalties: the fouled self-taker is not disproportionately a non-specialist.

**The established taker's edge** (defined from kicks before the match):

| League | Established taker | Other takers | Gap (pp) | 95% CI |
|---|---:|---:|---:|---|
| All five leagues | 80.46% (1,085) | 78.72% (1,908) | +1.74 | [−1.30, +4.68] |
| Serie A | 79.49% (312) | 78.24% (432) | +1.25 | [−4.79, +7.07] |
| La Liga | 79.45% (219) | 77.17% (381) | +2.29 | [−4.75, +8.86] |
| Premier League | 80.73% (218) | 79.45% (326) | +1.29 | [−5.74, +7.93] |
| Bundesliga | 84.81% (158) | 78.33% (323) | +6.48 | [−1.16, +13.25] |
| Ligue 1 | 79.21% (178) | 80.27% (446) | −1.06 | [−8.45, +5.56] |

**The leak.** Defining the established taker from the whole season (the player with the most attempts for the team that season, later kicks included) gives 83.00% (2,259) vs 71.63% (1,276), a gap of +11.37 pp [+8.48, +14.31]. Much of that is likely the outcome leaking into the label (a taker who misses can lose the job); only the before-the-kick definition is used in the model.

**Repeatability.** Across 126 takers with at least 10 kicks (2,091 kicks), the split-half correlation is −0.04; the Spearman-Brown reliability is **−0.08, 95% CI [−0.47, 0.18]**. Over samples of this size, a taker's conversion record carries no detectable information about his other kicks.

### 4.6 Per-league replication

Per-league treatment cells (n = 10–23) leave each test severely underpowered, and individual verdicts are noisy:

| League | Treatment rate (n) | Control rate (n) | Z | p (one-tailed) | p (Holm) |
|---|---:|---:|---:|---:|---:|
| Premier League | 91.30% (23) | 79.63% (599) | +1.375 | 0.915 | 1.000 |
| La Liga        | 55.56% (18) | 77.37% (716) | −2.167 | 0.015 | 0.076 |
| Serie A        | 80.00% (15) | 78.57% (812) | +0.134 | 0.553 | 1.000 |
| Bundesliga     | 60.00% (10) | 79.83% (575) | −1.539 | 0.062 | 0.247 |
| Ligue 1        | 84.62% (13) | 79.71% (754) | +0.437 | 0.669 | 1.000 |

La Liga clears p < 0.05 in the predicted direction before adjustment; after Holm's correction for five tests, no league does. One nominally significant league in five is not unusual under pure noise. The pooled test is the only inference to take seriously.

### 4.7 2×2 matrix (context)

The treatment is one of the four cells in a 2×2 of (GK conceded the foul) × (taker was the fouled player):

|                                  | GK conceded the foul | Outfielder conceded the foul |
|----------------------------------|---|---|
| Taker = the player who was fouled | **75.95% (n=79)** ◀ treatment | 79.02% (n=491) |
| Taker = not the fouled player (incl. handballs) | 78.33% (n=203) | 79.00% (n=2,762) |

The three control cells cluster tightly, from 78.33% to 79.02%; the treatment cell sits 3.01 pp below the pooled control. The 2×2 makes the comparison transparent but does not change the inference.

### 4.8 Descriptive context

Across all 4,110 penalties (loose filter), conversion by season ranges from 72.59% (2017-2018) to 80.79% (2021-2022). The lowest season sits clearly below the others; it is dropped in one sensitivity check (§4.4), and the adjusted model includes season fixed effects.

---

## 5. Practical takeaways

### Evidence labels

- **Strong**: large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a pre-stated equivalence margin); survives the main controls; holds across leagues or seasons.
- **Moderate**: consistent direction and plausible size, with one gap: the interval touches zero, a single method or sample, or only partial replication.
- **Exploratory**: small samples, an interval that comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.

### Who should care

- **Managers (match-day decisions): Exploratory.** No case yet for taking the ball off a fouled player: −3.0 pp, plausibly anywhere from −13.6 to +5.2. The interval comfortably includes zero and the equivalence test fails, so the data support neither a rule to hand the ball over nor a rule that he keeps it.
- **Coaches (training & tactics): Exploratory.** Being the team's established taker adds little: +1.7 pp over other takers (−1.3 to +4.7), higher in 4 of 5 leagues. The interval includes zero.
- **Clubs (recruitment): Moderate.** Don't pay for a penalty record: split-half reliability of −0.08 (95% CI −0.47 to 0.18) across 126 takers. The upper bound rules out a strongly repeatable conversion rate over samples of this size; it rests on one method and one dataset, hence Moderate.
- **Agents: no defensible claim** from this study.

---

## 6. Limitations

- **Power is the binding constraint.** At a treatment-cell n of 79 and a control rate around 79%, the minimum detectable effect at α=0.05 one-tailed and 80% power is about 12.6 percentage points. A real 3–5 pp effect would usually fail to reject under this design. A null result here is not evidence *against* the theory: it is consistent with both no effect and a moderate effect the data cannot resolve.
- **Equivalence margins chosen after the analysis.** The ±5 pp and ±10 pp margins (§3.3) were set once the results were known, so the equivalence tests are yardsticks rather than pre-registered tests. Neither margin is passed, so the choice does not flatter the result.
- **Taker selection is only partly controlled.** The model accounts for the taker's status, record and experience before the kick, but not for what the bench sees on the day: confidence, a knock, who asked for the ball.
- **No score-state / time controls.** Conversion rates might vary by minute or scoreline; the player-match table carries neither.
- **No goalkeeper effect.** Some goalkeepers save more penalties than others; the facing goalkeeper is not modelled.
- **Heterogeneous control.** The primary control pools penalties with no recorded fouled player (handballs, unrecorded fouls), which are not the same bench decision; §4.4 shows the result does not depend on it.
- **Unlinked penalties.** 575 of the 4,110 penalties cannot be tied to one taker, fouled player and conceder, almost all because one team took two or more in the match. If those penalties differ systematically, the linked sample is not fully representative.
- **No injury observation.** "Hurt taker" is the theoretical mechanism, but the dataset does not record whether the fouled player was actually injured or merely fouled. The treatment cell is therefore an *intent-to-treat* approximation of the mechanism.
- **FBref attribution edge cases.** Some `PKcon` allocations in goal-mouth scrambles depend on FBref's labelling and could carry small measurement error.

---

## 7. Conclusion

The bench-decision question (*should the fouled player take the penalty himself?*) does not get a clean answer from the available data. The point estimate moves the way the theory predicts (−3.01 pp), every alternative control group and the adjusted model land in the same place, and the binding constraint is the size of the treatment cell, not the test design. A follow-up that pools additional seasons (or extends to other leagues with comparable data) would change the conclusion only by changing n; the analytical framing is in place.

For now, the practical takeaway is conservative: there is no clear data warrant either to override the fouled player who wants to take it himself, or to insist that he does. The verdict is "not yet detectable", not "false".

---

## References

1. FBref: *Player-match penalty statistics by league and season.* https://fbref.com
2. statsmodels: *proportions_ztest*, *confint_proportions_2indep*, *GLM*, *multipletests* documentation. https://www.statsmodels.org/
3. Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference.* JASA.
4. Newcombe, R. G. (1998). *Interval estimation for the difference between independent proportions: comparison of eleven methods.* Statistics in Medicine.
5. Schuirmann, D. J. (1987). *A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability.* Journal of Pharmacokinetics and Biopharmaceutics.
6. Holm, S. (1979). *A simple sequentially rejective multiple test procedure.* Scandinavian Journal of Statistics.
7. Cameron, A. C., Gelbach, J. B. & Miller, D. L. (2008). *Bootstrap-based improvements for inference with clustered errors.* Review of Economics and Statistics.

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Source code: [`code/build.py`](code/build.py).*
