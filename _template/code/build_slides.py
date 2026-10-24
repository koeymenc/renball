"""
build_slides.py — slides.pptx for this project
==============================================

Every number comes from ../data/data.json; every style from
assets/slides/renball_slide_master.py (never reimplement styling here).
Default narrative (CLAUDE.md §5): title → TL;DR → context → data & method →
results (one chart per slide) → who should care → limitations →
conclusion → sources.

Run:
    python code/build_slides.py
    python code/build_pdfs.py --only slides      # export slides.pdf via PowerPoint
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "assets" / "slides"))

import renball_slide_master as R  # noqa: E402

DATA_JSON = PROJECT_DIR / "data" / "data.json"
OUTPUT_PPTX = PROJECT_DIR / "slides.pptx"
PROJECT_NUM = PROJECT_DIR.name.split("-")[0]


def main() -> None:
    d = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    prs = R.create_deck()

    R.add_title_slide(prs, "[Project title with an *accent* phrase]",
                      subtitle="[METHOD · SCOPE]", date="[Month Year]", project_num=PROJECT_NUM)
    R.add_bullet_slide(prs, "TL;DR", ["[Question]", "[Method in one line]", "[Headline result + interval]"],
                       eyebrow="TL;DR")
    # ... context, data & method, one results slide per chart (R.add_chart_slide) ...
    R.add_takeaways_slide(prs, d["takeaways"])
    R.add_bullet_slide(prs, "What this *can't* tell you", ["[Limitation 1]", "[Limitation 2]"],
                       eyebrow="LIMITATIONS")
    R.add_closing_slide(prs, headline="Full methodology, source code and data:",
                        project_path=f"/projects/{PROJECT_DIR.name}/")
    R.finalize_deck(prs)

    prs.save(OUTPUT_PPTX)
    print(f"[OK] Wrote {OUTPUT_PPTX.name} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
