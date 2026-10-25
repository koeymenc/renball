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
    (r"\b(?:after|before|from|until|past)\s(?:15|30|45|60|75|90)'", "window boundary minute in prose"),
    (r"\b\d{1,2}(?:st|nd|rd|th)\b", "illustrative minute (5th, 85th, the 75th and the 90th)"),
    (r"\b(?:first|last|final|opening)\s15\b", "window width in prose"),
]

ANCHORS = [
    # A one-goal lead early and late: the same values sit in the state table, so pin them.
    (r"(?:[Oo]ne goal up|[Oo]ne-goal lead|One up)[^.;]{0,40}?\d\.\d+(?= (?:points )?(?:in the first 15|early))",
     "$.headline.states.lead_early"),
    (r"(?:[Oo]ne goal up|[Oo]ne-goal lead|One up)[^;]{0,90}?(?:early|first 15 minutes),? (?:and )?\d\.\d+"
     r"(?= (?:in the last 15|late))", "$.headline.states.lead_late"),
    # The go-ahead goal from level, late
    (r"(?<=first 15 minutes and )\d\.\d+(?= in the last 15)", "$.headline.opener_ratio.late.ep"),
    (r"late equaliser is worth \d\.\d+", "$.headline.late_equaliser.ep"),
    (r"late second goal at 1–0 only \d\.\d+", "$.headline.late_cushion.ep"),
    # Game state, level and 1–0 up after 75' (a ratio like 1.58× is not a goal value)
    (r"goal for is worth \*{0,2}\d\.\d+(?![\d×])|\d\.\d+(?= EP for\b)", "$.game_state.level_late.up"),
    (r"goal against costs \d\.\d+|(?<=EP for · )\d\.\d+(?= EP against)", "$.game_state.level_late.down"),
    (r"conceding costs \*{0,2}\d\.\d+", "$.game_state.lead_late.down"),
    (r"second goal adds (?:only )?\d\.\d+", "$.game_state.lead_late.up"),
    (r"ratio 95% CI \d\.\d+(?=–\d\.\d+ · values)", "$.game_state.lead_late.lo"),
    (r"(?<=ratio 95% CI \d\.\d\d–)\d\.\d+(?= · values)", "$.game_state.lead_late.hi"),
    (r"Leading by one \| \d\.\d\d×", "$.game_state.rows[0].bins[0].ratio"),
    # Spread of the top five
    (r"within \d+\.\d+(?= EP| of each other)|\d+\.\d+(?= EP between first and fifth)",
     "$.players.top_ep_summary.top5_spread"),
]

if __name__ == "__main__":
    sys.exit(V.main(PROJECT_DIR, allow=ALLOW, anchors=ANCHORS, argv=sys.argv[1:]))
