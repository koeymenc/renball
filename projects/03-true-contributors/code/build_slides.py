"""
build_slides.py — Renball Project 03 slide builder
==================================================

Generates the 16:9 deck for "The True Contributors". Every number comes from
../data/data.json; styling and layouts come from the shared
assets/slides/renball_slide_master.py — never reimplemented here.

Run:
    python code/build_slides.py
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "assets" / "slides"))

import renball_slide_master as R  # noqa: E402

DATA_JSON = PROJECT_DIR / "data" / "data.json"
OUTPUT_PPTX = PROJECT_DIR / "slides.pptx"


def fx(x: float, d: int = 2) -> str:
    """Half-up on the shortest decimal form, the same rounding as the page; true minus sign."""
    s = str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    return s.replace("-", "−")


def n(x) -> str:
    return f"{int(x):,}"


# ════════════════════════════════════════════════════════════════════════
# Slides
# ════════════════════════════════════════════════════════════════════════
def slide_title(prs, d):
    R.add_title_slide(prs, title="The True *Contributors*.",
                      subtitle="WHO ACTUALLY MOVES THE TABLE? · EXPECTED POINTS PER 90 WITH HONEST RANKS",
                      date="May 2026", project_num="03")


def slide_tldr(prs, d):
    b, rep, aw = d["board"], d["repeatability"], d["awards"]
    t = b["top"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "TL;DR", "Three *sentences*")
    rows = [
        ("THE BOARD",
         f"{t[0]['player']} ({fx(t[0]['theta'])} EP per 90) and {t[1]['player']} ({fx(t[1]['theta'])}) are the only "
         f"players sure of a top-10 place. Number 3 could rank anywhere from {t[2]['rank_lo']} to {t[2]['rank_hi']}."),
        ("WHAT REPEATS",
         f"EP per 90 carries over from season to season (r = {fx(rep['p90']['r'])}); how decisive a player's goals "
         f"are barely does (r = {fx(rep['ep_per_inv']['r'])})."),
        ("REALITY CHECK",
         f"The model names the actual award winner in {aw['exact']} of {aw['eligible_winners']} league-seasons "
         f"(chance: {fx(aw['chance_exact'], 1)}); a goals + assists count names {aw['ga_exact']}."),
    ]
    y = R.BODY_TOP
    for label, body in rows:
        R.add_mono_label(sl, R.BODY_LEFT, y, 2.4, 0.3, label, color=R.ACCENT, size=10)
        R.add_text(sl, R.BODY_LEFT + 2.5, y - 0.07, 9.3, 1.3, body, font=R.SERIF, size=20, color=R.TEXT)
        y += 1.6


def slide_framework(prs, d):
    fw, q = d["framework"], d["quality"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "THE FRAMEWORK", "Price the goal, then *share* it")
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP, R.BODY_MAX_W, 0.7,
               "Goals win points, but not the same number of points, and a goal is rarely one player's work.",
               font=R.SERIF, size=24, color=R.TEXT, italic=True)
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP + 1.2, 5.8, 3.4,
               f"The price comes from Project 02: the expected final points just after a goal minus just before, "
               f"from every minute of {n(fw['matches_model'])} matches. A go-ahead goal from level is worth "
               f"{fx(fw['opener_early'], 3)} EP in the first 15 minutes and {fx(fw['opener_late'], 3)} in the last 15.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)
    R.add_text(sl, R.BODY_LEFT + 6.3, R.BODY_TOP + 1.2, 5.7, 3.4,
               f"The credit goes to the scorer, SCA1 (the action before the shot) and SCA2 (the action before that), "
               f"each at the goal's full value, once per player per goal: {n(q['collapsed'])} role credits merge "
               f"into {n(q['credits'])} credits.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)


def slide_data(prs, d):
    q, b = d["quality"], d["board"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "DATA", "Five leagues, seven *seasons*")
    stats = [(n(q["goals"]), "GOALS PRICED"), (n(q["matches"]), "MATCHES"),
             (n(q["players_eligible"]), f"PLAYERS · {n(b['min_minutes'])}+ MIN"), (f"{fx(q['sca2_pct'], 1)}%", "GOALS WITH SCA2")]
    x = R.BODY_LEFT
    for value, label in stats:
        R.add_rect(sl, x, R.BODY_TOP, 2.85, 1.6, R.BG_CARD, border=R.BORDER, border_pt=0.75)
        R.add_text(sl, x + 0.2, R.BODY_TOP + 0.15, 2.6, 0.9, value, font=R.SERIF, size=34, color=R.ACCENT)
        R.add_mono_label(sl, x + 0.2, R.BODY_TOP + 1.05, 2.6, 0.3, label, color=R.TEXT_MUTED, size=9)
        x += 3.0
    lines = [
        f"FBref match pages, {q['first_season']} to {q['last_season']}: Premier League, La Liga, Serie A, Bundesliga, "
        f"Ligue 1. Shot tables, official scores, every player's minutes, position and age per match.",
        f"The data end in {q['last_season']}: the SCA2 data end there because the source discontinued them.",
        f"Players told apart by birth date ({q['namesakes']} shared names); minutes from the same matches as the goals.",
    ]
    y = R.BODY_TOP + 1.95
    for line in lines:
        R.add_text(sl, R.BODY_LEFT, y, R.BODY_MAX_W, 0.6, line, font=R.SANS, size=13, color=R.TEXT_SECONDARY)
        y += 0.7


def slide_method(prs, d):
    pa, p = d["board"]["pull_at"], d["meta"]["params"]
    R.add_two_column_slide(
        prs, title="Shrink the noise, then *rank*",
        left={"label": "ADJUSTED RATE", "title": "Pulled toward the position average",
              "body": f"EP per 90 is noisy over few minutes. Each rate is pulled toward its position's average, "
                      f"more when minutes are few: a forward with {n(pa[0]['minutes'])} minutes "
                      f"{fx(pa[0]['pull_pct'], 0)}%, with {n(pa[2]['minutes'])} minutes {fx(pa[2]['pull_pct'], 0)}%.",
              "accent": True},
        right={"label": "PLAUSIBLE RANK", "title": "A range, not a place",
               "body": f"Every player's adjusted rate is drawn {n(p['posterior_draws'])} times with its "
                       f"uncertainty and ranked each time. The plausible rank is where he lands 95% of the time."},
        eyebrow="METHOD",
        caption=f"Empirical Bayes by position (DerSimonian–Laird priors) · measured ranges from Project 02's "
                f"{n(p['boot_resamples'])} match-bootstrap resamples · fixed seed",
    )


def slide_board_chart(prs, d):
    top = d["board"]["top"][:15]
    fig, ax = R.new_chart(width=11, height=4.5)
    rows = top[::-1]
    ys = range(len(rows))
    colors = [R.MPL_ACCENT if (p.get("p_top10_pct") or 0) >= 95 else R.MPL_TEXT_MUTED for p in rows]
    ax.barh(list(ys), [p["theta"] for p in rows], color=colors, height=0.62, edgecolor="none")
    for y, p in zip(ys, rows):
        ax.plot([p["theta_lo"], p["theta_hi"]], [y, y], color=R.MPL_TEXT, linewidth=1.2)
        ax.text(p["theta_hi"] + 0.012, y, fx(p["theta"]), va="center", color=R.MPL_TEXT, fontsize=9)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([f"{p['player']} · {p['team']}" for p in rows], fontsize=9)
    ax.set_xlim(0, 1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("EP per 90, adjusted", color=R.MPL_TEXT_SEC, fontsize=10)
    b = d["board"]
    R.add_chart_slide(prs, "Two players are *sure*. The rest is a shortlist.", fig, eyebrow="HEADLINE",
                      caption=f"{n(b['eligible'])} players with {n(b['min_minutes'])}+ minutes. Green: top-10 chance of "
                              f"95% or more. Whisker: 95% interval of the adjusted rate.")


def slide_board_table(prs, d):
    top = d["board"]["top"][:10]
    rows = [[str(p["rank"]), p["player"], p["team"], n(p["minutes"]), fx(p["p90"], 3), fx(p["theta"], 3),
             f"{p['rank_lo']}–{p['rank_hi']}", f"{fx(p['p_top10_pct'], 0)}%"] for p in top]
    R.add_table_slide(prs, "The top 10, with *plausible ranks*",
                      ["#", "PLAYER", "TEAM", "MINUTES", "MEASURED", "ADJUSTED", "PLAUSIBLE RANK", "TOP-10 CHANCE"],
                      rows, eyebrow="THE BOARD", col_widths=[0.6, 2.6, 2.0, 1.3, 1.4, 1.4, 1.7, 1.6],
                      caption="EP per 90 measured and adjusted toward the position average. Plausible rank: 95% of "
                              "4,000 joint draws. Top-10 chance: share of draws in the top 10.")


def slide_raw(prs, d):
    raw = d["board"]["raw_top"]
    gone = set(d["board"]["raw_top10_dropped_names"])
    fig, ax = R.new_chart(width=11, height=4.4)
    rows = raw[::-1]
    for y, p in enumerate(rows):
        c = R.MPL_TEXT_MUTED if p["player"] in gone else R.MPL_ACCENT
        ax.plot([p["theta"], p["p90"]], [y, y], color=R.MPL_TEXT_MUTED, linewidth=2)
        ax.plot([p["p90"]], [y], "o", markerfacecolor="none", markeredgecolor=R.MPL_TEXT_SEC, markersize=8)
        ax.plot([p["theta"]], [y], "o", color=c, markersize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{p['player']} · {n(p['minutes'])} min" for p in rows], fontsize=9)
    ax.set_xlim(0.4, 1.0)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("EP per 90: open circle measured, dot adjusted", color=R.MPL_TEXT_SEC, fontsize=10)
    b = d["board"]
    R.add_chart_slide(prs, "The raw top 10 *misleads*", fig, eyebrow="SHRINKAGE",
                      caption=f"{b['raw_top10_dropped']} of the raw top 10 leave the adjusted top 10 (grey): all short "
                              f"careers. {raw[2]['player']}'s {fx(raw[2]['p90'], 3)} over {n(raw[2]['minutes'])} minutes "
                              f"is pulled to {fx(raw[2]['theta'], 3)}.")


def slide_rules(prs, d):
    cr = d["credit_rules"]
    w = cr["weighted"]
    rows = [["Every role a credit (old rule)", str(cr["roles"]["top10_overlap"]), fx(cr["roles"]["rank_corr"], 3),
             cr["roles"]["leader"]],
            ["40/35/25 split", str(w["top10_overlap"]), fx(w["rank_corr"], 3), w["leader"]]]
    R.add_table_slide(prs, "The credit rule barely *matters*", ["RULE VS FULL CREDIT", "TOP-10 OVERLAP",
                                                                 "RANK CORRELATION", "LEADER"],
                      rows, eyebrow="ROBUSTNESS", col_widths=[4.4, 2.2, 2.6, 3.0],
                      caption=f"The split favours finishers: {w['biggest_riser']['player']} {w['biggest_riser']['rank_full']} → "
                              f"{w['biggest_riser']['rank_alt']}, {w['biggest_faller']['player']} "
                              f"{w['biggest_faller']['rank_full']} → {w['biggest_faller']['rank_alt']}.")


def slide_repeat(prs, d):
    rep = d["repeatability"]
    keys = ["inv_p90", "p90", "sca2_share", "ep_per_inv"]
    fig, ax = R.new_chart(width=11, height=4.2)
    rows = keys[::-1]
    for y, k in enumerate(rows):
        x = rep[k]
        c = R.MPL_TEXT_MUTED if k == "ep_per_inv" else R.MPL_ACCENT
        ax.plot([x["lo"], x["hi"]], [y, y], color=R.MPL_TEXT_SEC, linewidth=6, solid_capstyle="butt", alpha=0.6)
        ax.plot([x["r"]], [y], "o", color=c, markersize=10)
        ax.text(x["r"], y + 0.25, f"r = {fx(x['r'])}", ha="center", color=R.MPL_TEXT, fontsize=10)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([rep[k]["label"] for k in rows], fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Correlation with the next season", color=R.MPL_TEXT_SEC, fontsize=10)
    R.add_chart_slide(prs, "Volume repeats. Decisiveness *doesn't*.", fig, eyebrow="SKILL OR NOISE",
                      caption=f"Consecutive seasons, top 5 leagues. EP per 90: r = {fx(rep['p90']['r'])} "
                              f"({n(rep['p90']['pairs'])} pairs); EP per involvement: {fx(rep['ep_per_inv']['r'])}. "
                              f"Lines: 95% intervals.")


def slide_awards(prs, d):
    aw = d["awards"]
    seasons = sorted({c["season_label"] for c in aw["grid"]})
    leagues = []
    for c in aw["grid"]:
        if c["league"] not in leagues:
            leagues.append(c["league"])

    def cell(c):
        last = c["pick"].split(" ")[-1]
        if not c["winner"]:
            return f"{last} · no award"
        if c.get("winner_rank") is None:
            return f"{last} · GK winner"
        return f"{last} · won" if c["winner_rank"] == 1 else f"{last} · #{c['winner_rank']}"

    rows = []
    for lg in leagues:
        rows.append([lg] + [cell(next(c for c in aw["grid"] if c["league"] == lg and c["season_label"] == se))
                            for se in seasons])
    R.add_table_slide(prs, "The model's pick vs the *award*", ["LEAGUE"] + seasons, rows, eyebrow="REALITY CHECK",
                      col_widths=[1.9] + [1.45] * len(seasons),
                      caption=f"Pick (surname) · won: the pick won the award · #: the actual winner's rank on the model's list. "
                              f"{aw['exact']} of {aw['eligible_winners']} named; top 3 in {aw['top3']}; chance "
                              f"{fx(aw['chance_exact'], 1)}; goals + assists leader {aw['ga_exact']}.")


def slide_sca2(prs, d):
    s2 = d["sca2"]
    top = s2["top"][:10]
    fig, ax = R.new_chart(width=11, height=4.4)
    rows = top[::-1]
    ax.barh(range(len(rows)), [p["ep_sca2"] for p in rows], color=R.MPL_SECONDARY, height=0.6, edgecolor="none")
    for y, p in enumerate(rows):
        ax.plot([p["ep_sca2_lo"], p["ep_sca2_hi"]], [y, y], color=R.MPL_TEXT, linewidth=1.2)
        ax.text(p["ep_sca2_hi"] + 0.8, y, f"{fx(p['ep_sca2'], 1)} · {fx(p['share_sca2_pct'], 0)}% of his EP",
                va="center", color=R.MPL_TEXT, fontsize=9)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{p['player']} · {p['team']}" for p in rows], fontsize=9)
    ax.set_xlim(0, 95)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("EP from SCA2 credits (the pass before the assist)", color=R.MPL_TEXT_SEC, fontsize=10)
    br = top[1]
    R.add_chart_slide(prs, "The hidden *architects*", fig, eyebrow="SCA2",
                      caption=f"{br['player']} is second with {fx(br['ep_sca2'])} EP from SCA2 alone, but his plausible "
                              f"rank runs from {br['rank_lo']} to {br['rank_hi']}. Roles counted separately; whiskers: 95%.")


def slide_eff(prs, d):
    ef = d["efficiency"]
    rows = (ef["top"][:6] + ef["bottom"])[::-1]
    fig, ax = R.new_chart(width=11, height=4.4)
    ax.axvline(ef["avg"], color=R.MPL_TEXT_MUTED, linestyle=(0, (4, 4)), linewidth=1)
    n_bottom = len(ef["bottom"])
    for y, p in enumerate(rows):
        c = R.MPL_TEXT_SEC if y < n_bottom else R.MPL_ACCENT
        ax.plot([p["lo"], p["hi"]], [y, y], color=c, linewidth=3, solid_capstyle="butt", alpha=0.7)
        ax.plot([p["ep_per_inv"]], [y], "o", color=c, markersize=7)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{p['player']} · {p['team']}" for p in rows], fontsize=9)
    ax.set_xlim(0.3, 1.1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("EP per involvement (dashed: the average credit)", color=R.MPL_TEXT_SEC, fontsize=10)
    R.add_chart_slide(prs, "Decisive goals describe the *team*", fig, eyebrow="EP PER INVOLVEMENT",
                      caption=f"Average credit {fx(ef['avg'], 3)} EP. {ef['above']} players clearly above, {ef['below']} "
                              f"below (chance: ~{ef['chance_each_side']} each). The lowest all played for "
                              f"{', '.join(ef['bottom_teams'][:-1])} or {ef['bottom_teams'][-1]}.")


def slide_positions(prs, d):
    pos = d["positions"]
    rows = []
    for i in range(5):
        row = [str(i + 1)]
        for p in ("FW", "MF", "DF"):
            x = pos[p][i]
            row += [x["player"], fx(x["theta"], 3)]
        rows.append(row)
    b = d["board"]
    R.add_table_slide(prs, "Best by *position*", ["#", "FORWARD", "ADJ.", "MIDFIELDER", "ADJ.", "DEFENDER", "ADJ."],
                      rows, eyebrow="POSITIONS", col_widths=[0.5, 2.7, 1.0, 2.7, 1.0, 2.7, 1.0],
                      caption=f"Each pulled toward its own position's average (forwards {fx(b['priors']['FW']['mu'], 3)}, "
                              f"midfielders {fx(b['priors']['MF']['mu'], 3)}, defenders {fx(b['priors']['DF']['mu'], 3)}). "
                              f"Goalkeepers left out: best {fx(b['gk_max_theta'], 3)}.")


def slide_young(prs, d):
    y = d["young"]
    rows = [[str(i + 1), p["player"], p["team"], str(int(p["age_end"])), n(p["minutes"]), fx(p["p90"], 3),
             fx(p["theta"], 3), str(p["rank"])] for i, p in enumerate(y["rows"][:8])]
    R.add_table_slide(prs, "Young players to *watch*", ["#", "PLAYER", "TEAM", "AGE", "MINUTES", "MEASURED", "ADJUSTED",
                                                        "OVERALL RANK"],
                      rows, eyebrow="23 OR UNDER", col_widths=[0.5, 2.8, 2.0, 0.9, 1.4, 1.5, 1.5, 1.8],
                      caption=f"Aged {y['max_age']} or under on 30 June 2024 (end of the data), {n(d['board']['min_minutes'])}+ "
                              f"minutes: {n(y['eligible'])} players. Short careers are pulled hardest.")


def slide_takeaways(prs, d):
    R.add_takeaways_slide(prs, d["takeaways"], show_basis=True)


def slide_limitations(prs, d):
    q = d["quality"]
    R.add_bullet_slide(
        prs, "What this *can't* tell you",
        bullets=[
            "Prices, not causes: a goal's value says how much it mattered, not how hard it was.",
            "Three roles only: defending, pressing and off-ball runs earn nothing; keepers and defenders are undervalued.",
            "No team or league adjustment: players at high-scoring clubs get more involvements.",
            f"SCA2 missing for {fx(q['sca2_missing_pct'], 1)}% of goals; the data end in {q['last_season']} (source discontinued).",
            "A normal prior pulls true outliers in too hard; plausible ranks ignore shared price uncertainty.",
        ],
        eyebrow="LIMITATIONS",
    )


def slide_conclusion(prs, d):
    t = d["board"]["top"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "CONCLUSION", "What this *changes*")
    tb = R.textbox(sl, R.BODY_LEFT, R.BODY_TOP, R.BODY_MAX_W, 1.0)
    p = tb.text_frame.paragraphs[0]
    R.add_run(p, "Two certainties. ", font=R.SERIF, size=32, color=R.TEXT)
    R.add_run(p, "Then a shortlist.", font=R.SERIF, size=32, color=R.ACCENT, italic=True)
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP + 1.2, R.BODY_MAX_W, 2.2,
               f"{t[0]['player']} and {t[1]['player']} are clear of everyone at {fx(t[0]['theta'])} and "
               f"{fx(t[1]['theta'])} EP per 90. Below them, ranks are ranges. Short careers inflate raw per-90s, the "
               "volume of a player's involvement repeats while the decisiveness of his goals does not, and award "
               "voters follow the box score. For a club, the useful number is the adjusted rate with its plausible rank.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)


def slide_sources(prs, d):
    R.add_closing_slide(
        prs, headline="Thanks for reading.", url="renball.com",
        project_path="/projects/03-true-contributors/",
        lines=["→ methodology      the shrinkage, the rank intervals, the award check",
               "→ dashboard        every player and player-season, with intervals",
               "→ code/            players.py · shrink.py · build.py"],
    )


def main() -> None:
    d = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    prs = R.create_deck()
    for fn in (slide_title, slide_tldr, slide_framework, slide_data, slide_method, slide_board_chart,
               slide_board_table, slide_raw, slide_rules, slide_repeat, slide_awards, slide_sca2, slide_eff,
               slide_positions, slide_young, slide_takeaways, slide_limitations, slide_conclusion, slide_sources):
        fn(prs, d)
    R.finalize_deck(prs)
    prs.save(OUTPUT_PPTX)
    print(f"[OK] Wrote {OUTPUT_PPTX.relative_to(PROJECT_DIR)} ({OUTPUT_PPTX.stat().st_size / 1024:.1f} KB, "
          f"{len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
