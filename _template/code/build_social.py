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

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "assets" / "social"))

import renball_chart_style as S  # noqa: E402
import renball_social as X       # noqa: E402

DATA = json.loads((PROJECT_DIR / "data" / "data.json").read_text(encoding="utf-8"))
IMAGES = PROJECT_DIR / "social" / "images"
NUM = PROJECT_DIR.name.split("-")[0]
EYEBROW = f"Renball research · {NUM}"
SOURCE = "[Source · scope · n]"


def hook_card() -> None:
    """Post 1: one headline number, big."""
    for fmt in ("landscape", "portrait"):
        fig, _ = S.stat_card("[value]", "[what the number is]", fmt, eyebrow=EYEBROW,
                             title="[Hook with an *accent*]", sub="[comparison / interval]",
                             source=SOURCE)
        S.save(fig, IMAGES / f"01_hook_{fmt}.png")


def finding_chart() -> None:
    """One chart = one idea. Copy this per finding."""
    def draw(ax, f):
        bars = ax.bar(["A", "B"], [1, 2], color=[S.ACCENT, S.SECONDARY])
        S.label_bars(ax, bars, "{:.1f}", f)

    S.export(draw, IMAGES, "02_finding", eyebrow=EYEBROW,
             title="[Finding headline with an *accent*]", subtitle="[What the chart shows]",
             source=SOURCE)


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    hook_card()
    finding_chart()
    return 1 if X.build(PROJECT_DIR) else 0


if __name__ == "__main__":
    sys.exit(main())
