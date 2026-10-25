"""
build_social.py — X package images, validation and preview
==========================================================

1. Renders every chart image from data/data.json with the shared Renball
   matplotlib theme (assets/social/renball_chart_style.py) into
   social/images/ — landscape 1600x900 and portrait 1080x1350.
2. Validates thread.md / posts/ / alt_text.md against the Research Standard
   (post counts, 280-char limit as X counts it, images + alt text present)
   and writes social/preview.html (assets/social/renball_social.py).

The copy itself is hand-written in social/*.md; code/verify.py checks every
number in it against data.json. social/ is gitignored — drafts stay private.

Run:
    python code/build_social.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "assets" / "social"))

import renball_chart_style as S  # noqa: E402
import renball_social as X       # noqa: E402

DATA = json.loads((PROJECT_DIR / "data" / "data.json").read_text(encoding="utf-8"))
IMAGES = PROJECT_DIR / "social" / "images"
NUM = PROJECT_DIR.name.split("-")[0]
EYEBROW = f"Renball research · {NUM}"
P = DATA["primary"]
T, C, TST = P["treatment"], P["control"], P["test"]
RB = DATA["robustness"]
SEASONS = DATA["metadata"]["seasons"]
SOURCE = f"FBref · top 5 leagues · {SEASONS[0][:4]}-{SEASONS[0][-2:]} to {SEASONS[-1][:4]}-{SEASONS[-1][-2:]}"


def sgn(x: float, d: int = 1) -> str:
    return f"{'−' if x < 0 else '+'}{abs(x):.{d}f}"


def dots(ax, f, rows, *, label_fmt="{:.0f}%", horizontal=True) -> None:
    """Dot-and-interval: a dot at each rate, a line for its plausible range (no truncated bars)."""
    for i, (label, v, lo, hi, color) in enumerate(rows):
        if horizontal:
            ax.plot([lo, hi], [i, i], color=color, lw=6, solid_capstyle="butt", alpha=0.85)
            ax.plot([v], [i], "o", color=S.TEXT, ms=13, zorder=3)
            ax.text(v, i + 0.28, label_fmt.format(v), ha="center", va="bottom", color=S.TEXT,
                    fontsize=f["size"]["annot"] * 1.15, family=S.MONO)
        else:
            ax.plot([i, i], [lo, hi], color=color, lw=6, solid_capstyle="butt", alpha=0.85)
            ax.plot([i], [v], "o", color=S.TEXT, ms=11, zorder=3)


def hook_chart() -> None:
    """Post 1: the comparison itself, with its plausible ranges."""
    rows = [(f"Every other penalty\n{C['attempts']:,} penalties", C["rate"], C["ci_lo"], C["ci_hi"], S.SECONDARY),
            (f"Fouled by the keeper,\ntook it himself\n{T['attempts']} penalties", T["rate"], T["ci_lo"], T["ci_hi"],
             S.ACCENT)]

    def draw(ax, f):
        dots(ax, f, rows)
        ax.set_yticks([0, 1])
        ax.set_yticklabels([r[0] for r in rows])
        ax.set_ylim(-0.6, 1.75)
        ax.set_xlim(*S.nice_range([r[2] for r in rows] + [r[3] for r in rows], padding=3))
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel("Penalties scored (%)")

    S.export(draw, IMAGES, "01_hook", eyebrow=EYEBROW,
             title="Fouled by the keeper, taking it *himself*",
             subtitle=f"{T['rate']:.0f}% vs {C['rate']:.0f}%: about {abs(TST['rate_diff_pp']):.0f} points lower\n"
                      f"lines: plausible range (95%), the small group's is wide",
             source=SOURCE)


def forest_rows() -> list[tuple[str, float, float, float]]:
    adj = RB["adjusted"]
    rows = [(r["short"], r["diff_pp"], r["ci_lo"], r["ci_hi"]) for r in RB["controls"]]
    rows.append((adj["short"], adj["gap_pp"], adj["gap_lo"], adj["gap_hi"]))
    rows += [(r["short"], r["diff_pp"], r["ci_lo"], r["ci_hi"]) for r in RB["samples"]]
    return rows[::-1]


def robustness_chart() -> None:
    rows = forest_rows()
    margin = RB["tost"]["margin_pp"]

    def draw(ax, f):
        ys = list(range(len(rows)))
        ax.axvspan(-margin, margin, color=S.ACCENT, alpha=0.08, lw=0)
        ax.axvline(0, color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.2)
        for y, (_, d, lo, hi) in zip(ys, rows):
            top = y == len(rows) - 1
            ax.plot([lo, hi], [y, y], color=S.ACCENT if top else S.TEXT_SECONDARY,
                    lw=4 if top else 3, solid_capstyle="butt")
            ax.plot([d], [y], "o", color=S.ACCENT if top else S.TEXT, ms=9)
        ax.set_yticks(ys)
        ax.set_yticklabels([r[0] for r in rows])
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlim(min(r[2] for r in rows) - 2, max(r[3] for r in rows) + 2)
        ax.set_xlabel("Gap vs comparison (pp)")

    S.export(draw, IMAGES, "02_robustness", eyebrow=EYEBROW,
             title="Every check *straddles zero*",
             subtitle=f"Gap with its plausible range (95%) · shaded: within {margin:.0f} points either way",
             source=SOURCE)


def posterior_chart() -> None:
    """Bayesian view: the posterior of the gap (Beta(1,1) priors, same draws as build.py)."""
    bay, margin = RB["bayes"], RB["tost"]["margin_pp"]
    rng = np.random.default_rng(2026)
    n = bay["draws"]
    diff = (rng.beta(1 + T["conversions"], 1 + T["attempts"] - T["conversions"], n)
            - rng.beta(1 + C["conversions"], 1 + C["attempts"] - C["conversions"], n)) * 100
    hist, edges = np.histogram(diff, bins=160, range=(-30, 20), density=True)
    mids = (edges[:-1] + edges[1:]) / 2

    def draw(ax, f):
        ax.fill_between(mids, hist, where=mids < 0, color=S.ACCENT, alpha=0.35, lw=0)
        ax.fill_between(mids, hist, where=mids >= 0, color=S.TEXT_MUTED, alpha=0.35, lw=0)
        ax.plot(mids, hist, color=S.TEXT, lw=1.6)
        ax.axvline(0, color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.2)
        ax.axvline(-margin, color=S.ACCENT, ls=(0, (2, 3)), lw=1)
        ax.set_yticks([])
        ax.set_xlim(-30, 20)
        ax.set_xlabel("Gap: fouled taker minus everyone else (points)")
        S.callout(ax, f"{bay['p_lower_pct']:.0f}% below zero", xy=(-6, hist.max() * 0.55),
                  xytext=(-27, hist.max() * 0.85), f=f)

    S.export(draw, IMAGES, "03_posterior", eyebrow=EYEBROW,
             title="Leaning one way, *not settled*",
             subtitle=f"How likely each size of gap is · a {bay['p_drop_beyond_margin_pct']:.0f}% chance the drop\n"
                      f"is bigger than {margin:.0f} points (left of the dotted line)",
             source=SOURCE)


def taker_chart() -> None:
    est = RB["established"]
    rows = [("Whole-season\ndefinition", est["season_definition"]), ("Before-the-kick\ndefinition", est["vs_other"])]

    def draw(ax, f):
        xs = [0, 1]
        vals = [r[1]["diff_pp"] for r in rows]
        bars = ax.bar(xs, vals, width=0.5, color=[S.TEXT_MUTED, S.ACCENT])
        S.ci_whiskers(ax, xs, [r[1]["ci_lo"] for r in rows], [r[1]["ci_hi"] for r in rows])
        ax.axhline(0, color=S.TEXT_MUTED, lw=1)
        ax.set_ylim(-4, 18)
        ax.set_xticks(xs)
        ax.set_xticklabels([r[0] for r in rows])
        ax.set_ylabel("Regular taker's edge (points)")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() + 0.04, v, f"{sgn(v, 1)}", va="center",
                    color=S.TEXT, fontsize=f["size"]["annot"], family=S.MONO)

    S.export(draw, IMAGES, "04_taker", eyebrow=EYEBROW,
             title="The specialist's edge *mostly vanishes*",
             subtitle="Define the taker from the whole season and the result leaks in:\n"
                      "takers who miss lose the job · lines: plausible ranges (95%)",
             source=SOURCE)


def repeat_card() -> None:
    rep = RB["repeatability"]
    for fmt in ("landscape", "portrait"):
        fig, _ = S.stat_card(f"{rep['spearman_brown']:.2f}".replace("-", "−"), "half a record vs the other half", fmt,
                             eyebrow=EYEBROW, title="A penalty record *barely repeats*",
                             sub=f"{rep['n_takers']} takers with {rep['min_attempts']}+ kicks · 0 = no link, 1 = a "
                                 f"reliable skill · range {rep['sb_lo']:.2f} to {rep['sb_hi']:.2f}".replace("-", "−"),
                             source=SOURCE)
        S.save(fig, IMAGES / f"05_repeat_{fmt}.png")


def league_chart() -> None:
    blocks = P["by_league"]
    short = {"Premier League": "PL", "La Liga": "LaLiga", "Serie A": "Serie A", "Bundesliga": "BuLi", "Ligue 1": "Ligue 1"}

    def draw(ax, f):
        w = 0.17
        for i, b in enumerate(blocks):
            for off, grp, color in ((-w, b["treatment"], S.ACCENT), (w, b["control"], S.SECONDARY)):
                ax.plot([i + off, i + off], [grp["ci_lo"], grp["ci_hi"]], color=color, lw=6, solid_capstyle="butt",
                        alpha=0.85)
                ax.plot([i + off], [grp["rate"]], "o", color=S.TEXT, ms=10, zorder=3)
        ax.set_ylim(*S.nice_range([b["treatment"]["ci_lo"] for b in blocks] +
                                  [b["treatment"]["ci_hi"] for b in blocks], padding=3))
        ax.set_xticks(range(len(blocks)))
        ax.set_xticklabels([f"{short.get(b['label'], b['label'])}\n{b['treatment']['attempts']} kicks" for b in blocks])
        ax.set_ylabel("Penalties scored (%)")

    md = DATA["metadata"]
    S.export(draw, IMAGES, "06_league", eyebrow=EYEBROW,
             title="League by league it *looks* dramatic",
             subtitle=f"Green: keeper fouled the taker ({md['treatment_n_by_league_min']} to "
                      f"{md['treatment_n_by_league_max']} kicks) · blue: the rest\n"
                      f"allowing for five tests, none stands out · lines: plausible ranges",
             source=SOURCE)


def takeaways_card() -> None:
    for fmt in ("landscape", "portrait"):
        fig, _ = S.takeaways_card(DATA["takeaways"], fmt, eyebrow=EYEBROW, title="Who should *care*?",
                                  source=SOURCE)
        S.save(fig, IMAGES / f"07_takeaways_{fmt}.png")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hook_chart()
    robustness_chart()
    posterior_chart()
    taker_chart()
    repeat_card()
    league_chart()
    takeaways_card()
    return 1 if X.build(PROJECT_DIR) else 0


if __name__ == "__main__":
    sys.exit(main())
