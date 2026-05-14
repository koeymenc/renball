# Should the Fouled Player Take the Penalty Himself? — Conversion After a Goalkeeper Foul on the Taker

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** May 2026

---

## Abstract

When a goalkeeper fouls a player in the box, the fouled player frequently takes the resulting penalty himself. The practical question for the bench is whether he should — the just-fouled player is theoretically jarred and agitated, the goalkeeper across from him locked in. This study isolates that exact decision point (treatment n = 100) across the top 5 European leagues and compares its conversion rate against every other penalty in scope (control n = 3,757) using a one-tailed two-proportion z-test. The point estimate moves in the predicted direction (75.00% vs 78.25%, a 3.25 percentage-point drop) but the difference is not statistically detectable at α = 0.05 (z = −0.78, p = 0.218 one-tailed). The conclusion is constrained by power: at a treatment cell of ~100, even a moderate true effect would be hard to surface against a control rate so close to the population mean.

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

**Sample size (strict filter, used for the test):** 3,857 single-penalty matches — 100 in treatment, 3,757 in control. The seasons in scope and counts are written to `data/data.json` by `code/build.py` and surfaced in the dashboard.

**Variables used:**
- `Performance_PKatt` — penalty attempted by this player in this match
- `Performance_PK` — penalty scored by this player in this match
- `Performance_PKwon` — penalty foul won by this player in this match (i.e. the fouled player)
- `Performance_PKcon` — penalty foul conceded by this player in this match
- `Pos` — playing position (GK / DF / MF / FW)
- `match_id` — used to group all players involved in the same penalty event

**Cleaning & filtering decisions:**

1. **SPECIALS + SUMMARY merge.** For each competition, the per-season `ROWS_DICTS_SPECIALS` (contains `PKwon`, `PKcon`) and `ROWS_DICTS_SUMMARY` (contains `PK`, `PKatt`) DataFrames are concatenated across seasons and merged on the identification + match-context columns (`match_id`, `Player`, `team_id`, `Season`, etc.) with an outer join, producing one combined DataFrame per competition where every player–match row carries all four penalty fields.

2. **Loose penalty filter (descriptive only).** Matches are retained if any row has a non-zero value in any of `{PK, PKatt, PKwon, PKcon}`. This pool drives the dashboard's *Overall* / *Per-league* / *Per-season* charts.

3. **Strict single-penalty filter (used for the test).** For the primary test we additionally require that for each `match_id`, the per-column maximum across all rows is ≤ 1 and at least one column is > 0. This restricts the test sample to matches with a single penalty event so the GK-caused / taker-was-fouled attribution is unambiguous — in matches with multiple penalties, attribution becomes ambiguous (which penalty did the GK foul? which one did the taker win?), so they are excluded.

4. **Treatment construction.** A strict-filter match falls in the *treatment* group if **both** of the following hold within the same `match_id`:
    - at least one row has `PKcon = 1` and `Pos = GK` (the GK conceded the penalty foul); and
    - at least one row has `PKwon = 1` and `PKatt = 1` (the same player won the foul and took the penalty).

5. **Control construction.** Every strict-filter match that is *not* in treatment. This pools three of the four cells in the GK × taker 2×2 matrix (see §4 below).

---

## 3. Methodology

**Test.** Two-proportion z-test, one-tailed (alternative: treatment proportion smaller).

For p̂₁ = k₁/n₁ (treatment) and p̂₂ = k₂/n₂ (control), pooled p̂ = (k₁ + k₂) / (n₁ + n₂):

$$
Z \;=\; \frac{\hat{p}_1 - \hat{p}_2}{\sqrt{\hat{p}(1-\hat{p})\left(\tfrac{1}{n_1}+\tfrac{1}{n_2}\right)}}
$$

P-value: P(Z ≤ z_obs). Reject H₀ if p < 0.05.

Implementation: `statsmodels.stats.proportion.proportions_ztest([k_t, k_c], [n_t, n_c], alternative='smaller')`.

**Confidence intervals.** 95% Wilson intervals on each proportion (`statsmodels.stats.proportion.proportion_confint(..., method='wilson')`) — chosen over the normal approximation because the treatment cell is small (n=100) and Wilson is well-behaved at moderate n.

**Per-league replication.** The same test is applied within each of the five leagues, partitioning treatment / control identically but restricting to a single league at a time. Treatment-cell sample sizes within a single league are 13–25 — these tests are reported for transparency but are severely underpowered and any individual league's verdict should be read with that caveat.

**Assumptions and how they are met:**
- *Independence within and between groups.* Each penalty is taken in a distinct match (strict filter); treatment and control match-id sets are disjoint by construction.
- *Approximate normality of the sampling distribution.* The standard rule of thumb (n·p̂ ≥ 10 and n·(1−p̂) ≥ 10) holds for the pooled treatment cell (100 × 0.75 = 75; 100 × 0.25 = 25) — the test is well-conditioned, but the small n caps achievable power.
- *Same underlying population.* All penalties are in-game (non-shootout) top-5-league penalties, from a single consolidated FBref-derived dataset.

**Software stack.**
- Python 3.12 (project venv at repo root)
- `pandas` — data wrangling, match-level grouping
- `statsmodels` — `proportions_ztest`, `proportion_confint`
- Output: JSON to `data/data.json`; Chart.js dashboard at `analysis.html`

---

## 4. Results

> All numbers in this section come from `code/build.py` → `data/data.json` and are surfaced live in the dashboard.

### 4.1 Primary test (pooled across leagues)

| Group | n (attempts) | Conversions | Rate | 95% CI (Wilson) |
|---|---:|---:|---:|---|
| Treatment — GK fouled the taker | 100 | 75 | 75.00% | [65.70%, 82.45%] |
| Control — all other penalties   | 3,757 | 2,940 | 78.25% | [76.91%, 79.54%] |

- Difference: **−3.25 pp** (point estimate, treatment − control)
- z = **−0.778**
- p = **0.218** (one-tailed)
- **Verdict: fail to reject H₀ at α = 0.05.**

The point estimate moves in the predicted direction but the 95% CI on the treatment proportion alone spans roughly 65.7%–82.5%, comfortably overlapping the entire control CI. The data is consistent with anything from a meaningful negative effect to no effect at all.

### 4.2 Per-league replication

Per-league treatment cells (n = 13–25) leave each test severely underpowered, and individual verdicts are noisy:

| League | Treatment rate (n) | Control rate (n) | Z | p (one-tailed) |
|---|---:|---:|---:|---:|
| Premier League | 88.00% (25) | 78.59% (626) | +1.13 | 0.87 |
| La Liga        | 57.89% (19) | 77.46% (803) | −2.00 | 0.023 |
| Serie A        | 80.95% (21) | 77.70% (888) | +0.35 | 0.64 |
| Bundesliga     | 61.54% (13) | 78.18% (614) | −1.43 | 0.077 |
| Ligue 1        | 77.27% (22) | 79.42% (826) | −0.24 | 0.40 |

La Liga clears p<0.05 in the predicted direction; Bundesliga is marginal in the same direction; Premier League and Serie A swing the other way. With single-cell counts in the teens, this is approximately what one would expect from noise. The pooled test is the only inference to take seriously.

### 4.3 2×2 matrix (context)

The treatment is one of the four cells in a 2×2 of (GK caused foul) × (taker was the fouled player):

|                                  | GK caused the foul | Outfielder caused the foul |
|----------------------------------|---|---|
| Taker = the player who was fouled | **75.00% (n=100)** ◀ treatment | 78.87% (n=549) |
| Taker = a different player        | 78.11% (n=265)    | 78.15% (n=2,943) |

Visual inspection: the three control cells cluster tightly around 78%; the treatment cell sits ~3 pp below. The 2×2 makes the comparison transparent but does not change the inference — only the single primary test does.

---

## 5. Limitations

- **Power is the binding constraint.** At a treatment-cell n of ~100 and a control rate around 78%, the minimum detectable effect at α=0.05 one-tailed and 80% power is roughly 9–10 percentage points. A real 3–5 pp effect would consistently fail to reject under this design. A null result here is not strong evidence *against* the theory — it is consistent with both no effect and a moderate effect the data cannot resolve.
- **Penalties only, no shootouts.** All analysis is restricted to in-game penalties.
- **No score-state / time controls.** Conversion rates might vary by minute or scoreline; this analysis pools across all in-game situations.
- **No taker fixed effect.** Elite penalty specialists are concentrated in the control group (most are not the player just fouled by a GK in their own match), which would tend to *raise* the control rate and inflate the apparent treatment−control gap rather than mask it; the direction of this bias is, if anything, working in the theory's favour, so does not threaten the null verdict.
- **No injury observation.** "Hurt taker" is the theoretical mechanism, but the dataset does not record whether the fouled player was actually injured or merely fouled. The treatment cell is therefore an *intent-to-treat* approximation of the mechanism.
- **FBref attribution edge cases.** Some `PKcon` allocations in goal-mouth scrambles depend on FBref's labelling and could carry small measurement error. The strict single-penalty filter mitigates but does not eliminate this.

---

## 6. Conclusion

The bench-decision question — *should the fouled player take the penalty himself?* — does not get a clean answer from the available data. The point estimate moves the way the theory predicts (−3.25 pp), the per-league pattern is mixed, and the binding constraint is the size of the treatment cell, not the test design. A follow-up that pools additional seasons (or extends to other leagues with comparable data) would change the conclusion only by changing n — the analytical framing is in place.

For now, the practical takeaway is conservative: there is no clear data warrant either to override the fouled player who wants to take it himself, or to insist that he does. The verdict is "not yet detectable", not "false".

---

## References

1. FBref — *Player-match penalty statistics by league and season.* https://fbref.com
2. statsmodels — *proportions_ztest* documentation. https://www.statsmodels.org/
3. Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference.* JASA.

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Source code: [`code/build.py`](code/build.py).*
