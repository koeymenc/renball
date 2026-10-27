"""
build_slides.py — Renball Project 02 slide builder
==================================================

Generates the 16:9 deck for "Not All Goals Are Equal". Every number comes
from ../data/data.json; styling and layouts come from the shared
assets/slides/renball_slide_master.py — never reimplemented here.

Run:
    python code/build_slides.py
"""

from __future__ import annotations

import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPO_ROOT = PROJECT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "assets" / "slides"))

import renball_slide_master as R  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

DATA_JSON = PROJECT_DIR / "data" / "data.json"
OUTPUT_PPTX = PROJECT_DIR / "slides.pptx"


def fx(x: float, d: int = 2) -> str:
    """Half-up on the shortest decimal form — the same rounding as the page (0.955 -> 0.96); true minus sign."""
    s = str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
    return s.replace("-", "−")


def sg(x: float, d: int = 2) -> str:
    return ("+" if x >= 0 else "") + fx(x, d)


def n(x) -> str:
    return f"{x:,}"


def short(season: str) -> str:
    """'2017-2018' -> '2017-18'"""
    return f"{season[:4]}-{season[-2:]}"


# ════════════════════════════════════════════════════════════════════════
# Slides
# ════════════════════════════════════════════════════════════════════════
def slide_title(prs, d):
    R.add_title_slide(prs, title="Not All Goals Are *Equal*.",
                      subtitle="A TIME-AWARE EXPECTED-POINTS MODEL · TOP 5 LEAGUES + EREDIVISIE",
                      date="October 2026", project_num="02")


def slide_tldr(prs, d):
    s, h, gs = d["sample"], d["headline"], d["game_state"]
    op, lv, ps = h["opener_ratio"], gs["level_late"], d["players"]["premium_summary"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "TL;DR", "Three *sentences*")
    rows = [
        ("THE MODEL",
         f"Price every goal by the state it creates minus the state it ends, from {n(s['team_minutes'])} "
         f"team-minutes in {n(s['matches_model'])} matches."),
        ("THE CLOCK",
         f"A go-ahead goal from level is worth {fx(op['late']['ep'])} EP in the last 15, {fx(op['value'])}× the "
         f"first 15 (95% CI {fx(op['lo'])}–{fx(op['hi'])}). Level late, the upside is {fx(lv['ratio'])}× the downside."),
        ("THE PLAYERS",
         f"No \"clutch\" signal: only {ps['ci_above_zero']} of {n(ps['eligible'])} players scored at clearly "
         f"better-than-average times, fewer than chance."),
    ]
    y = R.BODY_TOP
    for label, body in rows:
        R.add_mono_label(sl, R.BODY_LEFT, y, 2.4, 0.3, label, color=R.ACCENT, size=10)
        R.add_text(sl, R.BODY_LEFT + 2.5, y - 0.07, 9.3, 1.3, body, font=R.SERIF, size=20, color=R.TEXT)
        y += 1.6


def slide_context(prs, d):
    h = d["headline"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "THE QUESTION", "Every goal counts as *one*. Should it?")
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP, R.BODY_MAX_W, 0.7,
               "An early opener, a late winner and a consolation at 4–0 down all add one to the scoreboard.",
               font=R.SERIF, size=24, color=R.TEXT, italic=True)
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP + 1.2, 5.8, 3.2,
               "The first nudges the odds. The second nearly settles them. The third changes almost nothing. "
               "A goal's worth depends on the scoreline it changes and on how much time is left to change it back.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)
    R.add_text(sl, R.BODY_LEFT + 6.3, R.BODY_TOP + 1.2, 5.7, 3.2,
               f"So price it: the expected final points of the scoring team just after the goal, minus just "
               f"before it. A late equaliser is worth {fx(h['late_equaliser']['ep'])} EP; a late second goal at "
               f"1–0 only {fx(h['late_cushion']['ep'])}.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)


def slide_data(prs, d):
    dq, s = d["data_quality"], d["sample"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "DATA", "Six leagues, seven *seasons*")
    stats = [(n(s["goals_all"]), "GOALS PRICED"), (n(dq["matches_loaded"]), "MATCHES LOADED"),
             (n(s["matches_model"]), "MATCHES IN THE MODEL"), (n(s["team_minutes"]), "TEAM-MINUTES")]
    x = R.BODY_LEFT
    for value, label in stats:
        R.add_rect(sl, x, R.BODY_TOP, 2.85, 1.6, R.BG_CARD, border=R.BORDER, border_pt=0.75)
        R.add_text(sl, x + 0.2, R.BODY_TOP + 0.15, 2.6, 0.9, value, font=R.SERIF, size=34, color=R.ACCENT)
        R.add_mono_label(sl, x + 0.2, R.BODY_TOP + 1.05, 2.6, 0.3, label, color=R.TEXT_MUTED, size=9)
        x += 3.0
    seasons = d["meta"]["seasons"]
    lines = [
        f"FBref match pages, {seasons[0]} to {seasons[-1]}: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, "
        f"Eredivisie. Shot tables, official scores, per-match minutes and ages.",
        f"Own goals are missing from the shot table: in {n(dq['og_affected'])} matches ({fx(dq['og_affected_pct'], 1)}%) "
        f"the rebuilt score falls short of the official one. They are left out of the value model.",
        f"{n(dq['eredivisie_failed'])} of {n(dq['eredivisie_matches'])} Eredivisie matches have no usable data.",
    ]
    y = R.BODY_TOP + 1.95
    for line in lines:
        R.add_text(sl, R.BODY_LEFT, y, R.BODY_MAX_W, 0.6, line, font=R.SANS, size=13, color=R.TEXT_SECONDARY)
        y += 0.7


def slide_method(prs, d):
    p = d["meta"]["params"]
    R.add_two_column_slide(
        prs, title="Two tables, one *subtraction*",
        left={"label": "STATE VALUE", "title": "What a scoreline is worth",
              "body": "Every minute a team spent at a goal difference in a 15-minute window, averaged over the "
                      "points those teams finished with (3 · win + 1 · draw). 0–0s and goalless spells count.",
              "accent": True},
        right={"label": "GOAL VALUE", "title": "What a goal is worth",
               "body": "The state the goal creates minus the state it ends, in the same window. Time-blind "
                       "version: the same with all minutes pooled."},
        eyebrow="METHOD",
        caption=f"Intervals: {n(p['boot_resamples'])} bootstrap resamples of whole matches within each league · "
                f"fixed seed · cells seen in fewer than {p['sparse_matches']} matches flagged sparse",
    )


def _heat(ax, M, row_labels, col_labels, *, vmax, fmt_cell):
    cmap = LinearSegmentedColormap.from_list("renball", [R.MPL_BG_CARD, R.MPL_ACCENT])
    ax.imshow(np.ma.masked_invalid(M), cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels)
    ax.grid(False)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, fmt_cell(v), ha="center", va="center", fontsize=10,
                    color=R.MPL_BG if v > vmax * 0.6 else R.MPL_TEXT, family="monospace")


def slide_state_values(prs, d):
    sv = d["state_values"]
    rows = [i for i, g in enumerate(sv["gd_range"]) if abs(g) <= 2][::-1]
    M = np.array([[c["ep"] if c else np.nan for c in sv["matrix"][i]] for i in rows])
    fig, ax = R.new_chart(width=11, height=4.4)
    _heat(ax, M, [sv["gd_labels"][i] for i in rows], sv["time_bins"], vmax=3, fmt_cell=lambda v: fx(v))
    ax.set_xlabel("Minute window", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_ylabel("Goal difference", color=R.MPL_TEXT_SEC, fontsize=11)
    st = d["headline"]["states"]
    R.add_chart_slide(prs, "What each scoreline is *worth*", fig, eyebrow="STATE VALUES",
                      caption=f"Expected final points by goal difference and window. One up: {fx(st['lead_early'])} "
                              f"early, {fx(st['lead_late'])} late. Level: {fx(st['level_early'])} → "
                              f"{fx(st['level_late'])}.")


def slide_goal_values(prs, d):
    gv = d["goal_values"]
    idx = [i for i, t in enumerate(gv["transitions"]) if -2 <= t["gd_before"] <= 2][::-1]
    M = np.array([[c["ep"] if c and c.get("ep") is not None else np.nan for c in gv["matrix"][i]] for i in idx])
    fig, ax = R.new_chart(width=11, height=4.4)
    _heat(ax, M, [gv["transitions"][i]["label"] for i in idx], gv["time_bins"], vmax=1.6, fmt_cell=lambda v: fx(v))
    ax.set_xlabel("Minute window", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_ylabel("Goal (scoring team)", color=R.MPL_TEXT_SEC, fontsize=11)
    b = d["headline"]["best_cell"]
    R.add_chart_slide(prs, "The value of a goal, by *minute*", fig, eyebrow="GOAL VALUES",
                      caption=f"State after minus state before. Brightest: {b['transition']} in the last 15 "
                              f"({fx(b['ep'])} EP, {n(b['goals'])} goals). Leads stretched late are worth little.")


def slide_opener(prs, d):
    h = d["headline"]
    ob, op, eq = h["opener_by_bin"], h["opener_ratio"], h["late_equaliser"]
    gv = d["goal_values"]
    eq_row = gv["matrix"][[t["gd_before"] for t in gv["transitions"]].index(-1)]
    bins = d["meta"]["time_bins"]
    fig, ax = R.new_chart(width=11, height=4.3)
    x = np.arange(len(bins))
    w = 0.38
    for off, cells, color, label in ((-w / 2, ob, R.MPL_ACCENT, "Go-ahead from level (0→1)"),
                                     (w / 2, eq_row, R.MPL_SECONDARY, "Equaliser (−1→0)")):
        vals = [c["ep"] for c in cells]
        ax.bar(x + off, vals, w, color=color, label=label, edgecolor="none")
        for xi, c in zip(x + off, cells):
            ax.plot([xi, xi], [c["lo"], c["hi"]], color=R.MPL_TEXT, linewidth=1.2)
    for xi, c in zip(x - w / 2, ob):
        ax.text(xi, c["hi"] + 0.03, fx(c["ep"]), ha="center", color=R.MPL_TEXT, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(bins)
    ax.set_ylim(0, 1.8)
    ax.set_ylabel("EP per goal", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.legend(frameon=False, labelcolor=R.MPL_TEXT_SEC, fontsize=10, loc="upper left")
    R.add_chart_slide(prs, f"The opener: *{fx(op['value'])}×* late vs early", fig, eyebrow="HEADLINE",
                      caption=f"0→1: {fx(op['early']['ep'])} EP in the first 15, {fx(op['late']['ep'])} in the last 15 "
                              f"(ratio 95% CI {fx(op['lo'])}–{fx(op['hi'])}). Late equaliser {fx(eq['ep'])} EP. "
                              f"Whiskers: 95% intervals.")


def slide_game_state(prs, d):
    gs = d["game_state"]
    bins = d["meta"]["time_bins"]
    rows = []
    for r in gs["rows"]:
        rows.append([r["label"]] + [f"{fx(c['ratio'])}×" for c in r["bins"]])
        rows.append(["   for / against (EP)"] + [f"{fx(c['up'])} / {fx(c['down'])}" for c in r["bins"]])
    lv = gs["level_late"]
    R.add_table_slide(prs, "Next goal: *upside ÷ downside*", ["SCORE"] + bins, rows, eyebrow="GAME MANAGEMENT",
                      col_widths=[2.9] + [1.55] * 6,
                      caption=f"Value of scoring the next goal ÷ cost of conceding it. Level in the last 15: a goal "
                              f"for is worth {fx(lv['up'])} EP, a goal against costs {fx(lv['down'])}: {fx(lv['ratio'])}× (95% CI "
                              f"{fx(lv['lo'])}–{fx(lv['hi'])}). Prices, not a test of tactics.")


def slide_ep_by_bin(prs, d):
    h = d["headline"]
    eb, tot = h["ep_by_bin"], h["ep_last_vs_first_bin"]
    fig, ax = R.new_chart(width=11, height=4.3)
    vals = [b["total_ep"] for b in eb]
    bars = ax.bar([b["bin"] for b in eb], vals, width=0.6, edgecolor="none",
                  color=[R.MPL_ACCENT if i == len(eb) - 1 else R.MPL_TEXT_SEC for i in range(len(eb))])
    for bar, b in zip(bars, eb):
        ax.text(bar.get_x() + bar.get_width() / 2, b["total_ep"] + 80, f"{n(round(b['total_ep']))}",
                ha="center", color=R.MPL_TEXT, fontsize=10)
    ax.set_ylabel("Total EP delivered", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_ylim(0, max(vals) * 1.15)
    R.add_chart_slide(prs, "Where the points get *cashed in*", fig, eyebrow="BY WINDOW",
                      caption=f"Every goal at its own value. Last 15 vs first 15: {fx(tot['value'])}× (95% CI "
                              f"{fx(tot['lo'])}–{fx(tot['hi'])}): {n(eb[-1]['goals'])} goals against {n(eb[0]['goals'])}.")


def slide_calibration(prs, d):
    c = d["calibration"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "OUT OF SAMPLE", "It predicts seasons it never *saw*")
    h = R.CAPTION_TOP - R.CAPTION_GAP - R.BODY_TOP
    fig, ax = R.new_chart(width=6.0, height=h)
    x = np.arange(len(c["by_bin"]))
    w = 0.27
    for off, key, color, label in ((-w, "timed", R.MPL_ACCENT, "Time-aware"), (0, "untimed", R.MPL_SECONDARY, "Time-blind"),
                                   (w, "base", R.MPL_TEXT_MUTED, "No score info")):
        ax.bar(x + off, [b[key] for b in c["by_bin"]], w, color=color, label=label, edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels([b["bin"] for b in c["by_bin"]], fontsize=9)
    ax.set_ylabel("Brier score (lower = better)", color=R.MPL_TEXT_SEC, fontsize=10)
    ax.set_ylim(0, 0.8)
    ax.legend(frameon=False, labelcolor=R.MPL_TEXT_SEC, fontsize=9, ncol=3, loc="upper center")
    R.add_chart_picture(sl, fig, R.BODY_LEFT, R.BODY_TOP, 6.0, h)
    fig2, ax2 = R.new_chart(width=5.9, height=h)
    rel = c["reliability"]
    ax2.plot([0, 3], [0, 3], color=R.MPL_TEXT_MUTED, linestyle=(0, (4, 4)), linewidth=1)
    ax2.scatter([b["predicted"] for b in rel], [b["observed"] for b in rel],
                s=[20 + b["minutes"] / 1500 for b in rel], color=R.MPL_ACCENT, zorder=3)
    ax2.set_xlim(0, 3); ax2.set_ylim(0, 3)
    ax2.set_xlabel("Predicted EP", color=R.MPL_TEXT_SEC, fontsize=10)
    ax2.set_ylabel("Points actually won", color=R.MPL_TEXT_SEC, fontsize=10)
    R.add_chart_picture(sl, fig2, R.BODY_LEFT + 6.4, R.BODY_TOP, 5.9, h)
    R.add_text(sl, R.BODY_LEFT, R.CAPTION_TOP, R.BODY_MAX_W, 0.3,
               f"Fit on {c['train_seasons'][0]} to {c['train_seasons'][-1]}; predict {n(c['test_matches'])} matches in "
               f"{' and '.join(c['test_seasons'])}. Brier {fx(c['brier']['timed'], 3)} vs {fx(c['brier']['untimed'], 3)} "
               f"time-blind; largest calibration gap {fx(c['reliability_max_gap'])} EP.",
               font=R.MONO, size=10, color=R.TEXT_MUTED)


def slide_robustness(prs, d):
    rb, s, h = d["robustness"], d["sample"], d["headline"]
    op = h["opener_ratio"]
    rows = [["Primary model", n(s["matches_model"]), fx(rb["primary"]["opener_late"]), fx(rb["primary"]["opener_early"]),
             f"{fx(rb['primary']['ratio'])}×", f"{fx(op['lo'])}–{fx(op['hi'])}"],
            ["Own-goal matches put back", n(rb["inclusive"]["matches"]), fx(rb["inclusive"]["opener_late"]),
             fx(rb["inclusive"]["opener_early"]), f"{fx(rb['inclusive']['ratio'])}×", "n/a"],
            [f"Fit on {short(rb['train']['seasons'][0])} to {short(rb['train']['seasons'][-1])}", n(rb["train"]["matches"]),
             fx(rb["train"]["opener_late"]), fx(rb["train"]["opener_early"]), f"{fx(rb['train']['ratio'])}×", "n/a"],
            [f"Fit on {short(rb['test']['seasons'][0])} to {short(rb['test']['seasons'][-1])}", n(rb["test"]["matches"]),
             fx(rb["test"]["opener_late"]), fx(rb["test"]["opener_early"]), f"{fx(rb['test']['ratio'])}×", "n/a"]]
    rows += [[x["label"], n(x["matches"]), fx(x["opener_late"]), fx(x["opener_early"]), f"{fx(x['ratio'])}×",
              f"{fx(x['lo'])}–{fx(x['hi'])}"] for x in rb["by_league"]]
    R.add_table_slide(prs, "Does it *hold up*?", ["VERSION", "MATCHES", "OPENER LATE", "OPENER EARLY", "RATIO", "95% CI"],
                      rows, eyebrow="ROBUSTNESS", highlight_first_row=True, col_widths=[3.9, 1.6, 1.8, 1.8, 1.4, 1.8],
                      caption=f"Late vs early go-ahead goal from level. League range {fx(rb['league_ratio_min'])}× to "
                              f"{fx(rb['league_ratio_max'])}×; league differences inside it not tested.")


def _forest(prs, title, eyebrow, rows, xlabel, caption, *, zero=False, decimals=2):
    fig, ax = R.new_chart(width=11, height=4.5)
    rows = rows[::-1]
    ys = list(range(len(rows)))
    if zero:
        ax.axvline(0, color=R.MPL_TEXT_MUTED, linestyle=(0, (4, 4)), linewidth=1)
    for y, (label, v, lo, hi) in zip(ys, rows):
        top = y == len(rows) - 1
        ax.plot([lo, hi], [y, y], color=R.MPL_ACCENT if top else R.MPL_TEXT_SEC, linewidth=3 if top else 2,
                solid_capstyle="butt")
        ax.plot([v], [y], "o", color=R.MPL_ACCENT if top else R.MPL_TEXT, markersize=7)
        ax.text(hi, y + 0.28, f"{sg(v, decimals) if zero else fx(v, decimals)}", ha="right",
                color=R.MPL_TEXT_SEC, fontsize=8)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel, color=R.MPL_TEXT_SEC, fontsize=10)
    R.add_chart_slide(prs, title, fig, eyebrow=eyebrow, caption=caption)


def slide_top_ep(prs, d):
    pl = d["players"]
    rows = [(f"{p['player']} · {p['team']}", p["ep"], p["ep_lo"], p["ep_hi"]) for p in pl["top_ep"]]
    _forest(prs, "Top 10: a *statistical tie* at the top", "EP COLLECTED", rows, "EP collected (goals + assists)",
            f"Top five within {fx(pl['top_ep_summary']['top5_spread'])} EP, intervals overlapping. Goals + SCA1, once "
            f"per player per goal. Bars: 95% intervals.")


def slide_premium(prs, d):
    pl = d["players"]
    ps = pl["premium_summary"]
    rows = [(f"{p['player']} · {p['team']}", p["premium"], p["premium_lo"], p["premium_hi"]) for p in pl["top_premium"]]
    _forest(prs, "Clutch? Not beyond *chance*", "TIMING PREMIUM", rows, "EP above the same goals at average times",
            f"Only {ps['ci_above_zero']} of {n(ps['eligible'])} players ({ps['min_involvements']}+ involvements) clearly "
            f"above zero; chance alone gives ~{ps['expected_by_chance_each_side']}.", zero=True)


def slide_per90(prs, d):
    pl = d["players"]
    ps = pl["per90_summary"]
    rows = [(f"{p['player']} · {p['team']}", p["p90"], p["p90_lo"], p["p90_hi"]) for p in pl["top_per90"]]
    _forest(prs, "EP per 90: hot streaks *float up*", "RATE", rows, "EP per 90 minutes",
            f"At least {n(ps['min_minutes'])} minutes. {ps['short_in_top10']} of the top ten played under "
            f"{n(ps['short_minutes'])} minutes; their intervals are the widest.", decimals=3)


def slide_takeaways(prs, d):
    R.add_takeaways_slide(prs, d["takeaways"], show_basis=True)


def slide_limitations(prs, d):
    dq, rb = d["data_quality"], d["robustness"]
    R.add_bullet_slide(
        prs, "What this *can't* tell you",
        bullets=[
            "Prices, not causes: a goal's value is measured on what teams went on to do, not isolated from red cards or subs.",
            "No team strength: a 1–0 lead is priced the same for favourite and underdog.",
            f"Own goals: {n(dq['og_affected'])} matches left out of the model; including them moves the headline "
            f"from {fx(rb['primary']['ratio'])}× to {fx(rb['inclusive']['ratio'])}×.",
            "Every goal counts as one (no xG); \"assist\" is FBref's SCA1; 15-minute windows.",
            "Timing premiums and per-90 rates are not tested for repeatability.",
        ],
        eyebrow="LIMITATIONS",
    )


def slide_conclusion(prs, d):
    op, lv = d["headline"]["opener_ratio"], d["game_state"]["level_late"]
    sl = R.add_blank_slide(prs)
    R.add_section_header(sl, "CONCLUSION", "What this *changes*")
    tb = R.textbox(sl, R.BODY_LEFT, R.BODY_TOP, R.BODY_MAX_W, 1.0)
    p = tb.text_frame.paragraphs[0]
    R.add_run(p, "The clock changes the price. ", font=R.SERIF, size=32, color=R.TEXT)
    R.add_run(p, "Clutch doesn't.", font=R.SERIF, size=32, color=R.ACCENT, italic=True)
    R.add_text(sl, R.BODY_LEFT, R.BODY_TOP + 1.2, R.BODY_MAX_W, 2.0,
               f"The same go-ahead goal from level is worth {fx(op['value'])}× as much in the last 15 minutes as in the "
               f"first, in every league and in seasons the model never saw. That makes the table usable for game "
               f"management: level late, a goal for is worth {fx(lv['ratio'])}× what a goal against costs. It doesn't "
               "single out clutch players: compared with the same scorelines at average times, almost nobody's timing "
               "stands out from chance.",
               font=R.SANS, size=15, color=R.TEXT_SECONDARY)


def slide_sources(prs, d):
    R.add_closing_slide(
        prs, headline="Thanks for reading.", url="renball.com",
        project_path="/projects/02-points-by-gamestate/",
        lines=["→ methodology      the model, the bootstrap, the held-out test, limitations",
               "→ dashboard        every player, state and goal value by league and season",
               "→ code/            matches.py · value_model.py · build.py"],
    )


def main() -> None:
    d = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    prs = R.create_deck()
    for fn in (slide_title, slide_tldr, slide_context, slide_data, slide_method, slide_state_values,
               slide_goal_values, slide_opener, slide_game_state, slide_ep_by_bin, slide_calibration,
               slide_robustness, slide_top_ep, slide_premium, slide_per90, slide_takeaways,
               slide_limitations, slide_conclusion, slide_sources):
        fn(prs, d)
    R.finalize_deck(prs)
    prs.save(OUTPUT_PPTX)
    print(f"[OK] Wrote {OUTPUT_PPTX.relative_to(PROJECT_DIR)} ({OUTPUT_PPTX.stat().st_size / 1024:.1f} KB, "
          f"{len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
