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
from decimal import ROUND_HALF_UP, Decimal
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
SEASONS = DATA["meta"]["seasons"]
def short(season: str) -> str:
    return f"{season[:4]}-{season[-2:]}"


SOURCE = f"FBref · 6 leagues · {short(SEASONS[0])} to {short(SEASONS[-1])}"
H, GS, CAL, RB, PL = DATA["headline"], DATA["game_state"], DATA["calibration"], DATA["robustness"], DATA["players"]
BINS = DATA["meta"]["time_bins"]


def fx(x: float, d: int = 2) -> str:
    """Half-up on the shortest decimal form (the page's rounding); true minus sign."""
    return str(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)).replace("-", "−")


def hook_chart() -> None:
    """Post 1: the go-ahead goal from level, by window, with intervals."""
    ob, op = H["opener_by_bin"], H["opener_ratio"]

    def draw(ax, f):
        xs = np.arange(len(ob))
        vals = [c["ep"] for c in ob]
        ax.bar(xs, vals, width=0.62, color=[S.ACCENT if i == len(ob) - 1 else S.TEXT_SECONDARY for i in xs])
        S.ci_whiskers(ax, xs, [c["lo"] for c in ob], [c["hi"] for c in ob])
        for x, c in zip(xs, ob):
            ax.text(x, c["hi"] + 0.04, fx(c["ep"]), ha="center", va="bottom", color=S.TEXT,
                    fontsize=f["size"]["annot"], family=S.MONO)
        ax.set_xticks(xs)
        ax.set_xticklabels(BINS)
        ax.set_ylim(0, 1.8)
        ax.set_xlabel("Minute window")
        ax.set_ylabel("Expected points per goal")

    S.export(draw, IMAGES, "01_hook", eyebrow=EYEBROW,
             title=f"The same goal, *{fx(op['value'])}×* the value",
             subtitle=f"Going ahead from level: {fx(op['early']['ep'])} EP in the first 15 minutes,\n"
                      f"{fx(op['late']['ep'])} in the last 15 · lines: plausible ranges (95%)",
             source=SOURCE)


def state_chart() -> None:
    sv = DATA["state_values"]
    rows = [i for i, g in enumerate(sv["gd_range"]) if abs(g) <= 2][::-1]
    M = np.array([[c["ep"] for c in sv["matrix"][i]] for i in rows])

    def draw(ax, f):
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("rb", [S.BG_CARD, S.ACCENT])
        ax.imshow(M, cmap=cmap, vmin=0, vmax=3, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                ax.text(j, i, fx(M[i, j]), ha="center", va="center", family=S.MONO,
                        fontsize=f["size"]["annot"], color=S.BG if M[i, j] > 1.8 else S.TEXT)
        ax.set_xticks(range(len(BINS)))
        ax.set_xticklabels(BINS)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([sv["gd_labels"][i] for i in rows])
        ax.grid(False)
        ax.set_xlabel("Minute window")
        ax.set_ylabel("Goal difference")

    st = H["states"]
    S.export(draw, IMAGES, "02_states", eyebrow=EYEBROW,
             title="What a scoreline is *worth*, minute by minute",
             subtitle=f"Expected final points · one goal up: {fx(st['lead_early'])} early, {fx(st['lead_late'])} late\n"
                      f"from every minute of every match",
             source=SOURCE)


def game_state_chart() -> None:
    rows = GS["rows"]

    def draw(ax, f):
        xs = np.arange(len(BINS))
        colors = {1: S.SECONDARY, 0: S.ACCENT, -1: S.PALETTE[2]}
        for r in rows:
            ratios = [c["ratio"] for c in r["bins"]]
            ax.plot(xs, ratios, marker="o", lw=2.5, color=colors[r["gd"]])
            ax.fill_between(xs, [c["lo"] for c in r["bins"]], [c["hi"] for c in r["bins"]],
                            color=colors[r["gd"]], alpha=0.15, lw=0)
            ax.text(xs[-1] + 0.15, ratios[-1], r["label"].replace(" by one", ""), va="center",
                    color=colors[r["gd"]], fontsize=f["size"]["annot"])
        ax.axhline(1, color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.2)
        ax.set_yscale("log")
        ax.set_yticks([0.2, 0.5, 1, 2, 5])
        ax.set_yticklabels(["0.2×", "0.5×", "1×", "2×", "5×"])
        ax.set_xticks(xs)
        ax.set_xticklabels(BINS)
        ax.set_xlim(-0.3, len(BINS) + 0.9)
        ax.set_xlabel("Minute window")
        ax.set_ylabel("Goal for ÷ goal against")

    lv = GS["level_late"]
    S.export(draw, IMAGES, "03_next_goal", eyebrow=EYEBROW,
             title="Level late? The upside *beats* the downside",
             subtitle=f"Next goal for ÷ next goal against · level in the last 15:\n"
                      f"{fx(lv['up'])} for vs {fx(lv['down'])} against = {fx(lv['ratio'])}× · bands: plausible ranges",
             source=SOURCE)


def calibration_chart() -> None:
    bb = CAL["by_bin"]

    def draw(ax, f):
        xs = np.arange(len(bb))
        w = 0.38
        ax.bar(xs - w / 2, [b["timed"] for b in bb], w, color=S.ACCENT, label="Knows the minute")
        ax.bar(xs + w / 2, [b["untimed"] for b in bb], w, color=S.SECONDARY, label="Score only")
        ax.set_xticks(xs)
        ax.set_xticklabels(BINS)
        ax.set_ylim(0, 1.0)
        ax.set_xlabel("Minute window")
        ax.set_ylabel("Prediction error (Brier)")
        ax.legend(frameon=False, labelcolor=S.TEXT_SECONDARY, fontsize=f["size"]["annot"], ncol=2,
                  loc="upper right")

    S.export(draw, IMAGES, "04_held_out", eyebrow=EYEBROW,
             title="It predicts seasons it *never saw*",
             subtitle=f"Fit on {short(SEASONS[0])} to {short(CAL['train_seasons'][-1])}, tested on "
                      f"{short(CAL['test_seasons'][0])} and {short(CAL['test_seasons'][-1])}\n"
                      f"lower is better · overall {fx(CAL['brier']['timed'], 3)} vs {fx(CAL['brier']['untimed'], 3)}",
             source=SOURCE)


def leagues_chart() -> None:
    rows = sorted(RB["by_league"], key=lambda x: x["ratio"])

    def draw(ax, f):
        ys = np.arange(len(rows))
        ax.axvline(1, color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.2)
        for y, r in zip(ys, rows):
            ax.plot([r["lo"], r["hi"]], [y, y], color=S.TEXT_SECONDARY, lw=3, solid_capstyle="butt")
            ax.plot([r["ratio"]], [y], "o", color=S.ACCENT, ms=10)
            ax.text(r["hi"] + 0.05, y, f"{fx(r['ratio'])}×", va="center", color=S.TEXT,
                    fontsize=f["size"]["annot"], family=S.MONO)
        ax.set_yticks(ys)
        ax.set_yticklabels([r["label"] for r in rows])
        ax.set_xlim(0.8, 3.2)
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel("Late go-ahead goal ÷ early go-ahead goal")

    S.export(draw, IMAGES, "05_leagues", eyebrow=EYEBROW,
             title="Every league, *same story*",
             subtitle=f"Last 15 vs first 15, go-ahead goal from level · range {fx(RB['league_ratio_min'])}× to "
                      f"{fx(RB['league_ratio_max'])}×\nlines: plausible ranges (95%) · dashed: no difference",
             source=SOURCE)


def _forest(rows, name, title, subtitle, xlabel, *, zero=False, sign=False):
    rows = rows[::-1]

    def draw(ax, f):
        ys = np.arange(len(rows))
        if zero:
            ax.axvline(0, color=S.TEXT_MUTED, ls=(0, (4, 4)), lw=1.2)
        for y, (label, v, lo, hi) in zip(ys, rows):
            top = y == len(rows) - 1
            ax.plot([lo, hi], [y, y], color=S.ACCENT if top else S.TEXT_SECONDARY, lw=4 if top else 3,
                    solid_capstyle="butt")
            ax.plot([v], [y], "o", color=S.ACCENT if top else S.TEXT, ms=9)
        ax.set_yticks(ys)
        ax.set_yticklabels([r[0] for r in rows])
        ax.grid(False)
        ax.grid(axis="x", color=S.BORDER, lw=0.9)
        ax.set_xlabel(xlabel)

    S.export(draw, IMAGES, name, eyebrow=EYEBROW, title=title, subtitle=subtitle, source=SOURCE)


def premium_chart() -> None:
    ps = PL["premium_summary"]
    rows = [(p["player"], p["premium"], p["premium_lo"], p["premium_hi"]) for p in PL["top_premium"][:6]]
    _forest(rows, "06_clutch", "Clutch? Not beyond *chance*",
            f"Timing premium: EP above the same goals scored at average times\n"
            f"only {ps['ci_above_zero']} of {ps['eligible']:,} players clearly above zero · chance alone: "
            f"~{ps['expected_by_chance_each_side']}",
            "Timing premium (EP)", zero=True)


def top_chart() -> None:
    ts = PL["top_ep_summary"]
    rows = [(p["player"], p["ep"], p["ep_lo"], p["ep_hi"]) for p in PL["top_ep"][:5]]
    _forest(rows, "07_top5", "The top five: a *statistical tie*",
            f"Expected points collected from goals + assists, {short(SEASONS[0])} to {short(SEASONS[-1])}\n"
            f"within {fx(ts['top5_spread'])} of each other · lines: plausible ranges (95%)",
            "EP collected")


def takeaways_card() -> None:
    for fmt in ("landscape", "portrait"):
        fig, _ = S.takeaways_card(DATA["takeaways"], fmt, eyebrow=EYEBROW, title="Who should *care*?", source=SOURCE)
        S.save(fig, IMAGES / f"08_takeaways_{fmt}.png")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hook_chart()
    state_chart()
    game_state_chart()
    calibration_chart()
    leagues_chart()
    premium_chart()
    top_chart()
    takeaways_card()
    return 1 if X.build(PROJECT_DIR) else 0


if __name__ == "__main__":
    sys.exit(main())
