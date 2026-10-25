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
SOURCE = f"FBref · top 5 leagues · {DATA['metadata']['seasons'][0]} to {DATA['metadata']['seasons'][-1]}"


def sgn(x: float, d: int = 1) -> str:
    return f"{'−' if x < 0 else '+'}{abs(x):.{d}f}"


def hook_chart() -> None:
    """Post 1: the comparison itself, with its intervals."""
    def draw(ax, f):
        xs = [0, 1]
        rates = [T["rate"], C["rate"]]
        bars = ax.bar(xs, rates, width=0.55, color=[S.ACCENT, S.SECONDARY])
        lo, hi = S.nice_range([T["ci_lo"], T["ci_hi"] + 4, C["ci_lo"], C["ci_hi"]], padding=3)
        ax.set_ylim(lo, hi)
        S.ci_whiskers(ax, xs, [T["ci_lo"], C["ci_lo"]], [T["ci_hi"], C["ci_hi"]])
        for x, r, top in zip(xs, rates, [T["ci_hi"], C["ci_hi"]]):
            ax.text(x, top + (hi - lo) * 0.03, f"{r:.2f}%", ha="center", va="bottom",
                    color=S.TEXT, fontsize=f["size"]["annot"] * 1.3, family=S.MONO)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"Fouled by the GK,\ntook it himself\nn = {T['attempts']}",
                            f"Every other\npenalty\nn = {C['attempts']:,}"])
        ax.set_ylabel("Conversion (%)")

    S.export(draw, IMAGES, "01_hook", eyebrow=EYEBROW,
             title="Fouled by the keeper, taking it *himself*",
             subtitle=f"Gap {sgn(TST['rate_diff_pp'], 2)} pp · 95% CI {sgn(TST['diff_ci_lo'])} to "
                      f"{sgn(TST['diff_ci_hi'])} pp · whiskers: 95% CIs",
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
             subtitle=f"Gap with 95% interval · shaded: ±{margin:.0f} pp = no practical difference",
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
        ax.set_xlabel("Gap: fouled taker minus everyone else (pp)")
        S.callout(ax, f"{bay['p_lower_pct']:.1f}% below zero", xy=(-6, hist.max() * 0.55),
                  xytext=(-27, hist.max() * 0.85), f=f)

    S.export(draw, IMAGES, "03_posterior", eyebrow=EYEBROW,
             title="Leaning one way, *not settled*",
             subtitle=f"Bayesian posterior, flat priors · {bay['p_drop_beyond_margin_pct']:.1f}% chance the drop\n"
                      f"exceeds {margin:.0f} pp (left of the dotted line)",
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
        ax.set_ylabel("Established taker's edge (pp)")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() + 0.04, v, f"{sgn(v, 2)} pp", va="center",
                    color=S.TEXT, fontsize=f["size"]["annot"], family=S.MONO)

    S.export(draw, IMAGES, "04_taker", eyebrow=EYEBROW,
             title="The specialist's edge *mostly vanishes*",
             subtitle="Define the taker from the whole season and the outcome leaks in:\n"
                      "takers who miss lose the job · whiskers: 95% CIs",
             source=SOURCE)


def repeat_card() -> None:
    rep = RB["repeatability"]
    for fmt in ("landscape", "portrait"):
        fig, _ = S.stat_card(f"{rep['spearman_brown']:.2f}", "split-half reliability of conversion", fmt,
                             eyebrow=EYEBROW, title="A penalty record *barely repeats*",
                             sub=f"{rep['n_takers']} takers with {rep['min_attempts']}+ kicks · 95% CI "
                                 f"{rep['sb_lo']:.2f} to {rep['sb_hi']:.2f}",
                             source=SOURCE)
        S.save(fig, IMAGES / f"05_repeat_{fmt}.png")


def league_chart() -> None:
    blocks = P["by_league"]

    def draw(ax, f):
        xs = np.arange(len(blocks))
        w = 0.36
        t_rates = [b["treatment"]["rate"] for b in blocks]
        c_rates = [b["control"]["rate"] for b in blocks]
        ax.bar(xs - w / 2, t_rates, w, color=S.ACCENT, label="GK fouled the taker")
        ax.bar(xs + w / 2, c_rates, w, color=S.SECONDARY, label="Every other penalty")
        S.ci_whiskers(ax, xs - w / 2, [b["treatment"]["ci_lo"] for b in blocks],
                      [b["treatment"]["ci_hi"] for b in blocks], cap=0.05)
        ax.set_ylim(*S.nice_range([b["treatment"]["ci_lo"] for b in blocks] +
                                  [b["treatment"]["ci_hi"] for b in blocks], padding=2))
        ax.set_xticks(xs)
        short = {"Premier League": "PL", "La Liga": "LaLiga", "Serie A": "Serie A",
                 "Bundesliga": "BuLi", "Ligue 1": "Ligue 1"}
        ax.set_xticklabels([f"{short.get(b['label'], b['label'])}\nn = {b['treatment']['attempts']}" for b in blocks])
        ax.set_ylabel("Conversion (%)")

    S.export(draw, IMAGES, "06_league", eyebrow=EYEBROW,
             title="League by league it *looks* dramatic",
             subtitle=f"Green: GK fouled the taker (n = {DATA['metadata']['treatment_n_by_league_min']}–"
                      f"{DATA['metadata']['treatment_n_by_league_max']}) · blue: every other penalty\n"
                      f"After a Holm correction none is significant · whiskers: 95% CIs",
             source=SOURCE)


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hook_chart()
    robustness_chart()
    posterior_chart()
    taker_chart()
    repeat_card()
    league_chart()
    return 1 if X.build(PROJECT_DIR) else 0


if __name__ == "__main__":
    sys.exit(main())
