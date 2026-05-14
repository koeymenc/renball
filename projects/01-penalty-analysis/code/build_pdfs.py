"""
build_pdfs.py — Build methodology.html (canonical) plus opportunistic PDFs

What it always does:
- methodology.md  ->  methodology.html
    Single styled HTML doc in the Renball dark theme. This is the canonical
    deploy artifact — readers open it directly in a browser. The dashboard's
    download row links here.

What it does opportunistically (only if the system dep is installed):
- methodology.html  ->  methodology.pdf   (via WeasyPrint, needs GTK runtime)
- slides.pptx       ->  slides.pdf        (via LibreOffice `soffice` headless)

If either binary is missing, the script prints clear manual-export instructions
and exits 0. slides.pdf is typically a manual export from PowerPoint anyway.

Run:
    python code/build_pdfs.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import markdown

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

SLIDES_PPTX = PROJECT_DIR / "slides.pptx"
SLIDES_PDF  = PROJECT_DIR / "slides.pdf"
METH_MD     = PROJECT_DIR / "methodology.md"
METH_HTML   = PROJECT_DIR / "methodology.html"
METH_PDF    = PROJECT_DIR / "methodology.pdf"

LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


# ── Renball PDF stylesheet (dark theme) ────────────────────
METHODOLOGY_CSS = """
@page { size: A4; margin: 2.2cm 2.5cm; background: #080c08; }

* { box-sizing: border-box; }

body {
  background: #080c08;
  color: #e8efe8;
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
  font-size: 10.5pt;
  line-height: 1.65;
}

h1, h2, h3, h4, h5 {
  font-family: 'Instrument Serif', Georgia, serif;
  color: #e8efe8;
  letter-spacing: -0.01em;
  margin-top: 1.6em;
  margin-bottom: 0.5em;
  font-weight: normal;
}
h1 { font-size: 26pt; margin-top: 0; }
h2 { font-size: 18pt; border-bottom: 1px solid #1e2e1e; padding-bottom: 0.25em; }
h3 { font-size: 14pt; color: #c1ff72; }

p { margin: 0.6em 0; color: #cfd8cf; }

strong { color: #e8efe8; font-weight: 600; }
em { color: #c1ff72; font-style: italic; }

a { color: #c1ff72; text-decoration: none; }

code {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.88em;
  color: #c1ff72;
  background: #111a11;
  padding: 0.1em 0.35em;
  border-radius: 2px;
}

pre code {
  display: block;
  padding: 0.8em 1em;
  background: #111a11;
  border-left: 2px solid #c1ff72;
  white-space: pre-wrap;
}

blockquote {
  border-left: 3px solid #c1ff72;
  padding: 0.4em 1.2em;
  margin: 1.2em 0;
  background: rgba(193, 255, 114, 0.06);
  color: #c1ff72;
  font-family: 'Instrument Serif', Georgia, serif;
  font-size: 1.05em;
  font-style: italic;
}

hr {
  border: none;
  border-top: 1px solid #1e2e1e;
  margin: 2em 0;
}

ul, ol { padding-left: 1.4em; color: #cfd8cf; }
ul li, ol li { margin: 0.25em 0; }

table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 0.92em;
}
table th, table td {
  padding: 0.55em 0.8em;
  border-bottom: 1px solid #1e2e1e;
  text-align: left;
}
table th {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8fa68f;
  border-bottom: 1px solid #2d3d2d;
  font-weight: normal;
}
table td:first-child { color: #e8efe8; }

/* Renball "ren·ball" header bar at top of doc */
.renball-mark {
  font-family: 'Instrument Serif', Georgia, serif;
  font-size: 16pt;
  margin-bottom: 1.5em;
  letter-spacing: -0.01em;
}
.renball-mark .ball { color: #c1ff72; }
.renball-mark .sep { color: #5a735a; font-family: 'JetBrains Mono', monospace; font-size: 9pt; margin-left: 0.6em; letter-spacing: 0.16em; }
"""


def build_methodology_html(md_text: str) -> str:
    body_html = markdown.markdown(md_text, extensions=["tables", "extra"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Methodology — Renball Project 01</title>
<style>{METHODOLOGY_CSS}</style>
</head>
<body>
<div class="renball-mark"><span>ren</span><span class="ball">ball</span><span class="sep">METHODOLOGY · PROJECT 01</span></div>
{body_html}
</body>
</html>
"""


def find_libreoffice() -> str | None:
    found = shutil.which("soffice")
    if found:
        return found
    for path in LIBREOFFICE_PATHS:
        if Path(path).exists():
            return path
    return None


def convert_slides() -> None:
    if not SLIDES_PPTX.exists():
        print(f"[SKIP] {SLIDES_PPTX.name} not found — run code/build_slides.py first")
        return

    soffice = find_libreoffice()
    if not soffice:
        print("[SKIP] slides.pdf — LibreOffice (soffice) not on this machine.")
        print("       Manual export:")
        print(f"         1. Open {SLIDES_PPTX.relative_to(PROJECT_DIR)} in PowerPoint")
        print( "         2. File -> Export -> Create PDF/XPS")
        print(f"         3. Save next to .pptx as: {SLIDES_PDF.relative_to(PROJECT_DIR)}")
        return

    print(f"[..] Converting {SLIDES_PPTX.name} via LibreOffice ...")
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf",
         "--outdir", str(PROJECT_DIR), str(SLIDES_PPTX)],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and SLIDES_PDF.exists():
        size_kb = SLIDES_PDF.stat().st_size / 1024
        print(f"[OK] Wrote {SLIDES_PDF.relative_to(PROJECT_DIR)} ({size_kb:.1f} KB)")
    else:
        print(f"[FAIL] LibreOffice conversion failed (exit {result.returncode})")
        print(result.stderr or result.stdout)


def convert_methodology() -> None:
    if not METH_MD.exists():
        print(f"[SKIP] {METH_MD.name} not found")
        return

    md_text = METH_MD.read_text(encoding="utf-8")
    html_text = build_methodology_html(md_text)

    # Always write the HTML — it's useful for manual print-to-PDF and for review
    METH_HTML.write_text(html_text, encoding="utf-8")
    html_kb = METH_HTML.stat().st_size / 1024
    print(f"[OK] Wrote {METH_HTML.relative_to(PROJECT_DIR)} ({html_kb:.1f} KB)")

    # Try WeasyPrint
    try:
        from weasyprint import HTML
        try:
            HTML(string=html_text, base_url=str(PROJECT_DIR)).write_pdf(str(METH_PDF))
        except OSError as e:
            raise RuntimeError(f"WeasyPrint render failed: {e}")
    except Exception as e:
        print(f"[SKIP] methodology.pdf — WeasyPrint couldn't run on this machine.")
        print(f"       Reason: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
        print( "       Manual export:")
        print(f"         1. Open {METH_HTML.relative_to(PROJECT_DIR)} in a browser")
        print( "         2. Ctrl+P (or Cmd+P) -> Destination: Save as PDF")
        print(f"         3. Save next to .md as: {METH_PDF.relative_to(PROJECT_DIR)}")
        print( "       (Or install GTK runtime per WeasyPrint docs to enable native PDF output.)")
        return

    if METH_PDF.exists():
        size_kb = METH_PDF.stat().st_size / 1024
        print(f"[OK] Wrote {METH_PDF.relative_to(PROJECT_DIR)} ({size_kb:.1f} KB)")


def main() -> None:
    print("== Renball PDF build ==")
    convert_methodology()
    convert_slides()


if __name__ == "__main__":
    main()
