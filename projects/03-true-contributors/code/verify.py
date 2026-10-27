"""
verify.py — Renball Research Standard check for this project
============================================================

Fails if any number in analysis.html (rendered), dashboard.html, slides.pptx,
methodology.md, social/ or config.json doesn't trace to data/data.json at
the precision shown — and if any deliverable is missing, stale or
inconsistent. See assets/build/renball_verify.py.

Add an ALLOW rule only for numbers that are not data claims (a display
cut-off, a reference date) and always say why. If a number IS a data claim,
put it in data.json via build.py instead.

Every matched number must also be anchored — unique in data.json, or next to
its sibling figures. A number that fails as WEAK (several different values
show as it) gets an ANCHORS rule: a regex around the number and the
data.json path it comes from; the verifier then checks it against that path.
Player boards repeat the same two-decimal rates many times over, so the
anchors below also bind a player's name to his own row (built from
data.json, so they follow a rebuild).

Run:
    python code/verify.py              # numbers + standard
    python code/verify.py --report     # also list each matched number, its path + anchor
    python code/verify.py --static     # skip the headless render of analysis.html
"""

import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR.parents[1] / "assets" / "build"))

import renball_verify as V  # noqa: E402

DATA = json.loads((PROJECT_DIR / "data" / "data.json").read_text(encoding="utf-8"))

ALLOW = [
    (r"\b[Tt]op[ -](?:15|20)\b", "display cut-off of a chart or table"),
    (r"\b(?:first|last|final|opening)\s15\b", "window width in prose (Project 02's goal prices)"),
    (r"\b30 June 2024\b", "reference date for ages: the end of the data"),
    (r"\b40/35/25\b", "the split rule's weights (also in data.json as meta.params.weights_pct)"),
    (r"\b95\s?%(?=\s*(?:range|of the time|or more|of simulations|:))|clears 95\s?%|95\s?%\+",
     "interval level / top-10 threshold"),
    (r"\b2\.5\s?% per side", "chance rate on each side of a 95% interval"),
    (r"\d+\(\d+\),\s*\d+–\d+", "journal volume, issue and pages in the references"),
]

ANCHORS = [
    # Plausible ranks quoted as "1 to N": Brandt's (SCA2 board) before the number 3's (main board)
    (r"Brandt[^.]{0,60}?1 to \d+", "$.sca2.top[1].rank_hi"),
    (r"(?<=anywhere from 1 to )\d+", "$.board.top[2].rank_hi"),
    (r"(?:ranks?|rank of|rank) 1 to \d+", "$.board.top[2].rank_hi"),
    # The two sure players, quoted together
    (r"clear of everyone at \d\.\d\d", "$.board.top[0].theta"),
    (r"(?<=clear of everyone at \d\.\d\d and )\d\.\d\d", "$.board.top[1].theta"),
    (r"top 10 in \d+% of (?:our )?simulations", "$.board.top[0].p_top10_pct"),
    (r"[Nn]obody else gets past \d+%", "$.board.top[2].p_top10_pct"),
    # Season-to-season correlations
    (r"EP per 90 (?:repeats|correlates)[^.;]{0,60}?r = \*{0,2}\d\.\d\d", "$.repeatability.p90.r"),
    (r"season-to-season r = \d\.\d\d|per 90 carries over at \d\.\d\d|Volume does \(\d\.\d\d\)|"
     r"(?:Expected points|EP) per 90: \d\.\d\d", "$.repeatability.p90.r"),
    (r"[Ii]nvolvements per 90: \d\.\d\d", "$.repeatability.inv_p90.r"),
    (r"(?:decisive|EP per involvement|price of his goals)[^.;]{0,60}?r = \d\.\d\d", "$.repeatability.ep_per_inv.r"),
    (r"[Dd]ecisive a player's goals are: \d\.\d\d|value of a player's goals: \d\.\d\d|barely does \(\d\.\d\d\)|"
     r"season to season: \d\.\d\d|EP per involvement: \d\.\d\d", "$.repeatability.ep_per_inv.r"),
    (r"(?:SCA2|pre-assist)[^.;]{0,80}?r = \*{0,2}\d\.\d\d", "$.repeatability.sca2_share.r"),
    (r"that pass carries over at \d\.\d\d|SCA2 share: \d\.\d\d", "$.repeatability.sca2_share.r"),
    # SCA2 coverage and shares
    (r"[Mm]issing for \d+(?:\.\d)?%", "$.quality.sca2_missing_pct"),
    (r"SCA2 (?:is |for |on |recorded (?:for|on) )+\d+(?:\.\d)?%", "$.quality.sca2_pct"),
    (r"typical player: \d+%|median of \d+(?:\.\d)?%", "$.sca2.share_median_pct"),
    (r"best (?:keeper's adjusted rate is )?\d\.\d{3}", "$.board.gk_max_theta"),
    # Award check counts
    (r"goals \+ assists (?:leader|count)[^.;]{0,60}?\*{0,2}\d+\*{0,2} times", "$.awards.ga_exact"),
    (r"(?:EP model|model's pick|the model)\D{0,12}\d+(?=\.| of| times| winners)", "$.awards.exact"),
]

# A player's name next to his own number: adjusted EP per 90 (two decimals), SCA2 EP (one decimal),
# SCA2 share (whole or one-decimal percent)
for k, p in enumerate(DATA["board"]["top"][:10]):
    ANCHORS.append((rf"{re.escape(p['player'])}\D{{0,14}}\d\.\d\d(?!\d)", f"$.board.top[{k}].theta"))
for k, p in enumerate(DATA["sca2"]["top"][:10]):
    ANCHORS.append((rf"{re.escape(p['player'])}\D{{0,20}}\d+\.\d(?![\d%])", f"$.sca2.top[{k}].ep_sca2"))
for k, p in enumerate(DATA["sca2"]["top_share"][:5]):
    ANCHORS.append((rf"{re.escape(p['player'].split()[-1])}\D{{0,20}}\d+(?:\.\d)?%",
                    f"$.sca2.top_share[{k}].share_sca2_pct"))

if __name__ == "__main__":
    sys.exit(V.main(PROJECT_DIR, allow=ALLOW, anchors=ANCHORS, argv=sys.argv[1:]))
