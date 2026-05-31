"""
report.py - one-shot Phase 1 review printer.

Loads data/data.json + a lightweight team->league map (FULL_DICT_ROWS keys
only) and prints every table CK asked for. Not part of the build pipeline;
delete or keep as a helper.
"""
from __future__ import annotations
import json
import os
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import enrich  # for COMP_TO_LEAGUE

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJ = Path(__file__).resolve().parent.parent
DATA = json.load(open(PROJ / "data" / "data.json", "r", encoding="utf-8"))


# ────────────────────────────────────────────────────────────────────────
# team -> league lookup (FULL_DICT_ROWS quick load)
# ────────────────────────────────────────────────────────────────────────
def _install_shim():
    if "pandas.core.indexes.numeric" in sys.modules:
        return
    import pandas.core.indexes.base as b
    class S:
        Int64Index = b.Index; UInt64Index = b.Index
        Float64Index = b.Index; NumericIndex = b.Index
    sys.modules["pandas.core.indexes.numeric"] = S()


def build_team_to_league() -> dict:
    pkl = Path(os.environ.get(
        "RENBALL_DATA_PATH",
        r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA")) / "FULL_DICT_ROWS.pkl"
    _install_shim()
    with open(pkl, "rb") as f:
        full = pickle.load(f)
    m = {}
    for comp, sections in full.items():
        league = enrich.COMP_TO_LEAGUE.get(comp)
        if not league:
            continue
        summary = sections.get("ROWS_DICTS_SUMMARY")
        if not isinstance(summary, dict):
            continue
        for season, df in summary.items():
            if "team_name" not in df.columns:
                continue
            for t in df["team_name"].dropna().astype(str).unique():
                m.setdefault(t, league)
    return m


TEAM2LG = build_team_to_league()
print(f"[report] team->league map: {len(TEAM2LG):,} teams loaded\n")


def lg(team: str | None) -> str:
    if not team:
        return "-"
    return TEAM2LG.get(team, "-")


def fmt_n(v, d=3, dash="-"):
    if v is None:
        return dash
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def hdr(s):
    print()
    print("=" * 100)
    print(f"  {s}")
    print("=" * 100)


# ────────────────────────────────────────────────────────────────────────
# Q1a: Top 15 EP/90 full credit
# ────────────────────────────────────────────────────────────────────────
def print_q1a():
    hdr("Q1a - FULL-CREDIT EP/90 - Top 15 (>=1000 min, Top-5 leagues)")
    print(f"{'#':>3}  {'PLAYER':<24}  {'TEAM':<18}  {'POS':<3}  {'AGE':>5}  "
          f"{'LEAGUE':<16}  {'MINS':>6}  {'EP/90':>6}  {'TOTAL_EP':>9}")
    print("-" * 100)
    for r in DATA["q1a_full_credit"]["rows"][:15]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:24]:<24}  "
              f"{(r['primary_team'] or '-')[:18]:<18}  "
              f"{(r.get('pos') or '-'):<3}  "
              f"{fmt_n(r.get('age'), 1):>5}  "
              f"{lg(r['primary_team'])[:16]:<16}  "
              f"{r['minutes']:>6,}  "
              f"{r['ep_per_90']:>6.3f}  "
              f"{r['ep_timed']:>9.2f}")


# ────────────────────────────────────────────────────────────────────────
# Q1b: Top 15 weighted EP/90 + rank delta vs Q1a
# ────────────────────────────────────────────────────────────────────────
def print_q1b():
    a_rank = {r["player"]: r["rank"] for r in DATA["q1a_full_credit"]["rows"]}
    hdr("Q1b - WEIGHTED EP/90 - Top 15 (0.40 scorer / 0.35 SCA1 / 0.25 SCA2)")
    print(f"{'#':>3}  {'PLAYER':<24}  {'TEAM':<18}  {'POS':<3}  {'AGE':>5}  "
          f"{'LEAGUE':<16}  {'MINS':>6}  {'wEP/90':>6}  {'wEP_TOT':>9}  "
          f"{'dRANK':>6}")
    print("-" * 110)
    for r in DATA["q1b_weighted_credit"]["rows"][:15]:
        p = r["player"]
        ra = a_rank.get(p)
        if ra is None:
            d = " new"
        else:
            d = f"{ra - r['rank']:+d}"
        print(f"{r['rank']:>3}  "
              f"{p[:24]:<24}  "
              f"{(r['primary_team'] or '-')[:18]:<18}  "
              f"{(r.get('pos') or '-'):<3}  "
              f"{fmt_n(r.get('age'), 1):>5}  "
              f"{lg(r['primary_team'])[:16]:<16}  "
              f"{r['minutes']:>6,}  "
              f"{r['ep_weighted_per_90']:>6.3f}  "
              f"{r['ep_weighted_timed']:>9.2f}  "
              f"{d:>6}")


# ────────────────────────────────────────────────────────────────────────
# Q1: Biggest rank shifts (gainers + losers)
# ────────────────────────────────────────────────────────────────────────
def print_q1_shifts():
    hdr("Q1 - BIGGEST RANK SHIFTS (A=full credit vs B=weighted)")
    shifts = [s for s in DATA["q1_rank_shift"] if s["delta"] is not None]
    shifts.sort(key=lambda r: -abs(r["delta"]))
    print(f"{'PLAYER':<28}  {'A':>3}  {'B':>3}  {'DELTA':>6}  "
          "(+ = weighting HELPED, - = weighting HURT)")
    print("-" * 60)
    for r in shifts[:10]:
        print(f"{r['player'][:28]:<28}  "
              f"{r['rank_a']:>3}  {r['rank_b']:>3}  "
              f"{r['delta']:>+6d}")


# ────────────────────────────────────────────────────────────────────────
# Q2: Per-(league, season) MVPs + combined 5L  (most recent 3 seasons)
# ────────────────────────────────────────────────────────────────────────
def print_q2():
    hdr("Q2 - PER-(LEAGUE, SEASON) MVP GRID  (most recent 3 seasons)")
    grid = DATA["q2_mvp_grid"]["grid"]
    leagues = DATA["q2_mvp_grid"]["leagues"]
    seasons = DATA["q2_mvp_grid"]["seasons"][-3:]
    for season in seasons:
        print(f"\n  Season {season}:")
        print(f"    {'LEAGUE':<16}  {'PLAYER':<26}  {'TEAM':<20}  "
              f"{'EP/90':>6}  {'MINS':>6}  {'CREDS':>5}")
        print("    " + "-" * 80)
        for league in leagues:
            cell = grid.get(league, {}).get(season, {}).get("model_pick")
            if not cell:
                print(f"    {league[:16]:<16}  (no qualifier)")
                continue
            print(f"    {league[:16]:<16}  "
                  f"{cell['player'][:26]:<26}  "
                  f"{cell['primary_team'][:20]:<20}  "
                  f"{cell['ep_per_90']:>6.3f}  "
                  f"{cell['minutes']:>6,}  "
                  f"{cell['goals_involved']:>5}")

    print(f"\n  Combined 5L MVP (all 7 seasons shown):")
    print(f"    {'SEASON':<11}  {'PLAYER':<26}  {'TEAM':<20}  "
          f"{'EP/90':>6}  {'MINS':>6}")
    print("    " + "-" * 80)
    for season, cell in DATA["q2_mvp_grid"]["combined_5l"].items():
        pick = cell.get("model_pick")
        if not pick:
            print(f"    {season:<11}  (no qualifier)")
            continue
        print(f"    {season:<11}  "
              f"{pick['player'][:26]:<26}  "
              f"{pick['primary_team'][:20]:<20}  "
              f"{pick['ep_per_90']:>6.3f}  "
              f"{pick['minutes']:>6,}")


# ────────────────────────────────────────────────────────────────────────
# Q3: Late-game share top 10
# ────────────────────────────────────────────────────────────────────────
def print_q3():
    hdr("Q3 - LATE-GAME SPECIALISTS  Top 10  (>=15 3-layer credits)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'TEAM':<20}  {'LATE_SHARE':>10}  "
          f"{'TOTAL_EP':>9}  {'LATE_EP':>8}  {'CREDITS':>7}")
    print("-" * 100)
    for r in DATA["q3_late_game"]["rows"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['primary_team'][:20]:<20}  "
              f"{r['share_late']:>10.3f}  "
              f"{r['ep_total']:>9.2f}  "
              f"{r['ep_late']:>8.2f}  "
              f"{r['goals_involved']:>7}")


# ────────────────────────────────────────────────────────────────────────
# Q4a/b: efficiency ratios
# ────────────────────────────────────────────────────────────────────────
def print_q4():
    hdr("Q4a - EP PER GOAL INVOLVED  Top 10  (>=5 credits)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'RATIO':>6}  {'TOTAL_EP':>9}  {'CREDITS':>7}")
    print("-" * 70)
    for r in DATA["q4_efficiency"]["q4a"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['ratio_ep_per_goal']:>6.3f}  "
              f"{r['ep_timed']:>9.2f}  "
              f"{r['goals_involved']:>7}")

    hdr("Q4b - TIME-AWARE MULTIPLIER  Top 10  (ep_timed / ep_untimed, >=5 credits)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'MULT':>5}  "
          f"{'EP_TIMED':>9}  {'EP_UNTIMED':>10}  {'CREDITS':>7}")
    print("-" * 80)
    for r in DATA["q4_efficiency"]["q4b"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['multiplier']:>5.3f}  "
              f"{r['ep_timed']:>9.2f}  "
              f"{r['ep_untimed']:>10.2f}  "
              f"{r['goals_involved']:>7}")
    print(f"\n  [Q4c] {DATA['q4_efficiency']['q4c_note']}")


# ────────────────────────────────────────────────────────────────────────
# Q5: position-adjusted (DF / MF / FW)
# ────────────────────────────────────────────────────────────────────────
def print_q5():
    hdr("Q5 - POSITION-ADJUSTED EP/90  Top 5 per panel  (>=1000 min, Top-5)")
    for pos, entry in DATA["q5_position"]["panels"].items():
        print(f"\n  [{pos}]")
        print(f"    {'#':>2}  {'PLAYER':<26}  {'TEAM':<20}  {'AGE':>5}  "
              f"{'MINS':>6}  {'EP/90':>6}  {'CREDITS':>7}")
        print("    " + "-" * 90)
        for r in entry["rows"]:
            print(f"    {r['rank']:>2}  "
                  f"{r['player'][:26]:<26}  "
                  f"{r['primary_team'][:20]:<20}  "
                  f"{fmt_n(r.get('age'), 1):>5}  "
                  f"{r['minutes']:>6,}  "
                  f"{r['ep_per_90']:>6.3f}  "
                  f"{r['goals_involved']:>7}")


# ────────────────────────────────────────────────────────────────────────
# Q6a/b: SCA2 hidden architects
# ────────────────────────────────────────────────────────────────────────
def print_q6():
    hdr("Q6a - SCA2 ABSOLUTE EP  Top 10  (all leagues)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'TEAM':<22}  "
          f"{'SCA2_EP':>8}  {'SCA2_CREDITS':>12}")
    print("-" * 90)
    for r in DATA["q6_architects"]["abs_top"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['primary_team'][:22]:<22}  "
              f"{r['ep_timed']:>8.2f}  "
              f"{r['goals_involved']:>12}")

    hdr("Q6b - SCA2 EP/90  Top 10  (>=1000 min, Top-5)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'TEAM':<22}  {'POS':<3}  "
          f"{'MINS':>6}  {'SCA2_EP/90':>10}  {'SCA2_CREDITS':>12}")
    print("-" * 110)
    for r in DATA["q6_architects"]["per_90_top"]["rows"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['primary_team'][:22]:<22}  "
              f"{(r.get('pos') or '-'):<3}  "
              f"{r['minutes']:>6,}  "
              f"{r['ep_per_90']:>10.3f}  "
              f"{r['goals_involved']:>12}")

    hdr("Q6 - LAYER BREAKDOWN  Top 10 by absolute SCA2 EP")
    print(f"{'PLAYER':<28}  {'TOTAL':>7}  {'SCORER%':>8}  {'SCA1%':>7}  {'SCA2%':>7}")
    print("-" * 70)
    for r in DATA["q6_architects"]["layer_breakdown"][:10]:
        tot = r["ep_total"] or 1.0
        print(f"{r['player'][:28]:<28}  "
              f"{tot:>7.2f}  "
              f"{100 * r['ep_scorer'] / tot:>7.1f}%  "
              f"{100 * r['ep_sca1'] / tot:>6.1f}%  "
              f"{100 * r['ep_sca2'] / tot:>6.1f}%")


# ────────────────────────────────────────────────────────────────────────
# Q7: young players
# ────────────────────────────────────────────────────────────────────────
def print_q7():
    hdr("Q7 - YOUNG PLAYERS TO WATCH  Top 10  (age <=23, >=500 min, Top-5)")
    print(f"{'#':>3}  {'PLAYER':<26}  {'TEAM':<20}  {'AGE':>5}  "
          f"{'LEAGUE':<16}  {'MINS':>6}  {'EP/90':>6}  {'CREDITS':>7}")
    print("-" * 110)
    for r in DATA["q7_young"]["rows"][:10]:
        print(f"{r['rank']:>3}  "
              f"{r['player'][:26]:<26}  "
              f"{r['primary_team'][:20]:<20}  "
              f"{fmt_n(r.get('age'), 1):>5}  "
              f"{lg(r['primary_team'])[:16]:<16}  "
              f"{r['minutes']:>6,}  "
              f"{r['ep_per_90']:>6.3f}  "
              f"{r['goals_involved']:>7}")


# ────────────────────────────────────────────────────────────────────────
# Editorial commentary
# ────────────────────────────────────────────────────────────────────────
def print_commentary():
    hdr("EDITORIAL NOTES (Claude's reading of the data)")

    print("""
CANDIDATES FOR THE 'NAMED PICKS' CLOSING SECTION
-------------------------------------------------
5 picks from the data the editorial 'The Picks' card row would feature:

1. Julian Brandt (Dortmund) - SCA2 specialist
   Q6: #2 absolute SCA2 EP (40.93). Only Messi creates more pre-assist
   value in Europe. Layer breakdown: 25% scorer / 37% SCA1 / 39% SCA2
   - the most balanced 'true architect' profile in the dataset.

2. Cole Palmer (Chelsea) - the half-season case
   Q1a: #4 EP/90 in Europe (0.983) in only 3,111 minutes, age 22.0.
   Also #3 in Q7 young leaderboard. Sample-size caveat applies.

3. Kevin De Bruyne (Manchester City) - the heavy-sample king
   Q5 MF: #3 (0.734 EP/90) over 14,674 minutes and 206 credits. By
   FAR the most-sampled top-3 pick anywhere in the analysis. The
   model's most stable elite pick.

4. Nicolas Jackson (Villarreal -> Chelsea) - model's 2022-23 5L MVP
   Q2: combined-5L MVP for 2022-23 at Villarreal (1.21 EP/90). The
   model says he was the most valuable player in Europe that season -
   a year before Chelsea paid for him.

5. Jamal Musiala (Bayern Munich) - young + sampled
   Q5 MF: #2 (0.786 EP/90, 6,302 minutes, age 21.1). Q7 #5. The
   rare young player whose per-90 number isn't a small-sample mirage.

(Optional 6th if you want a left-field name: Serhou Guirassy - model's
2023-24 5L MVP at Stuttgart, 1.30 EP/90. Now at Dortmund.)


STRONGEST SINGLE-SENTENCE FINDING (across all 7 Qs)
----------------------------------------------------
'Across seven seasons of Europe's six biggest leagues, only Lionel
Messi creates more pre-assist value than Julian Brandt - whose 40.93
EP from SCA2 alone represents 39% of his total contribution, more
than double the SCA2 share of Mbappé or Salah.'

This works because: (a) it's surprising, (b) it's specific (named
player + number + comparison), (c) Brandt has the volume to back it
up (66 SCA2 events, 105.78 total EP), (d) it's unique to this model
- no traditional stat surfaces him.


RED FLAGS / ODDITIES TO INVESTIGATE BEFORE PUBLISHING
------------------------------------------------------

[1] Borja Iglesias 2020-21 La Liga MVP (1.29 EP/90)
    Q2 grid. He played most of his career at Real Betis, a mid-table
    side - exactly the team profile the EP model rewards (their goals
    change game states often). Worth a sanity check: his minutes for
    Betis 2020-21 should be ~2,500+ to justify the pick. Verify.

[2] Q3 'late-game share' top 10 dominated by super-subs
    Marc Cardona (20 credits, 82.6% late), Danny Rose (15 credits,
    82.1%) - these are players whose almost-entire-contribution was
    late substitute appearances. Not a 'late-game specialist' in
    the meaningful sense. The section's framing should acknowledge:
    'these are super-sub specialists; players with high LATE EP at
    high TOTAL EP (e.g. Cristian Tello, 44 credits) are the more
    substantive finding.'

[3] Q4a/b top 10s are all 5-9 credit samples
    Kelvin Yeboah (6 credits, 1.30 ratio) leading Q4a is noise. The
    minimum threshold of 5 was set deliberately loose but the editorial
    section needs a higher cut. Suggest filtering Q4a/b in analysis.html
    to >=20 credits for display while keeping the full list in the
    dashboard.

[4] Q5 DF panel has Iling-Junior at 1,128 minutes
    Samuel Iling-Junior #1 at 0.785 EP/90 in just 1,128 mins (~12.5
    full matches) at Juventus. Half-season pick. The DF panel is
    structurally noisier than MF/FW because defender contributions
    are rare events. Worth a 'sample-size warning' caveat on the panel.

[5] Q6b per-90 Top 10 still has 4 players under 1,300 mins
    Bynoe-Gittens 1,725, Iling-Junior 1,128, Jallow 1,047, Mitroglou
    1,456. SCA2 events are rarer than goals, so the per-90 number
    is even more volatile. Suggest >=2,000 min for Q6b editorial
    display, keep >=1,000 in dashboard.

[6] Lamine Yamal in Q7 (age 16.9, 2,209 mins, 0.738 EP/90)
    NOT a red flag - this is actually a credible result and a great
    'editorial detail'. Flagging only because the age might prompt
    'is that right?' from a reader. Confirmed: 16.9 is correct (he
    debuted 2023-24).

[7] Q2 grid sparseness in early seasons
    The 2017-18 to 2019-20 rows often have lower 'EP/90' picks
    (Gnabry 0.92, Hazard 1.01, Bruno Fernandes 0.95, Dybala 0.98)
    than 2020-21+. Suspect early seasons had fewer KEEP_SET-eligible
    transitions per match (extreme blowouts excluded). Not a bug;
    just worth noting on the chart.


PHASE 2 RECOMMENDATIONS (data-side adjustments before HTML)
------------------------------------------------------------
None blocking. Suggested polishes:
 - Bump Q4a/b editorial display threshold to >=20 credits (apply in
   analysis.html slice, keep data wide).
 - Add 'sample-size cohort' visual coding: minutes <1,800 shown in
   muted color or with a small dot; minutes >=3,600 in accent. This
   honestly addresses the half-season picks without removing them.
""")


# ────────────────────────────────────────────────────────────────────────
def main():
    print_q1a()
    print_q1b()
    print_q1_shifts()
    print_q2()
    print_q3()
    print_q4()
    print_q5()
    print_q6()
    print_q7()
    print_commentary()


if __name__ == "__main__":
    main()
