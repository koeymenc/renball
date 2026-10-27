# The True Contributors: Expected Points per 90, Shared Credit and Honest Rankings

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** October 2026

---

## Abstract

Every goal scored in the Premier League, La Liga, Serie A, Bundesliga and Ligue 1 from 2017-18 to 2023-24 (34,054 goals in 12,599 matches) is priced by the expected points it added for the scoring team, using the team-minute model of Project 02 unchanged, and credited to the players involved: the scorer, SCA1 (the action before the shot) and SCA2 (the action before that), once per player per goal. A player's expected points (EP) per 90 minutes is then pulled toward the average for his position by an empirical Bayes model whose strength depends on his minutes, and every player's rank gets a 95% interval from 4,000 joint posterior draws. Among 4,167 players with at least 900 minutes, **Lionel Messi (0.813 EP per 90) and Kylian Mbappé (0.773) are the only players with a top-10 probability of 95% or more**; the number 3, Neymar, has a plausible rank from 1 to 34. Five of the ten highest raw per-90 rates belong to short careers that leave the adjusted top 10. EP per 90 repeats from one season to the next (r = 0.69, 95% CI 0.67–0.71), the share of a player's credits from SCA2 partly repeats (0.38, 0.27–0.48), and EP per involvement (how decisive a player's goals are) barely does (0.17, 0.11–0.23). Against the actual player-of-the-season award in each league, the model's pick names the winner in 12 of 33 league-seasons (chance: about 0.1), fewer than a simple goals-plus-assists count (17).

---

## 1. Research Question

> Which players add the most expected points per 90 minutes, once each goal is priced by what it was worth and shared with the players who made it, and how sure can a ranking of them be?

Four evaluable parts:

1. **Ranking with uncertainty:** an EP-per-90 board where small samples are shrunk and every rank carries an interval.
2. **Credit rule:** whether the way a goal's value is shared (full credit once per player, every role separately, or a 40/35/25 split) changes the answer.
3. **Skill or noise:** which of the numbers repeat from one season to the next.
4. **External check:** how often the model's best player in a league-season matches the actual award winner, against chance and against a goals-plus-assists count.

---

## 2. Data

**Sources:** FBref match pages, stored locally as one pickle per league (`match_data_final_<league>.pkl` in `RENBALL_MATCH_DATA_PATH`), read through Project 02's extraction (`matches.py`). Per match: the shot table (minute, team, scorer, outcome, SCA1 and SCA2 players), `match_details` (official score, teams, date) and each side's player summary (minutes, position and age per player). Award winners: `data/static/actual_mvps.json`, one entry per league and season with the award name and a source URL, checked in October 2026.

**Scope:** the top 5 leagues, 2017-18 to 2023-24 (seven seasons). The Eredivisie, which Project 02's value model also uses, is left out of the boards so that every player is compared within the same five leagues the award check covers.

**Where the data ends:** 2023-24. The SCA2 data end there because the source discontinued them, so the study can't be extended to later seasons with the same method. Ages and the "young players" board refer to 30 June 2024.

**Sample:** 12,599 matches with a usable shot table and no goal of unknown minute; 34,054 goals; 6,566 players with minutes, 4,167 of them with at least 900. SCA1 is recorded for 94.3% of goals and SCA2 for 78.3% (77.7% to 79.1% in every season); the scorer is his own SCA1 on 10.4% of goals.

**Units of analysis:** the *goal* for credits; the *player over all seven seasons* for the boards; the *player-league-season* for the award check; the *pair of consecutive seasons* for repeatability.

**Cleaning and construction:**

1. **Goal prices.** Project 02's team-minute model on its own sample (13,206 matches in six leagues, own-goal matches excluded), recomputed here and checked against Project 02's published values before anything else runs: a go-ahead goal from level is worth 0.733 EP in the first 15 minutes and 1.507 in the last 15.
2. **Player identity.** FBref's per-match age (`years-days`) gives a birth date; players are keyed by name + birth date, so 45 names shared by different players are kept apart (shown with a birth year).
3. **Credits.** A goal's recorded roles (scorer, SCA1, SCA2) become role credits (92,842). For the per-90 boards a player gets one credit per goal at its full value, whatever his roles, which merges 8,694 role credits (9.4%) into 84,148 credits. For the SCA2 board every role counts separately.
4. **Minutes, position, age** come from the player summaries of the same matches, so a player's EP and minutes cover exactly the same games. Position is the one he played most minutes in (FBref's first listed position, grouped into GK, DF, MF, FW). Two credits have no matching appearance and are kept.
5. **Own goals.** The shot table has none, so in matches with an own goal the running score is wrong from it on. 8.1% of goals come from such matches; they keep their value on the boards, as in Project 02.

---

## 3. Methodology

### 3.1 Goal value and EP per 90

For a goal from goal difference \(g\) to \(g+1\) in 15-minute window \(b\), Project 02's value is

$$v = V(g+1, b) - V(g, b),$$

where \(V\) is the expected final points of a team in that state, estimated from every team-minute. A player's EP is the sum of \(v\) over his credits; EP per 90 is \(x_i = 90 \cdot \text{EP}_i / m_i\) for \(m_i\) minutes.

### 3.2 Empirical Bayes shrinkage

Each player's observed rate is treated as a noisy measurement of his true rate \(\theta_i\):

$$x_i \mid \theta_i \sim N\!\left(\theta_i,\; v_i\right), \qquad v_i = \frac{90^2\,\varphi_p}{m_i}, \qquad \theta_i \sim N(\mu_p, \tau_p^2),$$

where \(p\) is the player's position. The dispersion \(\varphi_p\) is the per-minute variance of a player's match EP around his own rate, pooled within the position (quasi-Poisson):

$$\varphi_p = \frac{\sum_i \sum_j (e_{ij} - r_i m_{ij})^2 / m_{ij}}{\sum_i (n_i - 1)},$$

with \(e_{ij}\) and \(m_{ij}\) the EP and minutes of player \(i\) in match \(j\), \(r_i\) his per-minute rate and \(n_i\) his matches. The prior mean and spread \(\mu_p, \tau_p^2\) are estimated by the DerSimonian–Laird method from players with at least 900 minutes. The adjusted rate and its posterior variance are

$$\hat\theta_i = \mu_p + \frac{\tau_p^2}{\tau_p^2 + v_i}\,(x_i - \mu_p), \qquad s_i^2 = \frac{\tau_p^2\, v_i}{\tau_p^2 + v_i}.$$

| Position | Players (900+ min) | \(\mu\) (EP per 90) | \(\tau\) | \(\varphi\) |
|---|---:|---:|---:|---:|
| Forwards | 963 | 0.402 | 0.100 | 0.00468 |
| Midfielders | 1,303 | 0.221 | 0.109 | 0.00263 |
| Defenders | 1,588 | 0.114 | 0.062 | 0.00128 |
| Goalkeepers | 313 | 0.009 | 0.003 | 0.00009 |

For a forward, the share of the gap to \(\mu\) that the shrinkage removes is 79% at 1,000 minutes, 56% at 3,000 and 28% at 10,000.

### 3.3 Rank intervals

All 4,167 eligible players' rates are drawn together from \(N(\hat\theta_i, s_i^2)\) 4,000 times (seed 2026); each draw is ranked, and a player's plausible rank is the 2.5th to 97.5th percentile of his ranks. The top-10 probability is the share of draws in which he ranks 10th or better. The draws are independent across players: they carry each player's sampling noise, not the shared uncertainty of the goal prices.

### 3.4 Measured intervals

The 95% ranges on measured EP and EP per 90 come from Project 02's 1,000 match-bootstrap resamples (stratified by league, seed 2026): each resample re-prices every goal with that resample's values and reweights the matches each credit and each minute came from.

### 3.5 Credit rules

Three rules, each shrunk the same way: full credit once per player per goal (the headline); the old rule, every role a credit (a self-assisted goal counts twice); and a split of each goal's value 40/35/25 between scorer, SCA1 and SCA2, renormalised over the roles recorded for that goal. Ranks among the 4,167 eligible players are compared by top-10 overlap and rank correlation.

### 3.6 Repeatability

Per player-season (all five leagues together), the Pearson correlation between consecutive seasons of: EP per 90 and goal involvements per 90 (900+ minutes in both seasons), EP per involvement (10+ involvements in both) and the SCA2 share of role credits (20+ role credits in both). Intervals: 1,000 bootstrap resamples of players.

### 3.7 Award check

Per league-season, every player with 900+ minutes gets a season rate shrunk the same way (priors re-estimated from player-league-seasons). The model's pick is the highest adjusted season rate. It is compared with the actual award: PFA Players' Player of the Year (Premier League), Trofeo Alfredo Di Stéfano (La Liga; La Liga's own award was not given for most of the period), Serie A MVP (Serie A Footballer of the Year for 2017-18), VDV Player of the Season (Bundesliga) and UNFP Player of the Year (Ligue 1). Goalkeeper winners can't be picked and are left out of the counts. Baselines: a qualified player picked at random (expected matches \(\sum_c 1/n_c\)), the goals-plus-assists leader and the total-EP leader.

### 3.8 Decisive goals

EP per involvement is EP divided by credits: the average value of the goals a player was involved in. Its 95% interval comes from the same bootstrap; players with 50+ involvements are compared with the average credit, and the number clearly above or below is set against the 2.5% per side expected by chance.

### 3.9 Team context

A player's team share is his EP divided by his team's goal value while he played, with each match's team EP weighted by his minutes over 90.

### 3.10 Software

Python 3.12 (pandas, NumPy), Project 02's `matches.py` and `value_model.py`, this project's `players.py` and `shrink.py`; Chart.js on the page, Tabulator on the dashboard, python-pptx for the deck.

---

## 4. Results

### 4.1 The board

| # | Player | Team | Minutes | Measured EP / 90 | 95% range | Adjusted | Plausible rank | Top-10 chance | Team share |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Lionel Messi | Barcelona | 16,516 | 0.908 | 0.812–1.019 | 0.813 | 1–4 | 100% | 66.2% |
| 2 | Kylian Mbappé | Paris S-G | 16,403 | 0.858 | 0.756–0.960 | 0.773 | 1–7 | 100% | 60.4% |
| 3 | Neymar | Paris S-G | 9,354 | 0.824 | 0.706–0.938 | 0.702 | 1–34 | 78% | 58.0% |
| 4 | Erling Haaland | Dortmund | 10,702 | 0.798 | 0.666–0.939 | 0.695 | 2–31 | 75% | 55.7% |
| 5 | Robert Lewandowski | Bayern Munich | 18,888 | 0.736 | 0.648–0.832 | 0.680 | 2–33 | 67% | 52.0% |
| 6 | Josip Iličić | Atalanta | 8,176 | 0.802 | 0.633–0.988 | 0.675 | 2–57 | 60% | 63.2% |
| 7 | Cristiano Ronaldo | Juventus | 13,704 | 0.748 | 0.638–0.859 | 0.673 | 2–41 | 59% | 58.5% |
| 8 | Paulo Dybala | Juventus | 13,538 | 0.744 | 0.627–0.855 | 0.669 | 3–45 | 56% | 56.9% |
| 9 | Mohamed Salah | Liverpool | 20,697 | 0.705 | 0.618–0.789 | 0.658 | 3–42 | 45% | 53.6% |
| 10 | Harry Kane | Tottenham | 20,645 | 0.703 | 0.622–0.792 | 0.656 | 3–43 | 44% | 60.7% |

Only Messi and Mbappé have a top-10 probability of 95% or more. The plausible ranks of the top 10 reach down to 57. Messi's adjusted rate (0.813) sits at the bottom of his measured range: a normal prior pulls genuine outliers in somewhat too hard (§6).

### 4.2 Raw versus adjusted

| Player | Minutes | Measured EP / 90 | Adjusted | Adjusted rank | Pulled toward the average |
|---|---:|---:|---:|---:|---:|
| Cole Palmer | 3,111 | 0.841 | 0.600 | 19 | 54.9% |
| Victor Boniface | 1,546 | 0.804 | 0.518 | 69 | 71.0% |
| Adem Ljajić | 2,185 | 0.788 | 0.533 | 50 | 44.9% |
| Clinton N'Jie | 1,238 | 0.775 | 0.494 | 99 | 75.4% |
| Artem Dovbyk | 2,587 | 0.754 | 0.544 | 46 | 59.5% |

These five of the raw top 10 leave the adjusted top 10; the other five (Messi, Mbappé, Neymar, Iličić, Haaland) stay.

### 4.3 Credit rules

| Rule | Top-10 overlap with full credit | Rank correlation | Leader |
|---|---:|---:|---|
| Every role a credit | 10 | 0.998 | Lionel Messi |
| 40/35/25 split | 9 | 0.994 | Lionel Messi |

The split favours finishers: Mauro Icardi rises from 39 to 17 and Kevin De Bruyne falls from 16 to 43.

### 4.4 Repeatability

| Measure | r | 95% CI | Season pairs | Players |
|---|---:|---:|---:|---:|
| Goal involvements per 90 | 0.76 | 0.74–0.78 | 5,665 | 2,161 |
| EP per 90 | 0.69 | 0.67–0.71 | 5,665 | 2,161 |
| SCA2 share of role credits | 0.38 | 0.27–0.48 | 352 | 160 |
| EP per involvement | 0.17 | 0.11–0.23 | 1,329 | 586 |

### 4.5 Award check

Of 34 league-seasons with an award, one winner is a goalkeeper (Marc-André ter Stegen, La Liga 2022-23), leaving 33. The model's pick names the winner in **12**; the winner is in its top 3 in 20 and its top 10 in 30, with a median rank of 2. A random qualified player (242 to 321 per league-season) would name about 0.1. The goals-plus-assists leader names 17 and the total-EP leader 10.

| League | 2017-18 | 2018-19 | 2019-20 | 2020-21 | 2021-22 | 2022-23 | 2023-24 |
|---|---|---|---|---|---|---|---|
| Premier League | Salah ✓ | Agüero (van Dijk #174) | Mané (De Bruyne #4) | Fernandes (De Bruyne #56) | Salah ✓ | Haaland ✓ | Palmer (Foden #10) |
| La Liga | Messi ✓ | Messi ✓ | Messi (Benzema #2) | Messi (Suárez #6) | Benzema ✓ | Griezmann (ter Stegen, GK) | Sørloth (Bellingham #3) |
| Serie A | Dybala (Icardi #7) | Mertens (Ronaldo #4) | Ronaldo (Dybala #3) | Muriel (Lukaku #2) | Immobile (Leão #5) | Osimhen (Kvaratskhelia #2) | Dybala (Martínez #8) |
| Bundesliga | Lewandowski ✓ | Sancho (Reus #4) | Sancho (Lewandowski #2) | Lewandowski ✓ | Schick (Nkunku #4) | Nkunku (Bellingham #70) | Guirassy (Wirtz #7) |
| Ligue 1 | Fekir (Neymar #2) | Mbappé ✓ | Neymar (no award) | Mbappé ✓ | Mbappé ✓ | Messi (Mbappé #3) | Mbappé ✓ |

Cell: the model's pick; in brackets, the winner and his rank on the model's list; ✓ the pick won.

### 4.6 SCA2

| # | Player | Team | SCA2 credits | EP from SCA2 | 95% range | Plausible rank | Share from SCA2 |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Lionel Messi | Barcelona | 89 | 51.65 | 39.31–66.71 | 1–4 | 24.4% |
| 2 | Julian Brandt | Dortmund | 66 | 40.98 | 29.22–54.22 | 1–26 | 38.5% |
| 3 | Kylian Mbappé | Paris S-G | 61 | 37.42 | 27.00–48.71 | 2–41 | 19.5% |
| 4 | Mohamed Salah | Liverpool | 58 | 36.73 | 24.61–49.10 | 2–59 | 19.2% |
| 5 | Joshua Kimmich | Bayern Munich | 66 | 35.12 | 24.52–46.81 | 2–60 | 40.7% |

Among the 150 players with 100+ role credits the median SCA2 share is 22.5%; the highest are Luka Modrić (41.7%), Joshua Kimmich (40.7%) and Jordan Veretout (40.0%).

### 4.7 Decisive goals

The average credit is worth 0.687 EP. Of 432 players with 50+ involvements, 26 are clearly above it and 53 clearly below (about 11 per side expected by chance). The highest is M'Baye Niang (0.865, 0.778–0.952); the five lowest (Leroy Sané 0.477, Sergio Agüero 0.488, Neymar 0.492, Philippe Coutinho 0.503, Julian Draxler 0.506) all played for Barcelona, Bayern Munich, Manchester City or Paris S-G, whose goals often came with the match already decided.

### 4.8 Positions and young players

Best adjusted rate by position: forwards Messi (0.813), midfielders Kevin De Bruyne (0.604, rank 16 overall), defenders Raphaël Guerreiro (0.389, rank 557). The best goalkeeper's adjusted rate is 0.012 against a median forward's 0.391. Among 505 players aged 23 or under on 30 June 2024 with 900+ minutes, Erling Haaland leads (0.695, rank 4), then Cole Palmer (0.600) and Jamal Musiala (0.533).

---

## 5. Practical takeaways

### Evidence labels

- **Strong**: large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a pre-stated equivalence margin); survives the main controls; holds across leagues or seasons.
- **Moderate**: consistent direction and plausible size, with one gap: interval touches zero, single method or sample, or partial replication.
- **Exploratory**: small samples, interval comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.

### Who should care

- **Clubs (Strong):** rank on adjusted rates, not raw per-90s: 5 of the raw top 10 drop out once short careers are allowed for. Basis: 4,167 players, position priors, season-to-season r = 0.69.
- **Clubs (Strong):** EP per 90 repeats (r = 0.69); how decisive a player's goals look barely does (r = 0.17). Pay for involvement.
- **Agents (Moderate):** a pre-assist habit is partly real (SCA2 share r = 0.38, 352 season pairs, SCA2 recorded on 78.3% of goals).
- **Agents (Exploratory):** awards follow box scores: the goals-plus-assists leader matched 17 of 33 winners, the model 12; five different awards, a count rather than a test.
- **Coaches, managers:** no defensible claim from this study. It prices outcomes; it says nothing about how to train or change a match.

---

## 6. Limitations

1. **Prices, not causes.** Goal values come from what teams at that score went on to do; they say how much a goal mattered, not how hard it was.
2. **Three roles only.** Scorer, SCA1 and SCA2 are credited; defending, pressing, off-ball runs and earlier build-up earn nothing, so defenders and goalkeepers are undervalued by design.
3. **No team or league adjustment.** Players at high-scoring clubs get more involvements (the team share shows how much ran through them, nothing is subtracted); goal prices are pooled over six leagues.
4. **SCA2 coverage.** Missing for 21.7% of goals, and the data end in 2023-24 because the source discontinued it.
5. **Normal prior.** It pulls genuine outliers in too hard; the order at the top is robust, the level is conservative.
6. **Independent draws.** Plausible ranks carry each player's own noise, not the shared uncertainty of the goal prices.
7. **Own goals.** Goals in matches with an own goal (8.1%) keep a slightly mispriced value.
8. **Awards.** Five awards with different voters and one winner per season; a reality check, not a test.
9. **Weights.** The 40/35/25 split is a judgement, which is why it is a check and not the headline.

---

## 7. Conclusion

Priced by what each goal was worth and shared with the players who made it, the top of European football is Messi and Mbappé, clear of everyone at 0.813 and 0.773 EP per 90. Below them a ranking is a shortlist: the number 3 could plausibly be anywhere from 1 to 34. Short careers inflate raw per-90 rates, the volume of a player's involvement repeats while the decisiveness of his goals does not, and award voters follow the box score more closely than the model does.

---

## References

[^1]: FBref, match reports and shot tables, top 5 European leagues, 2017-18 to 2023-24. <https://fbref.com>
[^2]: Renball Project 02, *Not All Goals Are Equal*. <https://renball.com/projects/02-points-by-gamestate/analysis.html>
[^3]: DerSimonian, R. and Laird, N. (1986). Meta-analysis in clinical trials. *Controlled Clinical Trials* 7(3), 177–188.
[^4]: Efron, B. and Morris, C. (1975). Data analysis using Stein's estimator and its generalizations. *Journal of the American Statistical Association* 70(350), 311–319.
[^5]: Award winners and sources: `data/static/actual_mvps.json` (PFA, Marca's Trofeo Alfredo Di Stéfano, Lega Serie A, VDV, UNFP).
