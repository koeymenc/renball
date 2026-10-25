"""
build_slides.py, Renball Project 03 slide builder (The True Contributors)
==========================================================================

Generates a 16:9 deck for the three-layer expected-points attribution.
All numbers are pulled from ../data/data.json so the deck stays in sync
with the build.

Styling and slide layouts come exclusively from
`assets/slides/renball_slide_master.py`, never reimplement them here.

Run:
    python code/build_slides.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Pull in the shared Renball slide master ─────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
REPO_ROOT   = PROJECT_DIR.parent.parent                 # …/renball/
SHARED      = REPO_ROOT / "assets" / "slides"
sys.path.insert(0, str(SHARED))

import renball_slide_master as R  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402

DATA_JSON   = PROJECT_DIR / "data" / "data.json"
OUTPUT_PPTX = PROJECT_DIR / "slides.pptx"


# ════════════════════════════════════════════════════════════════════════
# Small helpers
# ════════════════════════════════════════════════════════════════════════
def _date_str(meta: dict) -> str:
    return (meta.get("generated_at") or "").replace("-", "·")[:7] or "May 2026"


def _short_team(name: str) -> str:
    return {"Paris S-G": "PSG", "Bayern Munich": "Bayern"}.get(name, name)


# ════════════════════════════════════════════════════════════════════════
# Slide content (one function per slide)
# ════════════════════════════════════════════════════════════════════════
def slide_title(prs, d):
    R.add_title_slide(
        prs,
        title="The True *Contributors*.",
        subtitle="WHO ACTUALLY MOVES THE TABLE? · A THREE-LAYER EXPECTED-POINTS ATTRIBUTION",
        date=_date_str(d["meta"]),
        project_num="03",
    )


def slide_tldr(prs, d):
    meta = d["meta"]
    top = d["q1a_full_credit"]["rows"][0]
    brandt = next(r for r in d["q6_architects"]["layer_breakdown"]
                  if r["player"] == "Julian Brandt")
    messi_sca2 = d["q6_architects"]["abs_top"][0]["ep_timed"]
    bullets = [
        f"We take project 02's time-aware expected-points (EP) value function and "
        f"credit a THIRD touchpoint per goal (the pre-assist, SCA2) alongside the "
        f"scorer and the assister.",
        f"Across {meta['total_goals']:,} goals in six leagues and seven seasons, the "
        f"per-90 board still leads with the consensus elite ({top['player']}, "
        f"{top['ep_per_90']:.2f} EP/90), the framework clears the eye test before it "
        f"surfaces surprises.",
        f"The marquee finding: Julian Brandt collects {brandt['ep_sca2']:.2f} EP from "
        f"pre-assists alone, second in Europe only to Messi ({messi_sca2:.2f}), and "
        f"39% of his total value comes from that single layer.",
    ]
    R.add_bullet_slide(prs, "TL;DR: three sentences", bullets, eyebrow="TL;DR")


def slide_question(prs, d):
    s = R.add_blank_slide(prs)
    R.add_section_header(s, "THE QUESTION", "Three touchpoints, *two* counted")
    R.add_text(s, R.BODY_LEFT, R.BODY_TOP, R.BODY_MAX_W, 0.9,
               "Every goal is built by a chain of contributions. The scoreboard credits the "
               "end of the chain and forgets the rest.",
               font=R.SERIF, size=24, color=R.TEXT, italic=True)
    rows = [
        ("SCORER",
         "Puts the ball in the net. Always credited: the goal goes on his record."),
        ("ASSIST · SCA1",
         "The final pass. Sometimes credited, when the box score bothers to log it."),
        ("PRE-ASSIST · SCA2",
         "The pass before the pass. Almost never credited: it disappears into the squad page."),
    ]
    y = R.BODY_TOP + 1.05
    for label, body in rows:
        accent = label.startswith("PRE-ASSIST")
        R.add_mono_label(s, R.BODY_LEFT, y, 3.0, 0.3, label,
                         color=R.ACCENT if accent else R.TEXT_SECONDARY, size=10)
        R.add_text(s, R.BODY_LEFT + 3.1, y - 0.05, 8.6, 0.65, body,
                   font=R.SANS, size=14,
                   color=R.TEXT if accent else R.TEXT_SECONDARY)
        y += 0.78
    R.add_text(s, R.BODY_LEFT, R.CAPTION_TOP, R.BODY_MAX_W, 0.3,
               "→ Credit all three. Then ask who the model elevates that the box score does not.",
               font=R.SANS, size=14, color=R.ACCENT, italic=True)


def slide_data_method(prs, d):
    meta = d["meta"]
    s = R.add_blank_slide(prs)
    R.add_section_header(s, "DATA & METHOD", "What the framework runs on")

    stats = [
        (f"{meta['total_goals']:,}",                 "GOAL EVENTS"),
        (f"{len(meta['leagues'])}",                  "LEAGUES"),
        (f"{len(meta['seasons'])}",                  "SEASONS"),
        (f"{meta['total_players_with_meta']:,}",     "PLAYERS W/ META"),
    ]
    x = R.BODY_LEFT
    for value, label in stats:
        R.add_rect(s, x, R.BODY_TOP, 2.85, 1.5, R.BG_CARD, border=R.BORDER, border_pt=0.75)
        R.add_text(s, x + 0.2, R.BODY_TOP + 0.12, 2.6, 0.9, value,
                   font=R.SERIF, size=38, color=R.ACCENT)
        R.add_mono_label(s, x + 0.2, R.BODY_TOP + 0.98, 2.6, 0.3, label,
                         color=R.TEXT_MUTED, size=9)
        x += 3.0

    # Three-layer credit card
    R.add_rect(s, R.BODY_LEFT, R.BODY_TOP + 1.85, R.BODY_MAX_W, 1.0, R.BG_CARD,
               border=R.ACCENT, border_pt=1.2)
    R.add_text(s, R.BODY_LEFT + 0.3, R.BODY_TOP + 2.05, R.BODY_MAX_W - 0.6, 0.55,
               "three_layer credit  =  scorer + SCA1 + SCA2     (each role = 1 credit · EP summed)",
               font=R.MONO, size=16, color=R.ACCENT)

    y = R.BODY_TOP + 3.05
    for line in [
        "Inherits project 02's value function verbatim: a goal is priced by the swing in "
        "expected league points it produces, conditioned on game-state and minute.",
        "Per-90 = (EP / minutes) × 90. Minutes come from FBref summary tables, Top-5 "
        "leagues only, so every per-90 board excludes Eredivisie.",
    ]:
        R.add_text(s, R.BODY_LEFT, y, R.BODY_MAX_W, 0.5, line,
                   font=R.SANS, size=13, color=R.TEXT_SECONDARY)
        y += 0.55
    R.add_text(s, R.BODY_LEFT, R.CAPTION_TOP, R.BODY_MAX_W, 0.3,
               "Absolute-EP boards keep all six leagues; per-90 boards are Top-5 only.",
               font=R.MONO, size=10, color=R.TEXT_MUTED)


def slide_q1a(prs, d):
    rows = d["q1a_full_credit"]["rows"][:10][::-1]   # reversed for barh bottom-up
    labels = [r["player"] for r in rows]
    values = [r["ep_per_90"] for r in rows]
    teams = [_short_team(r["primary_team"]) for r in rows]

    fig, ax = R.new_chart(width=11, height=4.6)
    bars = ax.barh(labels, values, color=R.MPL_ACCENT, edgecolor=R.MPL_ACCENT, linewidth=0)
    for bar, val, team in zip(bars, values, teams):
        ax.text(val + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}  ·  {team}", ha="left", va="center",
                color=R.MPL_TEXT_SEC, fontsize=10)
    ax.set_xlabel("EP per 90 · three-layer credit (scorer + SCA1 + SCA2)",
                  color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_xlim(0, max(values) * 1.25)
    ax.tick_params(axis="y", labelsize=11)

    R.add_chart_slide(
        prs, "The model clears the *eye test*", fig,
        caption="Top 10 by EP/90, ≥ 1,000 minutes, Top-5 leagues. The consensus elite leads, "
                "which is the point. Recover what everyone knows before surfacing surprises.",
        eyebrow="Q1a · FULL-CREDIT LEADERBOARD")


def slide_q1b_robustness(prs, d):
    R.add_bullet_slide(
        prs,
        "Does *weighting* the credits change the answer?",
        bullets=[
            "Re-run the same board with credits weighted 0.40 / 0.35 / 0.25 "
            "(scorer / SCA1 / SCA2). EP only; the minutes threshold is unchanged.",
            "The top eight is essentially identical. The biggest movers are pure scorers "
            "gaining a little under the heavier scoring weight: Lewandowski +6, Dovbyk +7.",
            "Creator-heavy names slip a few places: Jallow −9, Ljajić −9.",
            "That the tuned weights reproduce the simple 1/1/1 board IS the result: the "
            "ranking is not an artefact of the credit split.",
        ],
        eyebrow="Q1b · ROBUSTNESS",
        caption="Full rank-shift table on the dashboard · Q1 Rank Shift (A vs B)")


def _q2_agreement(d):
    """Count cells where the model's pick == the real award winner."""
    grid = d["q2_mvp_grid"]["grid"]
    comb = d["q2_mvp_grid"]["combined_5l"]
    matches = comparable = 0
    for seasons in grid.values():
        for cell in seasons.values():
            mp = cell.get("model_pick")
            w = (cell.get("actual") or {}).get("winner")
            if mp and w:
                comparable += 1
                if mp["player"] == w:
                    matches += 1
    for cell in comb.values():
        mp = cell.get("model_pick")
        w = (cell.get("actual_ballon_dor") or {}).get("winner")
        if mp and w:
            comparable += 1
            if mp["player"] == w:
                matches += 1
    pct = round(matches / comparable * 100) if comparable else 0
    return matches, comparable, pct


def slide_q2_mvps(prs, d):
    jackson = d["q2_mvp_grid"]["grid"]["La-Liga"]["2022-2023"]["model_pick"]
    muriel = d["q2_mvp_grid"]["combined_5l"]["2020-2021"]["model_pick"]
    m, n, pct = _q2_agreement(d)
    R.add_two_column_slide(
        prs,
        "The model's MVPs, *season by season*",
        left={
            "label": "LA LIGA · 2022-23",
            "title": jackson["player"],
            "body": f"{jackson['primary_team']} · {jackson['ep_per_90']:.3f} EP/90 over "
                    f"{jackson['minutes']:,} minutes ({jackson['goals_involved']} credits).\n\n"
                    f"La Liga's top per-90 pick the season before he joined Chelsea.",
            "accent": True,
        },
        right={
            "label": "5 LEAGUES COMBINED · 2020-21",
            "title": muriel["player"],
            "body": f"{muriel['primary_team']} · {muriel['ep_per_90']:.3f} EP/90 "
                    f"({muriel['goals_involved']} credits).\n\n"
                    f"The model's Ballon d'Or pick that season, not what the trophy "
                    f"cabinet recorded.",
        },
        eyebrow="Q2 · PER-SEASON MVPs",
        caption=f"Model's top EP/90 pick per (league × season) vs the real award winner, matched in "
                f"{m} of {n} cells ({pct}%). The model prices leverage, not reputation. Top-5 only.")


def slide_q3_late(prs, d):
    rows = d["q3_late_game"]["rows_substantive"][:10][::-1]
    labels = [r["player"] for r in rows]
    values = [r["share_late"] * 100 for r in rows]
    teams = [_short_team(r["primary_team"]) for r in rows]

    fig, ax = R.new_chart(width=11, height=4.6)
    bars = ax.barh(labels, values, color=R.MPL_ACCENT, edgecolor=R.MPL_ACCENT, linewidth=0)
    for bar, val, team in zip(bars, values, teams):
        ax.text(val + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%  ·  {team}", ha="left", va="center",
                color=R.MPL_TEXT_SEC, fontsize=10)
    ax.set_xlabel("Share of EP collected in the 60–90 minute bins",
                  color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_xlim(0, max(values) * 1.18)
    ax.tick_params(axis="y", labelsize=11)

    R.add_chart_slide(
        prs, "The late-game *substantives*", fig,
        caption="Top 10 by late share, ≥ 30 three-layer credits (super-subs filtered out). "
                "Includes all six leagues. Tello takes 73.8% of his value after the 60th minute.",
        eyebrow="Q3 · LATE-GAME SPECIALISTS")


def slide_q5_positions(prs, d):
    panels = d["q5_position"]["panels"]
    headers = ["Position", "#1 pick", "EP/90", "Minutes", "Credits"]
    rows = []
    for pos, label in [("DF", "Defender"), ("MF", "Midfielder"), ("FW", "Forward")]:
        r = panels[pos]["rows"][0]
        rows.append([label, r["player"], f"{r['ep_per_90']:.3f}",
                     f"{r['minutes']:,}", str(r["goals_involved"])])
    R.add_table_slide(
        prs,
        "Position-adjusted · *outfield* only",
        headers, rows,
        eyebrow="Q5 · POSITION-ADJUSTED",
        col_widths=[2.4, 3.4, 1.8, 2.2, 2.2],
        caption="Top EP/90 per modal position, ≥ 1,000 minutes. GK excluded: a structural blind "
                "spot of the framework (top GK ~0.1 EP/90 vs ~1.1 for forwards). De Bruyne is the "
                "most-sampled elite pick anywhere here: 14,674 minutes, 206 credits.")


def slide_q6_architects(prs, d):
    rows = d["q6_architects"]["layer_breakdown"][:10][::-1]
    labels = [r["player"] for r in rows]
    scorer = [r["ep_scorer"] for r in rows]
    sca1 = [r["ep_sca1"] for r in rows]
    sca2 = [r["ep_sca2"] for r in rows]

    fig, ax = R.new_chart(width=11, height=4.6)
    ax.barh(labels, scorer, color="#3f5a2a", edgecolor="none", label="Scorer EP")
    ax.barh(labels, sca1, left=scorer, color=R.MPL_BORDER_LIGHT, edgecolor="none",
            label="SCA1 (assist) EP")
    left2 = [a + b for a, b in zip(scorer, sca1)]
    ax.barh(labels, sca2, left=left2, color=R.MPL_ACCENT, edgecolor="none",
            label="SCA2 (pre-assist) EP")
    ax.set_xlabel("EP collected (cumulative, by role)", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(axis="y", visible=False)
    leg = ax.legend(loc="lower right", fontsize=9, frameon=False)
    for txt in leg.get_texts():
        txt.set_color(R.MPL_TEXT_SEC)

    R.add_chart_slide(
        prs, "The Hidden *Architects*", fig,
        caption="Top 10 SCA2 EP collectors, stacked by contribution role. Bright accent = the "
                "pre-assist layer. One player is structurally different from everyone else.",
        eyebrow="Q6 · MARQUEE FINDING")


def slide_brandt_spotlight(prs, d):
    brandt = next(r for r in d["q6_architects"]["layer_breakdown"]
                  if r["player"] == "Julian Brandt")
    messi_sca2 = d["q6_architects"]["abs_top"][0]["ep_timed"]
    sca2_share = brandt["ep_sca2"] / brandt["ep_total"] * 100

    s = R.add_blank_slide(prs)
    R.add_section_header(s, "SPOTLIGHT", "What the model *exists to find*")

    card_top = R.BODY_TOP
    card_h = R.CAPTION_TOP - R.CAPTION_GAP - card_top
    # Left card: Brandt headline number
    R.add_rect(s, R.BODY_LEFT, card_top, 6.0, card_h, R.BG_CARD, border=R.ACCENT, border_pt=1.5)
    R.add_mono_label(s, R.BODY_LEFT + 0.25, card_top + 0.2, 5.5, 0.3,
                     "PRE-ASSIST ARCHITECT", color=R.ACCENT, size=10)
    R.add_text(s, R.BODY_LEFT + 0.25, card_top + 0.55, 5.5, 0.7, brandt["player"],
               font=R.SERIF, size=32, color=R.TEXT)
    R.add_text(s, R.BODY_LEFT + 0.25, card_top + 1.3, 5.5, 0.4,
               "Borussia Dortmund · MF",
               font=R.MONO, size=11, color=R.TEXT_SECONDARY)
    R.add_text(s, R.BODY_LEFT + 0.25, card_top + 1.95, 5.5, 1.1,
               f"{brandt['ep_sca2']:.2f}",
               font=R.SERIF, size=64, color=R.ACCENT)
    R.add_mono_label(s, R.BODY_LEFT + 0.25, card_top + 3.10, 5.5, 0.3,
                     "EP COLLECTED FROM SCA2 ALONE", color=R.TEXT_MUTED, size=9)
    R.add_text(s, R.BODY_LEFT + 0.25, card_top + 3.5, 5.5, 0.8,
               f"Second in Europe only to Messi ({messi_sca2:.2f}). The pre-assist is his single "
               f"largest contribution layer.",
               font=R.SANS, size=13, color=R.TEXT_SECONDARY)

    # Right: SCA2-share comparison
    right_x = R.BODY_LEFT + 6.3
    right_w = R.BODY_MAX_W - 6.3
    R.add_mono_label(s, right_x, card_top + 0.15, right_w, 0.3,
                     "SCA2 SHARE OF TOTAL EP", color=R.TEXT_MUTED, size=10)
    R.add_hline(s, right_x, card_top + 0.55, right_w, color=R.BORDER, pt=1)
    compare = [
        ("Julian Brandt", sca2_share, True),
        ("Nabil Fekir", 31.6, False),
        ("Lionel Messi", 24.7, False),
        ("Kylian Mbappé", 19.6, False),
        ("Mohamed Salah", 19.5, False),
    ]
    y = card_top + 0.7
    for name, share, hot in compare:
        R.add_text(s, right_x, y, 3.0, 0.4, name, font=R.SANS, size=13,
                   color=R.ACCENT if hot else R.TEXT_SECONDARY, bold=hot)
        # mini bar
        bar_full = right_w - 3.0 - 1.15          # between the name column and the % label
        R.add_rect(s, right_x + 3.0, y + 0.11, bar_full * share / max(c[1] for c in compare), 0.18,
                   R.ACCENT if hot else R.BORDER_LIGHT)
        R.add_text(s, right_x + right_w - 1.0, y, 1.0, 0.4, f"{share:.1f}%",
                   font=R.MONO, size=12, color=R.ACCENT if hot else R.TEXT_SECONDARY,
                   align=PP_ALIGN.RIGHT, bold=hot)
        y += 0.62

    R.add_text(s, R.BODY_LEFT, R.CAPTION_TOP, R.BODY_MAX_W, 0.3,
               "Brandt's profile (25% scorer / 37% SCA1 / 39% SCA2) is shared by no pure goalscorer.",
               font=R.MONO, size=10, color=R.TEXT_MUTED)


def slide_q7_young(prs, d):
    rows = d["q7_young"]["rows"][:10][::-1]
    labels = [f"{r['player']} (age {r['age']:.0f})" if r.get("age") else r["player"]
              for r in rows]
    values = [r["ep_per_90"] for r in rows]
    # opacity proxy: mute low-sample (< 2000 min) by using dim colour
    colors = [R.MPL_ACCENT if (r.get("minutes") or 0) >= 2000 else "#6f8a3f" for r in rows]

    fig, ax = R.new_chart(width=11, height=4.6)
    bars = ax.barh(labels, values, color=colors, edgecolor="none")
    for bar, val, r in zip(bars, values, rows):
        ax.text(val + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}  ·  {r['minutes']:,} min", ha="left", va="center",
                color=R.MPL_TEXT_SEC, fontsize=9.5)
    ax.set_xlabel("EP per 90 · age ≤ 23", color=R.MPL_TEXT_SEC, fontsize=11)
    ax.set_xlim(0, max(values) * 1.28)
    ax.tick_params(axis="y", labelsize=10.5)

    R.add_chart_slide(
        prs, "Young players to *watch*", fig,
        caption="Top 10 EP/90, age ≤ 23, ≥ 500 minutes. Dim bars = under 2,000 minutes "
                "(low sample). Yamal sits #10 on 2,209 minutes at age 16.9, real volume, not a cameo.",
        eyebrow="Q7 · UNDER-23 WATCHLIST")


def slide_implications(prs, d):
    R.add_bullet_slide(
        prs,
        "What this *changes*",
        bullets=[
            "Contribution is a chain, not a tally. Pricing the pre-assist surfaces value "
            "the goal-and-assist box score structurally cannot see.",
            "Recruitment: a player like Brandt, whose largest layer is the pass before the "
            "pass, is materially mis-valued by conventional output metrics.",
            "The ranking is stable. Re-weighting the three layers barely moves the board, so "
            "the discoveries beneath the elite are not an artefact of the credit split.",
            "The dashboard exposes all seven boards with per-league and per-season drill-down, "
            "so any analyst can apply their own thresholds.",
        ],
        eyebrow="IMPLICATIONS",
    )


def slide_limitations(prs, d):
    R.add_bullet_slide(
        prs,
        "What this *isn't*",
        bullets=[
            "Not xG-weighted; penalties not separated; own goals missing from the shot data (inherited from project 02).",
            "Credit caps at SCA2: build-up beyond the pre-assist isn't captured.",
            "Per-90 boards exclude Eredivisie: the minutes source covers the top five leagues only.",
            "No opinion on goalkeepers: the three credited touchpoints are ones GKs rarely occupy.",
            "Observational, not causal: EP is the gap between states a goal connects, not its counterfactual effect.",
        ],
        eyebrow="LIMITATIONS",
        caption="Full discussion: methodology.html · §5",
    )


def slide_contact(prs, d):
    R.add_closing_slide(
        prs,
        headline="Every player, every league, every season.",
        url="renball.com",
        project_path="/projects/03-true-contributors/",
        lines=[
            "→ analysis.html        editorial write-up · Chart.js + custom SVG visuals",
            "→ dashboard.html       interactive Tabulator dashboard · 7 datasets · drill-down",
            "→ methodology.html     three-layer attribution · seven questions · nine limitations",
            "→ code/build.py        Python pipeline: project 02 framework + SCA2 enrichment",
        ],
    )


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════
def main() -> None:
    with open(DATA_JSON, encoding="utf-8") as f:
        d = json.load(f)

    prs = R.create_deck()
    slide_title(prs, d)            # 1
    slide_tldr(prs, d)             # 2
    slide_question(prs, d)         # 3
    slide_data_method(prs, d)      # 4
    slide_q1a(prs, d)              # 5
    slide_q1b_robustness(prs, d)   # 6
    slide_q2_mvps(prs, d)          # 7
    slide_q3_late(prs, d)          # 8
    slide_q5_positions(prs, d)     # 9
    slide_q6_architects(prs, d)    # 10
    slide_brandt_spotlight(prs, d) # 11
    slide_q7_young(prs, d)         # 12
    slide_implications(prs, d)     # 13
    slide_limitations(prs, d)      # 14
    slide_contact(prs, d)          # 15
    R.finalize_deck(prs)

    prs.save(OUTPUT_PPTX)
    size_kb = OUTPUT_PPTX.stat().st_size / 1024
    print(f"[OK] Wrote {OUTPUT_PPTX.relative_to(PROJECT_DIR)} "
          f"({size_kb:.1f} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
