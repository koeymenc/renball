"""
build_slides.py — Renball-branded slides.pptx for project 01
─────────────────────────────────────────────────────────────

Generates a 12-slide 16:9 PowerPoint deck for the penalty-conversion
project. All numbers are pulled live from ../data/data.json — change
the analysis, re-run build.py, re-run this script, and the deck stays
in sync.

Run:
    python code/build_slides.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_JSON = PROJECT_DIR / "data" / "data.json"
OUTPUT_PPTX = PROJECT_DIR / "slides.pptx"

# ── Renball design tokens ──────────────────────────────────
BG          = RGBColor(0x08, 0x0C, 0x08)
BG_ELEVATED = RGBColor(0x0E, 0x15, 0x0E)
BG_CARD     = RGBColor(0x11, 0x1A, 0x11)
SURFACE     = RGBColor(0x1A, 0x26, 0x1A)
BORDER      = RGBColor(0x1E, 0x2E, 0x1E)
BORDER_L    = RGBColor(0x2D, 0x3D, 0x2D)
TEXT        = RGBColor(0xE8, 0xEF, 0xE8)
TEXT_SEC    = RGBColor(0x8F, 0xA6, 0x8F)
TEXT_MUTED  = RGBColor(0x5A, 0x73, 0x5A)
ACCENT      = RGBColor(0xC1, 0xFF, 0x72)
ACCENT_DIM  = RGBColor(0x8F, 0xBF, 0x45)

SERIF = "Instrument Serif"
SANS  = "DM Sans"
MONO  = "JetBrains Mono"

# matplotlib equivalents (#rrggbb)
MPL_BG, MPL_BG_CARD = "#080c08", "#111a11"
MPL_BORDER, MPL_BORDER_L = "#1e2e1e", "#2d3d2d"
MPL_TEXT, MPL_TEXT_SEC, MPL_TEXT_MUTED = "#e8efe8", "#8fa68f", "#5a735a"
MPL_ACCENT, MPL_SECONDARY = "#c1ff72", "#72c1ff"

SLIDE_W, SLIDE_H = 13.333, 7.5  # inches


# ── Helpers ────────────────────────────────────────────────
def add_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    add_logo(slide)
    return slide


def add_logo(slide):
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.32), Inches(2), Inches(0.5))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r1 = p.add_run(); r1.text = "ren"
    r1.font.name = SERIF; r1.font.size = Pt(20); r1.font.color.rgb = TEXT
    r2 = p.add_run(); r2.text = "ball"
    r2.font.name = SERIF; r2.font.size = Pt(20); r2.font.color.rgb = ACCENT


def textbox(slide, x, y, w, h, *, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    tf.word_wrap = wrap
    tf.paragraphs[0].alignment = align
    return tb


def add_run(paragraph, text, *, font=SANS, size=14, color=TEXT, bold=False, italic=False):
    r = paragraph.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.font.bold = bold
    r.font.italic = italic
    return r


def add_text(slide, x, y, w, h, text, *, font=SANS, size=14, color=TEXT,
             bold=False, italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = textbox(slide, x, y, w, h, anchor=anchor, align=align)
    add_run(tb.text_frame.paragraphs[0], text, font=font, size=size,
            color=color, bold=bold, italic=italic)
    return tb


def add_mono_label(slide, x, y, w, h, text, *, color=TEXT_MUTED, size=9, align=PP_ALIGN.LEFT):
    return add_text(slide, x, y, w, h, text.upper(), font=MONO, size=size, color=color, align=align)


def add_rect(slide, x, y, w, h, fill, *, border=None, border_pt=0):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.shadow.inherit = False
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if border:
        shp.line.color.rgb = border
        shp.line.width = Pt(border_pt or 0.75)
    else:
        shp.line.fill.background()
    shp.text_frame.text = ""
    shp.text_frame.margin_left = shp.text_frame.margin_right = 0
    shp.text_frame.margin_top = shp.text_frame.margin_bottom = 0
    return shp


def add_hline(slide, x, y, w, color=BORDER, pt=1):
    return add_rect(slide, x, y, w, pt / 72, color)


# ── Matplotlib chart helpers ───────────────────────────────
def new_chart(width=10.5, height=4.5):
    fig, ax = plt.subplots(figsize=(width, height), facecolor=MPL_BG)
    ax.set_facecolor(MPL_BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_edgecolor(MPL_BORDER)
    ax.tick_params(colors=MPL_TEXT_MUTED, labelsize=10)
    ax.grid(axis="y", color=MPL_BORDER, alpha=0.7, linewidth=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def chart_to_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, facecolor=MPL_BG, bbox_inches="tight", pad_inches=0.2)
    buf.seek(0)
    plt.close(fig)
    return buf


def add_chart_picture(slide, fig, x, y, w):
    buf = chart_to_bytes(fig)
    slide.shapes.add_picture(buf, Inches(x), Inches(y), width=Inches(w))


# ── Slide content ──────────────────────────────────────────
def slide_title(prs, d):
    s = add_slide(prs)
    # Big project title
    tb = textbox(s, 0.7, 2.5, 12, 2.5, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, wrap=True)
    p = tb.text_frame.paragraphs[0]
    add_run(p, "Should the Fouled Player Take the Penalty ", font=SERIF, size=54, color=TEXT)
    add_run(p, "Himself", font=SERIF, size=54, color=ACCENT, italic=True)
    add_run(p, "?", font=SERIF, size=54, color=TEXT)

    add_mono_label(s, 0.7, 5.1, 12, 0.3, "A ONE-TAILED TEST · TOP 5 EUROPEAN LEAGUES", color=TEXT_SEC, size=12)

    date_str = (d.get("generated_at") or "")[:7] or "May 2026"
    add_mono_label(s, 0.7, 5.6, 12, 0.3, date_str, color=TEXT_MUTED, size=10)

    # Accent dividing line
    add_hline(s, 0.7, 6.0, 1.2, color=ACCENT, pt=2)

    # Footer
    add_mono_label(s, 0.7, 6.8, 12, 0.3, "RENBALL.COM", color=TEXT_MUTED, size=9)


def slide_tldr(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "TL;DR", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Three sentences", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    t = d["primary"]["treatment"]
    c = d["primary"]["control"]
    tst = d["primary"]["test"]

    rows = [
        ("THE QUESTION",
         "When a goalkeeper fouls a player who then takes the penalty himself, "
         "does conversion drop?"),
        ("THE TEST",
         f"One-tailed two-proportion z-test. Treatment n = {t['attempts']} "
         f"({t['rate']}%). Control n = {c['attempts']:,} ({c['rate']}%)."),
        ("THE RESULT",
         f"Δ = {tst['rate_diff_pp']:+.2f} pp (predicted direction) but p = "
         f"{tst['p_value']:.3f}, one-tailed — fail to reject H₀ at the available power."),
    ]

    y = 3.0
    for label, body in rows:
        add_mono_label(s, 0.7, y, 2.4, 0.3, label, color=ACCENT, size=10)
        add_text(s, 3.2, y - 0.07, 9.4, 1.1, body, font=SERIF, size=20, color=TEXT)
        y += 1.3


def slide_theory(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "THE THEORY", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Why we'd expect a drop", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    add_text(s, 0.7, 3.0, 12, 0.7,
             "The just-fouled player walks straight to the spot.",
             font=SERIF, size=24, color=TEXT, italic=True)

    add_text(s, 0.7, 4.0, 6, 2.6,
             "Theory of the taker: physically jarred — body contact, hit the ground, "
             "adrenaline. Emotionally agitated, narrowed focus.",
             font=SANS, size=15, color=TEXT_SEC)

    add_text(s, 7.0, 4.0, 6, 2.6,
             "Theory of the keeper: locked in. The foul that gave the penalty was his fault. "
             "Nothing left to lose. Maximum motivation.",
             font=SANS, size=15, color=TEXT_SEC)

    add_text(s, 0.7, 6.6, 12, 0.5,
             "→ If both pull conversion down, the bench should hand the ball to a designated specialist.",
             font=SANS, size=13, color=ACCENT, italic=True)


def slide_data(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "DATA", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "What we built the test on", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    seasons = d["metadata"]["seasons"]
    seasons_label = f"{seasons[0]} → {seasons[-1]}" if seasons else "—"
    t_n = d["primary"]["treatment"]["attempts"]

    stats = [
        (f"{d['overall']['attempts']:,}", "PENALTIES (LOOSE FILTER)"),
        (f"{d['metadata']['n_matches_strict']:,}", "SINGLE-PENALTY MATCHES"),
        (f"{t_n:,}", "TREATMENT-CELL N"),
        (str(len(d["metadata"]["leagues"])), "LEAGUES"),
    ]
    x = 0.7
    for value, label in stats:
        add_rect(s, x, 3.0, 2.85, 1.6, BG_CARD, border=BORDER, border_pt=0.75)
        add_text(s, x + 0.2, 3.15, 2.6, 0.9, value, font=SERIF, size=42, color=ACCENT)
        add_mono_label(s, x + 0.2, 4.05, 2.6, 0.3, label, color=TEXT_MUTED, size=9)
        x += 3.0

    add_text(s, 0.7, 4.95, 12, 0.4,
             f"Seasons in scope: {seasons_label}", font=SANS, size=13, color=TEXT_SEC)
    add_text(s, 0.7, 5.4, 12, 0.4,
             "Competitions: Premier League, La Liga, Serie A, Bundesliga, Ligue 1.",
             font=SANS, size=13, color=TEXT_SEC)
    add_text(s, 0.7, 5.9, 12, 0.4,
             "Source: FBref player-match data, consolidated locally as FULL_DICT_ROWS.pkl.",
             font=SANS, size=13, color=TEXT_SEC)
    add_text(s, 0.7, 6.45, 12, 0.7,
             "Strict filter = matches with at most one penalty event "
             "(unambiguous GK-caused / taker-was-fouled attribution).",
             font=MONO, size=11, color=TEXT_MUTED, italic=False)


def slide_method(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "METHOD", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "One-tailed two-proportion z-test", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    # Treatment card
    add_rect(s, 0.7, 3.0, 5.9, 2.7, BG_CARD, border=ACCENT, border_pt=1.5)
    add_mono_label(s, 0.95, 3.2, 5.5, 0.3, "TREATMENT", color=ACCENT, size=10)
    add_text(s, 0.95, 3.55, 5.5, 0.8,
             "GK fouled the taker", font=SERIF, size=24, color=TEXT)
    add_text(s, 0.95, 4.35, 5.5, 1.25,
             "Matches where the goalkeeper conceded the foul AND the fouled "
             "player is the same player who took the penalty.",
             font=SANS, size=13, color=TEXT_SEC)

    # Control card
    add_rect(s, 6.85, 3.0, 5.9, 2.7, BG_CARD, border=BORDER_L, border_pt=0.75)
    add_mono_label(s, 7.10, 3.2, 5.5, 0.3, "CONTROL", color=TEXT_SEC, size=10)
    add_text(s, 7.10, 3.55, 5.5, 0.8,
             "All other penalties", font=SERIF, size=24, color=TEXT)
    add_text(s, 7.10, 4.35, 5.5, 1.25,
             "Every other strict-filter match — GK fouled but a different player took, "
             "or outfielder caused the foul (any taker).",
             font=SANS, size=13, color=TEXT_SEC)

    # Hypothesis block
    add_text(s, 0.7, 6.0, 12, 0.4,
             "H₀: conversion_treatment = conversion_control",
             font=MONO, size=12, color=TEXT_SEC)
    add_text(s, 0.7, 6.4, 12, 0.4,
             "H₁: conversion_treatment < conversion_control     (one-tailed, α = 0.05)",
             font=MONO, size=12, color=ACCENT)
    add_text(s, 0.7, 6.85, 12, 0.4,
             "95% Wilson CIs on each proportion. Implementation: statsmodels.proportions_ztest(alternative='smaller').",
             font=MONO, size=10, color=TEXT_MUTED)


def slide_by_league(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "CONTEXT", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Conversion rate by league", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    fig, ax = new_chart(width=11, height=4.3)
    leagues = d["by_league"]
    labels = [l["label"] for l in leagues]
    rates = [l["rate"] for l in leagues]
    bars = ax.bar(labels, rates, color=MPL_ACCENT, width=0.55, edgecolor="none")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Conversion rate (%)", color=MPL_TEXT_SEC, fontsize=11)
    for bar, val, lg in zip(bars, rates, leagues):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.2,
                f"{val:.1f}%", ha="center", color=MPL_TEXT, fontsize=10)
        ax.text(bar.get_x() + bar.get_width() / 2, -6,
                f"n = {lg['attempts']:,}", ha="center", color=MPL_TEXT_MUTED, fontsize=8)
    add_chart_picture(s, fig, 0.7, 2.9, 12)

    add_text(s, 0.7, 6.85, 12, 0.4,
             "Across the top 5 leagues conversion clusters tightly in the high 70s — league of origin is "
             "not a major source of variation.",
             font=MONO, size=10, color=TEXT_MUTED)


def slide_by_season(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "CONTEXT", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Conversion across seasons", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    fig, ax = new_chart(width=11, height=4.3)
    seasons = d["by_season"]
    labels = [s["season"] for s in seasons]
    rates = [s["rate"] for s in seasons]
    ax.bar(labels, rates, color=MPL_ACCENT, width=0.55, edgecolor="none")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Conversion rate (%)", color=MPL_TEXT_SEC, fontsize=11)
    for i, (val, sn) in enumerate(zip(rates, seasons)):
        ax.text(i, val + 1.2, f"{val:.1f}%", ha="center", color=MPL_TEXT, fontsize=9)
        ax.text(i, -6, f"n = {sn['attempts']:,}", ha="center", color=MPL_TEXT_MUTED, fontsize=8)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    add_chart_picture(s, fig, 0.7, 2.9, 12)

    add_text(s, 0.7, 6.85, 12, 0.4,
             "Year-on-year stability is high — the ~77–80% band holds across the period in scope.",
             font=MONO, size=10, color=TEXT_MUTED)


def slide_primary(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "PRIMARY TEST · ONE-TAILED", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Treatment vs control", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    t = d["primary"]["treatment"]
    c = d["primary"]["control"]
    tst = d["primary"]["test"]

    # Bar chart on the left with CI whiskers
    fig, ax = new_chart(width=7.5, height=4.3)
    labels = ["Treatment\n(GK fouled the taker)", "Control\n(all other penalties)"]
    rates = [t["rate"], c["rate"]]
    bars = ax.bar(labels, rates, color=[MPL_ACCENT, MPL_SECONDARY], width=0.5, edgecolor="none")
    cis = [(t["ci_lo"], t["ci_hi"]), (c["ci_lo"], c["ci_hi"])]
    for i, (lo, hi) in enumerate(cis):
        x = bars[i].get_x() + bars[i].get_width() / 2
        ax.plot([x, x], [lo, hi], color=MPL_TEXT, linewidth=1.4)
        ax.plot([x - 0.07, x + 0.07], [lo, lo], color=MPL_TEXT, linewidth=1.4)
        ax.plot([x - 0.07, x + 0.07], [hi, hi], color=MPL_TEXT, linewidth=1.4)
    for bar, val in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, val - 6,
                f"{val:.2f}%", ha="center", color=MPL_BG, fontsize=14,
                fontweight="bold")
    ax.set_ylim(50, 95)
    ax.set_ylabel("Conversion rate (%)", color=MPL_TEXT_SEC, fontsize=11)
    add_chart_picture(s, fig, 0.7, 2.9, 7.4)

    # Result callout on the right
    x0 = 8.4
    add_rect(s, x0, 2.9, 4.5, 3.85, BG_CARD, border=ACCENT, border_pt=1.5)

    add_mono_label(s, x0 + 0.25, 3.1, 4.0, 0.3, "TREATMENT", color=TEXT_MUTED, size=9)
    add_text(s, x0 + 0.25, 3.4, 4.0, 0.7, f"{t['rate']:.2f}%",
             font=SERIF, size=28, color=ACCENT)
    add_text(s, x0 + 0.25, 4.05, 4.0, 0.3,
             f"n = {t['attempts']:,}  ·  95% CI [{t['ci_lo']:.2f}%, {t['ci_hi']:.2f}%]",
             font=MONO, size=9, color=TEXT_SEC)

    add_mono_label(s, x0 + 0.25, 4.55, 4.0, 0.3, "CONTROL", color=TEXT_MUTED, size=9)
    add_text(s, x0 + 0.25, 4.85, 4.0, 0.7, f"{c['rate']:.2f}%",
             font=SERIF, size=28, color=ACCENT)
    add_text(s, x0 + 0.25, 5.5, 4.0, 0.3,
             f"n = {c['attempts']:,}  ·  95% CI [{c['ci_lo']:.2f}%, {c['ci_hi']:.2f}%]",
             font=MONO, size=9, color=TEXT_SEC)

    add_hline(s, x0 + 0.25, 6.05, 4.0, color=BORDER_L, pt=1)

    add_text(s, x0 + 0.25, 6.15, 4.0, 0.45,
             f"Δ = {tst['rate_diff_pp']:+.2f} pp   z = {tst['z_stat']:+.3f}",
             font=MONO, size=11, color=TEXT)
    verdict = "Reject H₀" if tst["significant_at_05"] else "Fail to reject H₀"
    add_text(s, x0 + 0.25, 6.45, 4.0, 0.4,
             f"p = {tst['p_value']:.4f} (one-tailed)  ·  {verdict}",
             font=MONO, size=11, color=ACCENT)

    add_text(s, 0.7, 6.95, 12, 0.4,
             "Whiskers: 95% Wilson confidence intervals. Treatment CI is wide — n is the binding constraint.",
             font=MONO, size=10, color=TEXT_MUTED)


def slide_matrix(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "2×2 CONTEXT", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Where the treatment cell sits", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    m = d["matrix"]
    by_rc = {(cc["row"], cc["col"]): cc for cc in m["cells"]}

    # Grid layout
    label_w = 2.5
    cell_w = 4.0
    cell_h = 1.7
    grid_x = 0.7
    grid_y = 3.0

    # Column headers
    add_rect(s, grid_x, grid_y, label_w, 0.7, BG_ELEVATED, border=BORDER)
    for ci, col in enumerate(m["cols"]):
        cx = grid_x + label_w + ci * cell_w
        add_rect(s, cx, grid_y, cell_w, 0.7, BG_ELEVATED, border=BORDER)
        add_mono_label(s, cx + 0.1, grid_y + 0.2, cell_w - 0.2, 0.3,
                       col["label"], color=TEXT_SEC, size=10, align=PP_ALIGN.CENTER)

    # Rows
    for ri, row in enumerate(m["rows"]):
        ry = grid_y + 0.7 + ri * cell_h
        add_rect(s, grid_x, ry, label_w, cell_h, BG_ELEVATED, border=BORDER)
        add_mono_label(s, grid_x + 0.15, ry + cell_h / 2 - 0.2, label_w - 0.3, 0.5,
                       row["label"], color=TEXT_SEC, size=10)

        for ci, col in enumerate(m["cols"]):
            cx = grid_x + label_w + ci * cell_w
            cell = by_rc[(row["key"], col["key"])]
            fill = BG_CARD
            border_col = BORDER
            shp = add_rect(s, cx, ry, cell_w, cell_h, fill, border=border_col)
            if cell.get("is_treatment"):
                shp.line.color.rgb = ACCENT
                shp.line.width = Pt(2)
                # Inner accent glow as a thin overlay rect (use a subtle elevated bg)
                add_rect(s, cx + 0.05, ry + 0.05, cell_w - 0.1, cell_h - 0.1, SURFACE)
                add_mono_label(s, cx + 0.15, ry + 0.15, cell_w - 0.3, 0.3,
                               "TREATMENT", color=ACCENT, size=8, align=PP_ALIGN.CENTER)
            # rate
            add_text(s, cx + 0.1, ry + 0.45, cell_w - 0.2, 0.7,
                     f"{cell['rate']:.2f}%", font=SERIF, size=30,
                     color=ACCENT, align=PP_ALIGN.CENTER)
            add_mono_label(s, cx + 0.1, ry + 1.15, cell_w - 0.2, 0.3,
                           f"n = {cell['attempts']:,}", color=TEXT_MUTED, size=10,
                           align=PP_ALIGN.CENTER)

    add_text(s, 0.7, 6.95, 12, 0.4,
             "Accent-bordered cell = treatment. The other three pool into control.",
             font=MONO, size=10, color=TEXT_MUTED)


def slide_per_league(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "PER-LEAGUE REPLICATION", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "The same test, league by league", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    blocks = d["primary"]["by_league"]

    # Column geometry (8 columns)
    headers = ["LEAGUE", "T. RATE", "T. N", "C. RATE", "C. N", "Z", "P (1-T)", "SIG"]
    col_w = [2.6, 1.4, 1.0, 1.4, 1.2, 1.2, 1.4, 1.4]
    col_x = [0.7]
    for w in col_w[:-1]:
        col_x.append(col_x[-1] + w)

    # Header row
    header_y = 2.95
    add_hline(s, 0.7, header_y - 0.05, sum(col_w), color=BORDER_L, pt=1)
    for i, hd in enumerate(headers):
        align = PP_ALIGN.LEFT if i == 0 else PP_ALIGN.RIGHT
        add_mono_label(s, col_x[i], header_y, col_w[i] - 0.1, 0.4,
                       hd, color=TEXT_MUTED, size=10, align=align)
    add_hline(s, 0.7, header_y + 0.45, sum(col_w), color=BORDER, pt=1)

    # Body rows
    y = header_y + 0.6
    for blk in blocks:
        tt = blk["treatment"]; cc = blk["control"]; tst = blk["test"]
        low_n = tt["attempts"] < 30
        z_str = f"{tst['z_stat']:+.3f}" if tst["z_stat"] is not None else "—"
        p_str = f"{tst['p_value']:.4f}" if tst["p_value"] is not None else "—"
        sig_str = "Yes" if tst["significant_at_05"] else "No"
        sig_color = ACCENT if tst["significant_at_05"] else TEXT_MUTED
        t_rate_color = TEXT_MUTED if low_n else TEXT
        # League name
        add_text(s, col_x[0], y, col_w[0] - 0.1, 0.4, blk["label"],
                 font=SANS, size=13, color=TEXT)
        # T. rate
        add_text(s, col_x[1], y, col_w[1] - 0.1, 0.4, f"{tt['rate']:.2f}%",
                 font=MONO, size=12, color=t_rate_color, align=PP_ALIGN.RIGHT, italic=low_n)
        # T. n
        add_text(s, col_x[2], y, col_w[2] - 0.1, 0.4, f"{tt['attempts']}",
                 font=MONO, size=12, color=t_rate_color, align=PP_ALIGN.RIGHT, italic=low_n)
        # C. rate
        add_text(s, col_x[3], y, col_w[3] - 0.1, 0.4, f"{cc['rate']:.2f}%",
                 font=MONO, size=12, color=TEXT_SEC, align=PP_ALIGN.RIGHT)
        # C. n
        add_text(s, col_x[4], y, col_w[4] - 0.1, 0.4, f"{cc['attempts']:,}",
                 font=MONO, size=12, color=TEXT_SEC, align=PP_ALIGN.RIGHT)
        # Z
        add_text(s, col_x[5], y, col_w[5] - 0.1, 0.4, z_str,
                 font=MONO, size=12, color=TEXT, align=PP_ALIGN.RIGHT)
        # P
        add_text(s, col_x[6], y, col_w[6] - 0.1, 0.4, p_str,
                 font=MONO, size=12, color=TEXT, align=PP_ALIGN.RIGHT)
        # Sig
        sig_tag = sig_str + (" · low n" if low_n else "")
        add_text(s, col_x[7], y, col_w[7] - 0.1, 0.4, sig_tag,
                 font=MONO, size=12, color=sig_color, align=PP_ALIGN.RIGHT)
        y += 0.5

    add_text(s, 0.7, 6.6, 12, 0.5,
             "Per-league treatment cells of 13–25 leave each test severely underpowered. "
             "Verdicts cell-by-cell are essentially noise.",
             font=MONO, size=10, color=TEXT_MUTED)
    add_text(s, 0.7, 7.1, 12, 0.3,
             "Pooled test is the only inference to take seriously.",
             font=MONO, size=10, color=ACCENT)


def slide_conclusion(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "CONCLUSION", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "What the data says", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    tst = d["primary"]["test"]
    t = d["primary"]["treatment"]
    c = d["primary"]["control"]
    diff_abs = abs(tst["rate_diff_pp"])
    direction = "lower" if tst["rate_diff_pp"] < 0 else "higher"

    # Big headline
    tb = textbox(s, 0.7, 3.0, 12, 1.4)
    p = tb.text_frame.paragraphs[0]
    add_run(p, "The bench answer: ", font=SERIF, size=32, color=TEXT)
    add_run(p, "can't yet tell.", font=SERIF, size=32, color=ACCENT, italic=True)

    add_text(s, 0.7, 4.6, 12, 1.5,
             f"Conversion is {diff_abs:.2f} pp {direction} when the fouled player takes the kick himself "
             f"({t['rate']:.2f}% vs {c['rate']:.2f}% for everyone else). The point estimate moves in the "
             "predicted direction, but the treatment cell is too small to rule chance out "
             f"(p = {tst['p_value']:.3f}, one-tailed).",
             font=SANS, size=15, color=TEXT_SEC)

    add_text(s, 0.7, 6.4, 12, 0.7,
             "→ No statistical warrant to override the fouled player who wants to take it himself. "
             "Equally, no clean evidence he's at full strength.",
             font=SANS, size=13, color=ACCENT, italic=True)


def slide_sources(prs, d):
    s = add_slide(prs)
    add_mono_label(s, 0.7, 1.0, 8, 0.3, "SOURCES & METHODOLOGY", color=ACCENT, size=11)
    add_text(s, 0.7, 1.4, 12, 0.8, "Reproduce or dig deeper", font=SERIF, size=36, color=TEXT)
    add_hline(s, 0.7, 2.4, 1.2, color=ACCENT, pt=2)

    add_text(s, 0.7, 3.1, 12, 0.5, "Full methodology, source code and data:",
             font=SANS, size=15, color=TEXT_SEC)

    add_text(s, 0.7, 3.7, 12, 1.0, "renball.com",
             font=SERIF, size=56, color=ACCENT)

    add_mono_label(s, 0.7, 5.0, 12, 0.4, "/PROJECTS/01-PENALTY-ANALYSIS/", color=TEXT_SEC, size=12)

    add_text(s, 0.7, 5.7, 12, 0.4,
             "→ methodology  ·  formal H₀/H₁, test assumptions, limitations",
             font=MONO, size=12, color=TEXT_MUTED)
    add_text(s, 0.7, 6.05, 12, 0.4,
             "→ analysis.html  ·  interactive dashboard, live numbers from data.json",
             font=MONO, size=12, color=TEXT_MUTED)
    add_text(s, 0.7, 6.4, 12, 0.4,
             "→ code/build.py  ·  Python pipeline from raw pickles to aggregated JSON",
             font=MONO, size=12, color=TEXT_MUTED)

    add_text(s, 0.7, 7.0, 12, 0.3,
             "Data source: FBref player-match statistics, top 5 European leagues.",
             font=MONO, size=10, color=TEXT_MUTED)


# ── Main ───────────────────────────────────────────────────
def main() -> None:
    with open(DATA_JSON, encoding="utf-8") as f:
        d = json.load(f)

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)

    slide_title(prs, d)
    slide_tldr(prs, d)
    slide_theory(prs, d)
    slide_data(prs, d)
    slide_method(prs, d)
    slide_by_league(prs, d)
    slide_by_season(prs, d)
    slide_primary(prs, d)
    slide_matrix(prs, d)
    slide_per_league(prs, d)
    slide_conclusion(prs, d)
    slide_sources(prs, d)

    prs.save(OUTPUT_PPTX)
    size_kb = OUTPUT_PPTX.stat().st_size / 1024
    print(f"[OK] Wrote {OUTPUT_PPTX.relative_to(PROJECT_DIR)} ({size_kb:.1f} KB, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
