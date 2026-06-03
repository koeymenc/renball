# The True Contributors: A Three-Layer Expected-Points Attribution of Player Value

**Author:** Can Luca Köymen
**Site:** [renball.com](https://renball.com)
**Date:** May 2026

---

## Abstract

The standard scoreboard credits two touchpoints per goal — the scorer and, sometimes, the assister — and treats every goal as one undifferentiated unit. This project applies the time-aware expected-points (EP) value function from [project 02](https://renball.com/projects/02-points-by-gamestate/) to a **third** layer of contribution, the pre-assist (FBref's SCA2, the shot-creating action before the assist), and re-ranks players by the EP they collect across all three roles. Across **39,381 goal events** in six top-flight European leagues over seven seasons (2017-2018 to 2023-2024), with minutes/position/age metadata attached for **6,516 players**, the framework reproduces the eye-test at the top (Messi, Mbappé, Neymar lead the per-90 board) and then surfaces the players the box score systematically undervalues. The marquee finding: **Julian Brandt collects 40.93 EP from pre-assists alone — second in Europe only to Lionel Messi (51.69) — and 39% of his total contribution comes from that single layer, roughly double the SCA2 share of pure goalscorers like Mbappé (20%) or Salah (19%).** The work answers seven research questions (Q1–Q7) spanning per-90 leaderboards, season-by-season MVPs, late-game specialists, efficiency ratios, position-adjusted boards, the hidden-architect SCA2 board, and an under-23 watchlist.

---

## 1. Research Question

> When a goal's expected-points value is credited not just to the scorer and assister but also to the **pre-assist-creator (SCA2)**, which players does the model elevate that conventional goal-and-assist counting overlooks — and is that elevation robust to how the three credit layers are weighted?

This is a value-attribution study, not a hypothesis test. It rests on three evaluable claims, each addressed in §4:

1. **Face validity** — crediting three layers and normalising per 90 minutes must reproduce the consensus elite at the top of the board, or the framework has no standing to surface surprises beneath it (Q1a).
2. **Robustness** — the ranking must not be an artefact of the equal `1/1/1` credit split; re-weighting the layers should move the board only marginally (Q1b).
3. **Discovery** — the SCA2 layer must isolate a contribution profile (the "hidden architect") that absolute goal-and-assist tallies cannot see (Q6).

---

## 2. Data

**Primary source — goal events.** Inherited directly from project 02: the per-match FBref-derived shot tables (`match_data_final_<league>.pkl`), filtered to `outcome == "goal"`, one row per goal with `gd_before`, `gd_after`, `minute_bin`, the scoring team, and three contributor columns — `goalscorer`, `sca1_creator` (assist), and `sca2_creator` (pre-assist). Project 02's pipeline is used unmodified; project 03 reads its output `goal_events` DataFrame and the two value lookup tables (`val_map_timed`, `val_map_untimed`).

**Secondary source — player metadata.** Minutes played, position, and age are read from `FULL_DICT_ROWS.pkl` → `ROWS_DICTS_SUMMARY` (FBref per-player season-summary tables), via `RENBALL_DATA_PATH`. This source covers the **top five leagues only** — it does **not** contain Eredivisie. Every per-90 calculation is therefore Top-5-only; absolute-EP boards retain all six leagues.

**Leagues (6):** Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie.
**Per-90 scope (5):** as above, minus Eredivisie.
**Seasons (7):** 2017-2018 through 2023-2024.
**Sample:** 39,381 goal events; 6,516 players with attached metadata.

**Cleaning & filtering decisions:**

1. **Unknown contributors dropped.** FBref rows where the scorer/SCA1/SCA2 string cannot be parsed (own goals, fragmented entries) aggregate to a fake `"Unknown"` player. They are dropped from every editorial board; the dashboard retains them for transparency.
2. **Player pooling.** A player who appears under multiple `(scoring_team, player)` rows — because of a mid-period transfer — is pooled to a single row. EP and credit columns are summed; `primary_team` is set to the team where the player registered the most credits.
3. **Position bucketing.** The FBref `Pos` string is reduced to its first token (`"CM,LB"` → `"CM"`) and mapped to one of four buckets (`GK`/`DF`/`MF`/`FW`). A player's position is the **modal** bucket across all observed season rows.
4. **Age.** Taken as the **maximum** age observed across a player's rows — effectively age at the end of the most recent observed season (FBref's fractional-year format is preserved).
5. **Minutes.** Summed across all in-scope league-seasons per player. Players with zero attached minutes are excluded from every per-90 board.

---

## 3. Methodology

### 3.1 The inherited value function

Project 02 prices each goal by the swing in expected league points it produces, conditioned on game-state and minute. For a goal that moves the goal difference `gd_before → gd_after` in minute bin `b` (scoring team's perspective):

```
ep_collected_timed   = EP(gd_after, b) − EP(gd_before, b)
ep_collected_untimed = EP_untimed(gd_after) − EP_untimed(gd_before)
```

where `EP(gd, b) = 3·P(win | state) + 1·P(draw | state)` is the empirical expected final-match points over every team that entered that `(gd, minute_bin)` state. A late equaliser is worth nearly a full point; a 4–0 consolation, almost nothing. Only one-step transitions in the `[−7, +7]` GD range are kept. This project does **not** rebuild the value function — it reuses project 02's `val_map_timed` / `val_map_untimed` verbatim.

### 3.2 The third credit layer (SCA2)

Project 02 builds contributor tables for two roles, `goalscorer` and `sca1_creator`. Project 03 adds a third by re-running the *identical* aggregation machinery on the `sca2_creator` column — the pre-assist, FBref's shot-creating action immediately preceding the assist. The result is a parallel SCA2 contributor table carrying the same EP, per-bin (`ep_bin_X`) and per-transition (`cnt_*`) breakdowns as the scorer and assist tables. No project-02 code is modified; the SCA2 build composes its public functions.

### 3.3 Three-layer credit (Q1a — the default model)

The headline credit model gives **each of the three roles one credit per goal involved in**, and sums the EP each role collected:

```
three_layer = (scorer ⊕ sca1) ⊕ sca2
```

where `⊕` is project 02's outer-merge-and-sum on `(scoring_team, contributor)`. A player who scored a goal *and* pre-assisted a different goal receives two credits and the sum of both EP swings. `goals_involved` is the raw count of credit events; EP columns stack additively.

### 3.4 Weighted credit (Q1b — the robustness check)

To test whether the equal split drives the ranking, the build re-walks every goal event and emits up to three weighted credit rows with weights applied to **EP only** (the `goals_involved` count stays a raw 1 per credit):

| Role | Weight |
|---|---:|
| Scorer | 0.40 |
| SCA1 (assist) | 0.35 |
| SCA2 (pre-assist) | 0.25 |

The weighted EP is then pooled and normalised per 90 exactly as in Q1a. Comparing the Q1a and Q1b rankings (Q1 rank-shift) isolates the effect of the weighting choice.

### 3.5 Per-90 normalisation

Total EP rewards volume; **EP per 90 minutes** rewards rate:

```
ep_per_90 = (exp_points_collected_timed / minutes_played) × 90
```

Because `minutes_played` comes from the Top-5-only summary tables, **every per-90 board excludes Eredivisie**. This scope is stamped into the `scope` / `scope_note` metadata of every per-90 view and surfaced as subtitle text on the dashboard and editorial page.

### 3.6 Qualification thresholds

| View | Threshold | Rationale |
|---|---|---|
| Q1a, Q1b, Q2, Q5 | ≥ 1,000 minutes | ≈ 11 full matches — enough to stabilise a per-90 rate |
| Q7 (young) | ≥ 500 minutes | young players have less playing time; floor lowered deliberately |
| Q3 (late-game) | ≥ 15 credits (dashboard) · ≥ 30 (editorial) | the editorial cut removes super-sub small-sample specialists |
| Q4 (efficiency) | ≥ 5 credits (dashboard) · ≥ 20 (editorial) | ditto, for the ratio boards |

The dashboard exposes the looser threshold for transparency; the editorial page uses the stricter "substantive" cut so the narrative isn't carried by four-game cameos.

### 3.7 The seven research questions

| Q | Board | Key metric | Scope |
|---|---|---|---|
| Q1a | Full-credit leaderboard | EP/90, credits 1/1/1 | Top-5, ≥1,000 min |
| Q1b | Weighted leaderboard | weighted EP/90 (0.40/0.35/0.25) | Top-5, ≥1,000 min |
| Q2 | Per-(league × season) MVPs + 5-league combined | top EP/90 per cell | Top-5, ≥1,000 min/season |
| Q3 | Late-game specialists | share of EP from the 60–90 bins | all 6 leagues |
| Q4 | Efficiency ratios | EP per credit (Q4a); time multiplier (Q4b) | all 6 leagues |
| Q5 | Position-adjusted (DF/MF/FW) | EP/90 by modal position | Top-5, ≥1,000 min |
| Q6 | Hidden architects | absolute & per-90 SCA2 EP; role split | abs: all 6; per-90: Top-5 |
| Q7 | Young players (≤ 23) | EP/90 | Top-5, ≥500 min |

Q2 annotates each cell with the real-world award winner where `data/static/actual_mvps.json` has been manually curated. Q4c (EP per shot) is **deferred** — it requires non-goal shot extraction not present in project 02's goal-events subset.

### 3.8 Software stack

- Python 3.12 (repo-root project venv)
- `pandas`, `numpy` — aggregation and per-event credit walking
- `pickle` with a pandas-<2 index shim for the legacy `FULL_DICT_ROWS.pkl`
- Output: `data/data.json` (editorial payload) and `data/dashboard/` (9 per-view JSONs + manifest)
- `code/enrich.py` owns all project-03 logic; `code/build.py` orchestrates project 02's pipeline + this enrichment

---

## 4. Results

> All numbers come from `code/build.py` → `data/data.json` and are surfaced live in the editorial page.

### 4.1 Q1a — the model clears the eye test

| # | Player | Team | Minutes | Credits | EP/90 |
|--:|---|---|--:|--:|--:|
| 1 | Lionel Messi | Barcelona | 16,516 | 356 | **1.141** |
| 2 | Kylian Mbappé | Paris S-G | 16,403 | 334 | 1.054 |
| 3 | Neymar | Paris S-G | 9,354 | 205 | 0.986 |
| 4 | Cole Palmer | Chelsea | 3,111 | 50 | 0.983 |
| 5 | Josip Iličić | Atalanta | 8,176 | 139 | 0.958 |

The top of the board is exactly the consensus elite — which is the point. Before the framework is trusted to surface surprises, it has to recover what everyone already knows.

### 4.2 Q1b — weighting barely moves the answer

Re-running with `0.40 / 0.35 / 0.25` weights leaves **the top eight essentially identical**. The biggest movers are pure scorers gaining a few places under the heavier scoring weight (Lewandowski +6, Dovbyk +7) and creator-heavy names slipping (Jallow −9, Ljajić −9). That the carefully-tuned weights reproduce the simple `1/1/1` board *is* the robustness result: the ranking is not an artefact of the credit split.

### 4.3 Q2 — season-by-season MVPs

The model's top per-90 pick for La Liga 2022-2023 is **Nicolas Jackson at Villarreal (1.211 EP/90, 1,598 minutes, 26 credits)** — a year before Chelsea paid £30m+ for him. The 5-league combined pick for 2020-2021 is **Luis Muriel at Atalanta (1.605 EP/90, 43 credits)** — not what the trophy cabinet recorded.

### 4.4 Q3 — late-game substantives (≥ 30 credits)

| # | Player | Team | Credits | Late share | Late EP / Total EP |
|--:|---|---|--:|--:|--:|
| 1 | Cristian Tello | Betis | 44 | **73.8%** | 28.2 / 38.2 |
| 2 | Sergio León | Betis | 33 | 66.7% | 17.3 / 25.9 |
| 3 | Matías Vecino | Inter | 47 | 65.9% | 24.2 / 36.7 |

"Late share" is the fraction of a player's EP collected in the 60–75 and 75–90 bins. Tello's contribution lives almost entirely in the high-leverage minutes.

### 4.5 Q4 — efficiency ratios (≥ 20 credits)

- **Q4a · EP per credit:** Evann Guessand leads at **1.105 EP per credit** — he scores and creates in higher-leverage moments per goal than anyone else above the substantive threshold.
- **Q4b · time-aware multiplier (`ep_timed / ep_untimed`):** Guessand again at **1.196×** — the time dimension upgrades him most over the time-blind baseline.

### 4.6 Q5 — position-adjusted (outfield only)

The midfielder panel surfaces the framework's most stable elite pick: **Kevin De Bruyne, MF #3, over 14,674 minutes and 206 credits at 0.734 EP/90** — by far the largest sample of any top-3 pick on any board in this project. Jamal Musiala sits MF #2 (6,302 minutes, 0.786). The defender panel is dominated by wing-back archetypes (Grimaldo). **Goalkeepers are excluded** (see §5).

### 4.7 Q6 — the hidden architects (the marquee finding)

Top SCA2 EP collectors, all six leagues pooled:

| # | Player | Team | SCA2 credits | SCA2 EP |
|--:|---|---|--:|--:|
| 1 | Lionel Messi | Barcelona | 89 | 51.69 |
| 2 | **Julian Brandt** | **Dortmund** | **66** | **40.93** |
| 3 | Kylian Mbappé | Paris S-G | 60 | 37.55 |

Splitting each player's total EP by role exposes Brandt's structural difference:

| Player | Scorer EP | SCA1 EP | SCA2 EP | SCA2 share |
|---|--:|--:|--:|--:|
| **Julian Brandt** | 26.10 | 38.75 | 40.93 | **38.7%** |
| Nabil Fekir | 35.24 | 39.76 | 34.65 | 31.6% |
| Lionel Messi | 84.15 | 73.61 | 51.69 | 24.7% |
| Kylian Mbappé | 97.28 | 57.25 | 37.55 | 19.6% |
| Mohamed Salah | 96.58 | 58.20 | 37.44 | 19.5% |

The pre-assist is Brandt's single largest contribution layer — a profile no pure goalscorer shares. **Brandt is what the model exists to find.**

### 4.8 Q7 — young players to watch (age ≤ 23)

The board mixes credible established names (Musiala, Palmer) with very-low-sample flyers (Fofana 1.249 EP/90 on 559 minutes; Durán 1.24 on 611). The most interesting cell is at the bottom: **Lamine Yamal, Q7 #10, 0.738 EP/90 across 2,209 minutes and 23 credits at age 16.9** — the youngest player in the dataset to clear 500 minutes, and his rate rests on nearly a full season of evidence rather than a cameo.

---

## 5. Limitations

This project inherits every limitation of project 02's value function and adds its own:

1. **No expected-goal weighting** (inherited). Every goal counts 1.0 — a tap-in and a 30-yard volley value identically.
2. **Penalties and own goals are not separated** (inherited). They trigger the same transition value as open-play goals.
3. **Observational, not causal** (inherited). EP is the gap between the two states a goal connects, not the goal's counterfactual effect on the final result.
4. **Credit caps at SCA2.** Project 02 stopped at SCA1; this project adds SCA2 but goes no further. Build-up sequences distribute value further upstream than three layers capture.
5. **Per-90 boards exclude Eredivisie.** The minutes source (`FULL_DICT_ROWS.pkl`) covers the top five leagues only. Absolute boards (Q3, Q4, the Q6 absolute board) include all six; per-90 boards (Q1, Q2, Q5, Q6 per-90, Q7) do not. Eredivisie-only players are absent from every per-90 ranking.
6. **The model has no opinion on goalkeepers.** The three credited touchpoints are ones GKs occupy rarely; the top GK posts ~0.1 EP/90 against ~1.1 for the top forward — a coverage artefact, not a value judgement. GK contribution needs a different model (shot-stopping over expected, distribution value). Q5 reports outfield panels only.
7. **Equal `1/1/1` credit is a modelling choice.** Q1b shows the ranking is robust to a reasonable re-weighting, but the "right" weights are not estimated from data — they are a stipulation.
8. **Metadata is approximate.** Position is the modal FBref bucket; age is the maximum observed (≈ age at end of latest season). Both are season-summary derived, not match-resolved.
9. **Q4c (EP per shot) is deferred.** It requires non-goal shot extraction absent from the current goal-events pipeline — tracked as a TODO.

---

## 6. Conclusion

Crediting a third contribution layer does not change who sits at the very top of European football — Messi, Mbappé and Neymar lead the per-90 board with or without the pre-assist, and re-weighting the layers barely moves anyone. That stability is what licenses the interesting claim underneath it: once the SCA2 layer is priced, a small set of players whose value the box score cannot see comes into focus. Julian Brandt is the cleanest example — second only to Messi in pre-assist EP, with the pre-assist as his single largest contribution layer, a profile pure goalscorers never show.

The framework is a value-attribution lens, not a recruitment oracle. It says nothing about defending, goalkeeping, or chance creation that doesn't end in a goal, and it is calibrated to leverage rather than to a counterfactual. What it does well is name the contribution football's mainstream stats systematically under-credit. The next iterations are clear: extend credit past SCA2, fold in xG, and build the GK model the EP framework structurally cannot provide.

---

## References

- **Inherited framework:** [Project 02 — Not All Goals Are Equal](https://renball.com/projects/02-points-by-gamestate/) — the time-aware expected-points value function.
- **Source data:** FBref ([fbref.com](https://fbref.com)). Shot tables (`match_data_final_<league>.pkl`) and per-player summary tables (`FULL_DICT_ROWS.pkl`).
- **Interactive dashboard:** [`dashboard.html`](dashboard.html) — all seven ranking datasets, per-league and per-season drill-down, search, filtering, XLSX/CSV export.
- **Editorial summary:** [`analysis.html`](analysis.html) in this project folder.
- **Project page:** [renball.com/projects/03-true-contributors/](https://renball.com/projects/03-true-contributors/)
- **Source code:** `code/` — `build.py` (orchestrator), `enrich.py` (SCA2 merge, three-layer credit, Q1–Q7), `report.py`.

---

*Methodology document generated alongside [analysis.html](analysis.html) and [slides.pdf](slides.pdf). Per the current Renball toolchain, methodology.html is the canonical artifact — there is no methodology PDF (use the browser's print-to-PDF if you need one).*
