"""
build_dm_sans_static.py — static DM Sans TTFs from the official variable fonts
==============================================================================

Google Fonts ships DM Sans only as variable fonts (opsz + wght axes).
PowerPoint embeds static TTFs far more reliably than variable ones, and
matplotlib can only use a variable font's default instance — so we pin
static instances here.

    source  google/fonts  ofl/dmsans/DMSans[opsz,wght].ttf
                          ofl/dmsans/DMSans-Italic[opsz,wght].ttf
    opsz    14  (Google's static default; body sizes on slides are 12–15 pt)
    weights Regular 400 · Medium 500 · Bold 700, each roman + italic

Naming follows the RIBBI convention so Windows/PowerPoint see one family
"DM Sans" (Regular / Italic / Bold / Bold Italic) plus "DM Sans Medium",
both grouped under the typographic family "DM Sans". The OFL declares no
Reserved Font Name, so derivatives may keep the name.

Run (from repo root):
    python assets/fonts/build_dm_sans_static.py <DMSans[opsz,wght].ttf> <DMSans-Italic[opsz,wght].ttf> <out_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OPSZ = 14
STYLES = [  # (style name, weight, italic)
    ("Regular", 400, False), ("Italic", 400, True),
    ("Medium", 500, False), ("Medium Italic", 500, True),
    ("Bold", 700, False), ("Bold Italic", 700, True),
]


def _names(style: str) -> tuple[str, str]:
    """(legacy family nameID 1, legacy subfamily nameID 2) — RIBBI-safe."""
    if style in ("Regular", "Italic", "Bold", "Bold Italic"):
        return "DM Sans", style
    weight, _, it = style.partition(" ")
    return f"DM Sans {weight}", "Italic" if it else "Regular"


def build(src_roman: Path, src_italic: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for style, wght, italic in STYLES:
        vf = TTFont(src_italic if italic else src_roman)
        version = vf["name"].getDebugName(5) or "Version ?"
        font = instantiateVariableFont(vf, {"wght": wght, "opsz": OPSZ})
        fam, sub = _names(style)
        ps = "DMSans-" + style.replace(" ", "")
        name = font["name"]
        name.removeNames(platformID=1)                      # drop legacy Mac records
        for nid in (16, 17, 21, 22, 25):
            name.removeNames(nameID=nid)
        records = {
            1: fam, 2: sub,
            3: f"{version.replace('Version ', '')};renball;{ps}",
            4: f"DM Sans {style}", 5: f"{version}; static instance opsz={OPSZ} wght={wght}",
            6: ps,
        }
        if fam != "DM Sans":
            records.update({16: "DM Sans", 17: style})
        for nid, value in records.items():
            name.setName(value, nid, 3, 1, 0x409)
        os2 = font["OS/2"]
        os2.usWeightClass = wght
        bold = wght >= 700
        sel = os2.fsSelection & ~0b1100001          # clear ITALIC(0), BOLD(5), REGULAR(6)
        sel |= (1 if italic else 0) | (1 << 5 if bold else 0)
        if not italic and not bold:
            sel |= 1 << 6
        os2.fsSelection = sel
        font["head"].macStyle = (1 if bold else 0) | (2 if italic else 0)
        if "STAT" in font:
            del font["STAT"]
        path = out_dir / f"{ps}.ttf"
        font.save(path)
        written.append(path)
        print(f"[OK] {path.name}  ({path.stat().st_size // 1024} KB)")
    return written


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    build(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
