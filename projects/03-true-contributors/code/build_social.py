"""
build_social.py — X package images, validation and preview
==========================================================

1. Renders every chart image from data/data.json with the shared Renball
   matplotlib theme (assets/social/renball_chart_style.py) into
   social/images/ — landscape 1600x900 and portrait 1080x1350. Landscape
   charts show fewer rows: at phone-legible type, about six fit.
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
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "assets" / "social"))

import renball_chart_style as S  # noqa: E402
import renball_social as X       # noqa: E402

DATA = json.loads((PROJECT_DIR / "data" / "data.json").read_text(encoding="utf-8"))
IMAGES = PROJECT_DIR / "social" / "images"
NUM = PROJECT_DIR.name.split("-")[0]
EYEBROW = f"Renball research · {NUM}"
Q = DATA["quality"]
SOURCE = f"FBref · top 5 leagues · {Q['first_season']} to {Q['last_season']}"
B, REP, AW, S2, EF = DATA["board"], DATA["repeatability"], DATA["awards"], DATA["sca2"], DATA["efficiency"]
LANDSCAPE_ROWS = 6        # 15 pt ticks fit about six rows under a two-line header at 1600 x 900


def fx(x: float, d: int = 2) -> str:
    """Half-up on the shortest decimal form (the page's rounding); true minus sign."""
    return str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)).replace("-", "−")


def per_format(name: str, draw, *, title: str, subtitle, source: str = SOURCE) -> None:
    """Render landscape and portrait separately: draw(ax, f) can show fewer rows on the wide format;
    subtitle may be a function of the format name."""
    for fmt in ("landscape", "portrait"):
        S.export(draw, IMAGES, name, formats=(fmt,), eyebrow=EYEBROW, title=title,
                 subtitle=subtitle(fmt) if callable(subtitle) else subtitle, source=source)


def hbars(ax, f, rows, *, colors, label_fmt, xmax):
    """Horizontal bars from zero with an interval whisker and the value printed after it."""
    ys = list(range(len(rows)))[::-1]
    for y, (label, v, lo, hi), c in zip(ys, rows, colors):
        ax.barh(y, v, color=c, height=0.62, edgecolor="none")
        ax.plot([lo, hi], [y, y], color=S.TEXT, lw=1.6)
        ax.text(hi + xmax * 0.012, y, label_fmt(v), va="center", color=S.TEXT,
                fontsize=f["size"]["annot"], family=S.MONO)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, xmax)
    ax.grid(False)
    ax.grid(axis="x", color=S.BORDER, lw=0.9)


def hook_chart() -> None:
    """Post 1: the adjusted board with intervals; the two sure players in accent."""
    def draw(ax, f):
        top = B["top"][:LANDSCAPE_ROWS if f["name"] == "landscape" else 10]
        rows = [(p["player"], p["theta"], p["theta_lo"], p["theta_hi"]) for p in top]
        colors = [S.ACCENT if (p.get("p_top10_pct") or 0) >= 95 else S.TEXT_MUTED for p in top]
        hbars(ax, f, rows, colors=colors, label_fmt=lambda v: fx(v), xmax=1.0)
        ax.set_xlabel("Expected points added per 90, adjusted")

    per_format("01_hook", draw, title="Two players are *sure*. Then a shortlist.",
               subtitle=lambda fmt: (f"Green: top 10 in 95%+ of simulations · lines: plausible range (95%)\n"
                                     f"{B['eligible']:,} players with {B['min_minutes']:,}+ minutes"
                                     if fmt == "landscape" else
                                     f"Green: top 10 in 95%+ of simulations\n"
                                     f"lines: plausible range (95%) · {B['eligible']:,} players"))


def raw_chart() -> None:
    gone = set(B["raw_top10_dropped_names"])

    def draw(ax, f):
        land = f["name"] == "landscape"
        raw = B["raw_top"]
        if land:     # the short careers that drop out, against the two players who stay on top
            raw = [p for p in raw if p["player"] in gone or p["rank"] <= 2]
        ys = list(range(len(raw)))[::-1]
        for y, p in zip(ys, raw):
            c = S.TEXT_MUTED if p["player"] in gone else S.ACCENT
            ax.plot([p["theta"], p["p90"]], [y, y], color=S.TEXT_MUTED, lw=2.5)
            ax.plot([p["p90"]], [y], "o", mfc="none", mec=S.TEXT_SECONDARY, ms=12, mew=2)
            ax.plot([p["theta"]], [y], "o", color=c, ms=12)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{p['player']} · {p['minutes']:,} min" if land else
                            f"{p['player']}\n{p['minutes']:,} min" for p in raw])
        ax.set_xlim(0.4, 1.0)
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel("EP per 90")

    def subtitle(fmt):
        if fmt == "landscape":
            return (f"Grey: the {B['raw_top10_dropped']} short careers in the raw top 10, all gone once adjusted\n"
                    f"circle: EP per 90 as measured · dot: adjusted")
        return (f"{B['raw_top10_dropped']} of the 10 highest raw rates (grey) drop out\n"
                f"circle: as measured · dot: adjusted for minutes")

    per_format("02_raw", draw, title="The raw top 10 *misleads*", subtitle=subtitle)


def repeat_chart() -> None:
    keys = ["inv_p90", "p90", "sca2_share", "ep_per_inv"]
    names = {"inv_p90": "Involvements per 90", "p90": "EP per 90", "sca2_share": "SCA2 share",
             "ep_per_inv": "EP per involvement"}

    def draw(ax, f):
        ys = list(range(len(keys)))[::-1]
        for y, k in zip(ys, keys):
            x = REP[k]
            c = S.TEXT_MUTED if k == "ep_per_inv" else S.ACCENT
            ax.plot([x["lo"], x["hi"]], [y, y], color=S.TEXT_SECONDARY, lw=7, solid_capstyle="butt", alpha=0.6)
            ax.plot([x["r"]], [y], "o", color=c, ms=14, zorder=3)
            ax.text(x["hi"] + 0.025, y, fx(x["r"]), ha="left", va="center", color=S.TEXT,
                    fontsize=f["size"]["annot"] * 1.1, family=S.MONO)
        ax.set_yticks(ys)
        ax.set_yticklabels([names[k] for k in keys])
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(keys) - 0.2)
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel("Correlation with the next season")

    per_format("03_repeat", draw, title="Volume repeats. Decisiveness *doesn't*.",
               subtitle=f"Players with {REP['min_minutes']:,}+ minutes in two seasons in a row\n"
                        f"0 = no link, 1 = identical · lines: plausible range (95%)")


def awards_chart() -> None:
    rows = [("EP model's pick", AW["exact"], S.ACCENT), ("Goals + assists leader", AW["ga_exact"], S.SECONDARY),
            ("Total EP leader", AW["ep_total_exact"], S.TEXT_MUTED),
            ("Random qualified player", AW["chance_exact"], S.TEXT_MUTED)]

    def draw(ax, f):
        ys = list(range(len(rows)))[::-1]
        for y, (label, v, c) in zip(ys, rows):
            ax.barh(y, v, color=c, height=0.6, edgecolor="none")
            ax.text(v + 0.4, y, fx(v, 1) if v < 1 else f"{v:g}", va="center", color=S.TEXT,
                    fontsize=f["size"]["annot"] * 1.15, family=S.MONO)
        ax.set_yticks(ys)
        ax.set_yticklabels([r[0] for r in rows])
        ax.set_xlim(0, AW["eligible_winners"])
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel(f"Winners named, out of {AW['eligible_winners']}")

    per_format("04_awards", draw, title="Voters follow the *box score*",
               subtitle="Player of the season, five leagues, 2017-18 to 2023-24:\n"
                        "how often each method names the actual winner",
               source=SOURCE)


def sca2_chart() -> None:
    br = S2["top"][1]

    def draw(ax, f):
        top = S2["top"][:LANDSCAPE_ROWS if f["name"] == "landscape" else 8]
        rows = [(p["player"], p["ep_sca2"], p["ep_sca2_lo"], p["ep_sca2_hi"]) for p in top]
        hbars(ax, f, rows, colors=[S.SECONDARY] * len(rows), label_fmt=lambda v: fx(v, 1), xmax=80)
        ax.set_xlabel("EP from the pass before the assist")

    per_format("05_sca2", draw, title="The pass before the *assist*",
               subtitle=f"{br['player']} is second, but his plausible rank runs from {br['rank_lo']} to "
                        f"{br['rank_hi']}\nlines: plausible range (95%)")


def decisive_chart() -> None:
    def draw(ax, f):
        k = 3 if f["name"] == "landscape" else 5
        rows = EF["top"][:k] + EF["bottom"][:k]
        ys = list(range(len(rows)))[::-1]
        ax.axvline(EF["avg"], color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.4)
        for i, (y, p) in enumerate(zip(ys, rows)):
            c = S.ACCENT if i < k else S.TEXT_SECONDARY
            ax.plot([p["lo"], p["hi"]], [y, y], color=c, lw=5, solid_capstyle="butt", alpha=0.6)
            ax.plot([p["ep_per_inv"]], [y], "o", color=c, ms=11, zorder=3)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{p['player']} · {p['team']}" for p in rows])
        ax.set_xlim(0.3, 1.05)
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel("EP per involvement")

    teams = EF["bottom_teams"]
    per_format("06_decisive", draw, title="'Decisive' goals describe the *team*",
               subtitle=f"Dashed: the average goal ({fx(EF['avg'])} EP) · the lowest all played for\n"
                        f"{', '.join(teams[:-1])} or {teams[-1]}")


def takeaways_card() -> None:
    for fmt in ("landscape", "portrait"):
        fig, _ = S.takeaways_card(DATA["takeaways"], fmt, eyebrow=EYEBROW, title="Who should *care*?",
                                  source=SOURCE)
        S.save(fig, IMAGES / f"07_takeaways_{fmt}.png")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hook_chart()
    raw_chart()
    repeat_chart()
    awards_chart()
    sca2_chart()
    decisive_chart()
    takeaways_card()
    return 1 if X.build(PROJECT_DIR) else 0


if __name__ == "__main__":
    sys.exit(main())
