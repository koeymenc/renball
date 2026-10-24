"""
verify.py — Renball Research Standard check for this project
============================================================

Fails if any number in analysis.html (rendered), dashboard.html, slides.pptx,
methodology.md, social/ or config.json doesn't trace to data/data.json at
the precision shown — and if any deliverable is missing, stale or
inconsistent. See assets/build/renball_verify.py.

Add an ALLOW rule only for numbers that are not data claims (an illustrative
minute, a hypothetical effect size) and always say why. If a number IS a
data claim, put it in data.json via build.py instead.

Run:
    python code/verify.py              # numbers + standard
    python code/verify.py --report     # also list each matched number's data.json path
    python code/verify.py --static     # skip the headless render of analysis.html
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR.parents[1] / "assets" / "build"))

import renball_verify as V  # noqa: E402

ALLOW = [
    # (r"\b85th minute", "illustrative minute in the hook, not a data claim"),
]

if __name__ == "__main__":
    sys.exit(V.main(PROJECT_DIR, allow=ALLOW, argv=sys.argv[1:]))
