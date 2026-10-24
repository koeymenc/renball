"""
build_pdfs.py — methodology + slides PDFs for this project
==========================================================

    methodology.md   -> methodology.html   (dark on screen, light when printed)
    methodology.html -> methodology.pdf    (headless Chrome)
    slides.pptx      -> slides.pdf         (your installed PowerPoint, via COM)

Thin wrapper around assets/build/renball_pdf.py — never reimplement here.

Run:
    python code/build_pdfs.py                      # everything
    python code/build_pdfs.py --only slides        # after refining slides.pptx by hand
    python code/build_pdfs.py --theme dark         # dark methodology.pdf variant
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR.parents[1] / "assets" / "build"))

import renball_pdf as P  # noqa: E402

if __name__ == "__main__":
    sys.exit(P.main([str(PROJECT_DIR), *sys.argv[1:]]))
