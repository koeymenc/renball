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

Every matched number must also be anchored — unique in data.json, or next to
its sibling figures. A number that fails as WEAK (several different values
show as it) gets an ANCHORS rule: a regex around the number and the
data.json path it comes from; the verifier then checks it against that path.

Run:
    python code/verify.py              # numbers + standard
    python code/verify.py --report     # also list each matched number, its path + anchor
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

ANCHORS = [
    # (r"late go-ahead goal\D{0,60}\d\.\d+×", "$.early_vs_late.ratio"),
]

if __name__ == "__main__":
    sys.exit(V.main(PROJECT_DIR, allow=ALLOW, anchors=ANCHORS, argv=sys.argv[1:]))
