"""
renball_pdf.py — Shared PDF pipeline for every Renball project
==============================================================

No LibreOffice, no GTK. Two engines that already live on CK's machine:

    slides.pptx      -> slides.pdf         Microsoft PowerPoint via COM (pywin32)
    methodology.md   -> methodology.html   dark Renball theme on screen,
                                           clean light theme under @media print
    methodology.html -> methodology.pdf    headless Chrome --print-to-pdf

Plus two guards:
    check_fonts()   preflight — are Instrument Serif / DM Sans / JetBrains Mono
                    installed in the faces the deck needs? (PowerPoint renders
                    with *local* fonts; web pages load Google Fonts instead.)
    pdf_fonts()     post-export audit — which fonts did the PDF actually embed?

Typical use from a project's code/build_pdfs.py (a thin wrapper):

    import renball_pdf as P
    P.build_all(PROJECT_DIR)                    # methodology html + pdf, slides pdf

CLI (from repo root):

    python assets/build/renball_pdf.py projects/01-penalty-analysis
    python assets/build/renball_pdf.py projects/01-penalty-analysis --only slides
    python assets/build/renball_pdf.py projects/01-penalty-analysis --theme dark
    python assets/build/renball_pdf.py --check-fonts

Exit code is non-zero if any requested export fails.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

# ════════════════════════════════════════════════════════════════════════
# Fonts
# ════════════════════════════════════════════════════════════════════════
# Faces each brand family must provide for PowerPoint / matplotlib to render
# the design system faithfully. Web pages are unaffected (Google Fonts).
REQUIRED_FACES = {
    "Instrument Serif": {"Regular", "Italic"},
    "DM Sans":          {"Regular", "Italic"},
    "JetBrains Mono":   {"Regular"},
}

GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1'
    '&family=DM+Sans:ital,opsz,wght@0,9..40,300..700;1,9..40,300..700'
    '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)


def font_dirs(*, include_bundled: bool = False) -> list[Path]:
    """
    Directories holding *installed* fonts (Windows first, then macOS/Linux).
    PowerPoint only sees these; include_bundled adds the repo's assets/fonts/.
    """
    dirs = [REPO_ROOT / "assets" / "fonts"] if include_bundled else []
    if os.name == "nt":
        dirs += [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
                 Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    else:
        dirs += [Path.home() / "Library" / "Fonts", Path("/Library/Fonts"),
                 Path.home() / ".fonts", Path.home() / ".local/share/fonts",
                 Path("/usr/share/fonts")]
    return [d for d in dirs if d.exists()]


def _normalise_family(name: str) -> str:
    # Variable DM Sans registers as "DM Sans 9pt" / "DM Sans 14pt" (optical size)
    return re.sub(r"\s+\d+pt$", "", name.strip())


def scan_brand_fonts() -> dict[str, list[dict]]:
    """
    Return {family: [{"file", "style", "variable"}...]} for the three brand
    families, read from each font file's name table (not its filename).
    """
    from fontTools.ttLib import TTFont

    found: dict[str, list[dict]] = {f: [] for f in REQUIRED_FACES}
    seen: set[str] = set()
    for d in font_dirs():
        for path in d.rglob("*"):
            if path.suffix.lower() not in (".ttf", ".otf") or path.name in seen:
                continue
            low = path.name.lower()
            if not any(k in low for k in ("instrument", "dmsans", "dm-sans", "dm_sans", "jetbrains")):
                continue
            seen.add(path.name)
            try:
                tt = TTFont(path, lazy=True)
                nm = tt["name"]
                fam = nm.getDebugName(16) or nm.getDebugName(1) or ""
                sub = nm.getDebugName(17) or nm.getDebugName(2) or ""
                variable = "fvar" in tt
                tt.close()
            except Exception:
                continue
            fam = _normalise_family(fam)
            sub = re.sub(r"^\d+pt\s*", "", sub) or "Regular"   # "9pt Italic" -> "Italic"
            if fam.endswith(" Italic"):            # some files fold style into the family
                fam, sub = fam[: -len(" Italic")], "Italic"
            if fam in found:
                found[fam].append({"file": str(path), "style": sub, "variable": variable})
    return found


def check_fonts(verbose: bool = True) -> list[str]:
    """
    Preflight the brand fonts. Returns a list of problems (empty == all good).

    Variable fonts report their default instance's style ("Regular" or
    "Italic"), which is what PowerPoint embeds.
    """
    problems: list[str] = []
    found = scan_brand_fonts()
    for family, needed in REQUIRED_FACES.items():
        faces = found[family]
        styles = {f["style"] for f in faces}
        missing = sorted(needed - styles)
        if verbose:
            if faces:
                desc = ", ".join(sorted({f"{f['style']}{' (variable)' if f['variable'] else ''}" for f in faces}))
            else:
                desc = "not installed"
            status = "OK " if not missing else "!! "
            print(f"  [{status}] {family:<17} {desc}" + (f"  -- MISSING: {', '.join(missing)}" if missing else ""))
        if missing:
            problems.append(f"{family}: missing {', '.join(missing)}")
    return problems


def pdf_fonts(pdf_path: Path) -> list[str]:
    """
    Font names embedded in a PDF (subset prefixes like 'ABCDEF+' stripped).
    Uses a raw /BaseFont scan; good enough for PowerPoint and Chrome output.
    """
    raw = Path(pdf_path).read_bytes()
    names = set()
    for m in re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-_,#.]+)", raw):
        n = m.decode("latin-1").replace("#20", " ")
        names.add(n.split("+", 1)[-1])
    return sorted(names)


def pdf_font_usage(pdf_path: Path) -> dict[str, dict]:
    """Per embedded font: character count + a text sample (needs pypdfium2)."""
    import ctypes
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    usage: dict[str, dict] = {}
    buf = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    for page in pdfium.PdfDocument(str(pdf_path)):
        tp = page.get_textpage()
        for i in range(tp.count_chars()):
            ch = tp.get_text_range(i, 1)
            raw.FPDFText_GetFontInfo(tp.raw, i, buf, 256, ctypes.byref(flags))
            font = buf.value.decode("latin-1").split("+", 1)[-1]
            u = usage.setdefault(font, {"chars": 0, "sample": ""})
            u["chars"] += 1
            if ch.strip() and len(u["sample"]) < 40:
                u["sample"] += ch
    return usage


def audit_pdf_fonts(pdf_path: Path, expect: Iterable[str] = ("InstrumentSerif-Regular", "DMSans")) -> list[str]:
    """
    Report which fonts a PDF draws each run with; warn when an expected
    family isn't embedded (PowerPoint substituted it).

    Known PowerPoint quirk (verified 2026-10-23 by rendering at 10x): the
    variable JetBrains Mono is drawn with the correct glyphs but filed in the
    PDF under the name and metrics of "Calibri". Mono labels therefore show
    up as "Calibri" here; a genuinely missing JetBrains Mono is caught by
    check_fonts() before export instead.
    """
    try:
        usage = pdf_font_usage(pdf_path)
    except ImportError:
        usage = {f: {"chars": 0, "sample": ""} for f in pdf_fonts(pdf_path)}
    names = [f.replace(" ", "").lower() for f in usage]
    warnings = [f"{x} not embedded" for x in expect
                if not any(x.replace(" ", "").lower() in n for n in names)]
    for f, u in sorted(usage.items(), key=lambda kv: -kv[1]["chars"]):
        note = ("  (JetBrains Mono glyphs under PowerPoint's 'Calibri' label)"
                if f.startswith("Calibri") and not any("jetbrains" in n for n in names) else "")
        print(f"       {f:<26} {u['chars']:>5} chars  {u['sample'][:28]!r}{note}")
    for w in warnings:
        print(f"  [WARN] {w} -- PowerPoint substituted a fallback; run check_fonts()")
    return warnings


# ════════════════════════════════════════════════════════════════════════
# slides.pptx -> slides.pdf   (PowerPoint COM)
# ════════════════════════════════════════════════════════════════════════
PP_SAVE_AS_PDF = 32


class ExportError(RuntimeError):
    pass


def _powerpoint():
    """Return (app, started_by_us). Raises ExportError with a fix-it hint."""
    try:
        import pythoncom
        import win32com.client
    except ImportError as e:
        raise ExportError("pywin32 not installed in this venv -> "
                          ".venv/Scripts/python.exe -m pip install pywin32") from e
    pythoncom.CoInitialize()
    try:
        win32com.client.GetActiveObject("PowerPoint.Application")
        started = False
    except Exception:
        started = True
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
    except Exception as e:
        raise ExportError(f"PowerPoint not reachable via COM ({e}). Is Microsoft "
                          f"PowerPoint installed and licensed for this user?") from e
    return app, started


def pptx_to_pdf(pptx_path: Path, pdf_path: Optional[Path] = None, *,
                audit: bool = True) -> Path:
    """
    Export a .pptx to PDF with the user's installed PowerPoint.
    Opens read-only and windowless, so an open copy in PowerPoint is fine.
    If PowerPoint wasn't already running, it's closed again afterwards.
    """
    pptx_path = Path(pptx_path).resolve()
    pdf_path = Path(pdf_path).resolve() if pdf_path else pptx_path.with_suffix(".pdf")
    if not pptx_path.exists():
        raise ExportError(f"{pptx_path.name} not found -- run code/build_slides.py first")

    app, started = _powerpoint()
    t0 = time.time()
    pres = None
    try:
        # Open(FileName, ReadOnly, Untitled, WithWindow)
        pres = app.Presentations.Open(str(pptx_path), True, False, False)
        try:
            pres.SaveAs(str(pdf_path), PP_SAVE_AS_PDF)
        except Exception as e:
            raise ExportError(f"PowerPoint could not write {pdf_path.name} -- is it "
                              f"open in a PDF viewer? ({e})") from e
    finally:
        if pres is not None:
            pres.Close()
        if started:
            try:
                if app.Presentations.Count == 0:
                    app.Quit()
            except Exception:
                pass

    print(f"[OK] {pdf_path.name}  ({pdf_path.stat().st_size / 1024:.0f} KB, "
          f"{time.time() - t0:.0f}s via PowerPoint)")
    if audit:
        audit_pdf_fonts(pdf_path)
    return pdf_path


def pptx_to_pngs(pptx_path: Path, out_dir: Path, *, slides: Optional[Iterable[int]] = None,
                 width: int = 1600, height: int = 900) -> list[Path]:
    """Render slides to PNG via PowerPoint (QA previews; 1-based slide numbers)."""
    pptx_path = Path(pptx_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    app, started = _powerpoint()
    written: list[Path] = []
    pres = None
    try:
        pres = app.Presentations.Open(str(pptx_path), True, False, False)
        idx = list(slides) if slides else list(range(1, pres.Slides.Count + 1))
        for i in idx:
            p = out_dir / f"slide_{i:02d}.png"
            pres.Slides(i).Export(str(p), "PNG", width, height)
            written.append(p)
    finally:
        if pres is not None:
            pres.Close()
        if started:
            try:
                if app.Presentations.Count == 0:
                    app.Quit()
            except Exception:
                pass
    return written


# ════════════════════════════════════════════════════════════════════════
# HTML -> PDF   (headless Chrome, Edge as fallback)
# ════════════════════════════════════════════════════════════════════════
BROWSER_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> Optional[str]:
    for p in BROWSER_PATHS:
        if Path(p).exists():
            return p
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def headless_chrome(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    """
    Run headless Chrome with a throwaway profile, so it never hands off to
    (or locks) the user's running browser session.
    """
    browser = find_browser()
    if not browser:
        raise ExportError("Chrome/Edge not found -- install Google Chrome")
    with tempfile.TemporaryDirectory(prefix="renball_chrome_") as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--disable-extensions",
               f"--user-data-dir={profile}", *args]
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)


def html_to_pdf(html_path: Path, pdf_path: Optional[Path] = None, *,
                budget_ms: int = 15000) -> Path:
    """
    Print an HTML file to PDF with headless Chrome. Page size, margins and
    page-number footers come from the page's own @page CSS. `budget_ms` gives
    web fonts time to load before printing.
    """
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve() if pdf_path else html_path.with_suffix(".pdf")
    if pdf_path.exists():
        pdf_path.unlink()
    t0 = time.time()
    res = headless_chrome([
        "--no-pdf-header-footer",
        f"--virtual-time-budget={budget_ms}",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ])
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise ExportError(f"Chrome did not write {pdf_path.name} (exit {res.returncode}): "
                          f"{(res.stderr or res.stdout)[-400:]}")
    print(f"[OK] {pdf_path.name}  ({pdf_path.stat().st_size / 1024:.0f} KB, "
          f"{time.time() - t0:.0f}s via headless Chrome)")
    return pdf_path


# ════════════════════════════════════════════════════════════════════════
# methodology.md -> methodology.html
# ════════════════════════════════════════════════════════════════════════
# Screen: the existing dark Renball theme (unchanged look), now with a
# readable measure and the brand fonts loaded from Google Fonts.
# Print / PDF: a clean light document. Same three typefaces; the palette is
# inverted (--bg becomes ink, --text becomes the code/table surface) and the
# lime accent is used only where it reads on paper: the dark masthead band,
# highlighter fills and rules (--accent-dim). Paper itself is white.
METHODOLOGY_CSS = """
* { box-sizing: border-box; }

body {
  background: #080c08;
  color: #e8efe8;
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
  font-size: 10.5pt;
  line-height: 1.65;
}
@media screen {
  body { max-width: 860px; margin: 0 auto; padding: 3rem 1.75rem 5rem; font-size: 11pt; }
}

h1, h2, h3, h4, h5 {
  font-family: 'Instrument Serif', Georgia, serif;
  color: #e8efe8;
  letter-spacing: -0.01em;
  margin-top: 1.6em;
  margin-bottom: 0.5em;
  font-weight: normal;
  font-synthesis: none;
  line-height: 1.2;
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
blockquote p { color: inherit; }
/* Instrument Serif has one weight: emphasis inside a serif quote is colour, never faux bold */
blockquote { font-synthesis: none; }
blockquote strong, blockquote b { font-weight: 400; color: #e8efe8; }

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

.footnote { font-size: 0.88em; color: #8fa68f; }
.footnote hr { margin: 2.5em 0 1em; }

/* Renball "ren·ball" mark at top of doc */
.renball-mark {
  font-family: 'Instrument Serif', Georgia, serif;
  font-size: 16pt;
  margin-bottom: 1.5em;
  letter-spacing: -0.01em;
}
.renball-mark .ball { color: #c1ff72; }
.renball-mark .sep { color: #5a735a; font-family: 'JetBrains Mono', monospace; font-size: 9pt; margin-left: 0.6em; letter-spacing: 0.16em; }

.back-link {
  display: inline-block; margin-bottom: 2rem;
  font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.1em;
  text-transform: uppercase; color: #5a735a;
}
.back-link:hover { color: #c1ff72; }

/* ── Print / PDF ─────────────────────────────────────────────────────── */
@page {
  size: A4;
  margin: 20mm 19mm 22mm;
  @bottom-left {
    content: "renball.com  \\00B7  Project __NUM__  \\00B7  Methodology";
    font-family: 'JetBrains Mono', monospace; font-size: 7pt; letter-spacing: 0.12em;
    text-transform: uppercase; color: #5a735a;
  }
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: 'JetBrains Mono', monospace; font-size: 7pt; color: #5a735a;
  }
}

@media print {
  .back-link { display: none; }
  h1, h2, h3, h4 { break-after: avoid; }
  table, pre, blockquote, figure { break-inside: avoid; }
  tr { break-inside: avoid; }
  p, li { orphans: 3; widows: 3; }

  /* Masthead stays dark in both themes — the one place lime reads on paper */
  .renball-mark {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
    background: #080c08; color: #e8efe8;
    padding: 14px 18px; margin: 0 0 1.6em;
  }
  .renball-mark .sep { color: #8fa68f; }
}

/* Light document (default PDF theme) */
@media print {
  html:not([data-print-theme="dark"]) body {
    background: #fff; color: #080c08; font-size: 9.8pt; line-height: 1.6;
  }
  html:not([data-print-theme="dark"]) h1,
  html:not([data-print-theme="dark"]) h2,
  html:not([data-print-theme="dark"]) h3,
  html:not([data-print-theme="dark"]) h4 { color: #080c08; }
  html:not([data-print-theme="dark"]) h1 { font-size: 24pt; }
  html:not([data-print-theme="dark"]) h2 { font-size: 16pt; border-bottom: 1.5px solid #8fbf45; }
  html:not([data-print-theme="dark"]) h3 { font-size: 12.5pt; }
  html:not([data-print-theme="dark"]) p,
  html:not([data-print-theme="dark"]) ul,
  html:not([data-print-theme="dark"]) ol { color: #1a261a; }
  html:not([data-print-theme="dark"]) strong { color: #080c08; }
  html:not([data-print-theme="dark"]) em { color: inherit; }
  html:not([data-print-theme="dark"]) a {
    color: #080c08; text-decoration: underline; text-decoration-color: #8fbf45;
  }
  html:not([data-print-theme="dark"]) code {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
    color: #1a261a; background: #e8efe8;
  }
  html:not([data-print-theme="dark"]) pre code { border-left: 2px solid #8fbf45; }
  html:not([data-print-theme="dark"]) blockquote {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
    background: rgba(193, 255, 114, 0.28); border-left: 3px solid #8fbf45; color: #080c08;
  }
  html:not([data-print-theme="dark"]) blockquote strong {
    text-decoration: underline; text-decoration-color: #8fbf45; text-underline-offset: 2px;
  }
  html:not([data-print-theme="dark"]) hr { border-top-color: #8fa68f; }
  html:not([data-print-theme="dark"]) table th,
  html:not([data-print-theme="dark"]) table td { border-bottom: 0.75px solid #8fa68f; }
  html:not([data-print-theme="dark"]) table th { color: #5a735a; border-bottom: 1px solid #5a735a; }
  html:not([data-print-theme="dark"]) table td { color: #1a261a; }
  html:not([data-print-theme="dark"]) table td:first-child { color: #080c08; }
  html:not([data-print-theme="dark"]) .footnote { color: #5a735a; }
}

/* Dark document (--theme dark): keep the screen palette on paper */
@media print {
  html[data-print-theme="dark"] {
    -webkit-print-color-adjust: exact; print-color-adjust: exact; background: #080c08;
  }
  html[data-print-theme="dark"] body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

DARK_PAGE_CSS = "@page { background: #080c08; }"


KATEX = (
    '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"\n'
    '  onload="renderMathInElement(document.body, {delimiters: ['
    "{left: '$$', right: '$$', display: true}, {left: '\\\\(', right: '\\\\)', display: false}"
    '], throwOnError: false})"></script>'
)

_MATH_RE = re.compile(r"\$\$.+?\$\$|\\\(.+?\\\)", flags=re.S)
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")


def _md_title(md_text: str) -> Optional[str]:
    m = re.search(r"^#\s+(.+)$", md_text, flags=re.M)
    return re.sub(r"[*_`]", "", m.group(1)).strip() if m else None


def _normalise_md(md_text: str) -> str:
    """
    Python-Markdown needs a blank line before a list; GitHub doesn't. Insert
    one where a list starts straight after a paragraph line (outside code
    fences) so methodology.md renders the way it reads on GitHub.
    """
    out: list[str] = []
    in_fence = False
    for line in md_text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif (not in_fence and _LIST_ITEM_RE.match(line) and out and out[-1].strip()
              and not _LIST_ITEM_RE.match(out[-1]) and not out[-1].startswith(("    ", "\t", "|", "#", ">"))):
            out.append("")
        out.append(line)
    return "\n".join(out)


def _render_markdown(md_text: str) -> tuple[str, bool]:
    """Markdown -> HTML with $$...$$ and \\(...\\) math shielded for KaTeX."""
    import html as _html
    import markdown

    stash: list[str] = []

    def _protect(m: re.Match) -> str:
        stash.append(_html.escape(m.group(0), quote=False))
        return f"RENBALLMATH{len(stash) - 1}X"

    shielded = _MATH_RE.sub(_protect, _normalise_md(md_text))
    body = markdown.markdown(shielded, extensions=["tables", "extra", "sane_lists"])
    for i, tex in enumerate(stash):
        body = body.replace(f"RENBALLMATH{i}X", tex)
    return body, bool(stash)


def build_methodology_html(md_text: str, *, project_num: str,
                           print_theme: str = "light") -> str:
    body_html, has_math = _render_markdown(md_text)
    title = _md_title(md_text)
    page_title = f"Methodology — {title} — Renball" if title else f"Methodology — Renball Project {project_num}"
    theme_attr = ' data-print-theme="dark"' if print_theme == "dark" else ""
    css = METHODOLOGY_CSS.replace("__NUM__", project_num)
    if print_theme == "dark":
        css += DARK_PAGE_CSS
    return f"""<!DOCTYPE html>
<html lang="en"{theme_attr}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
{GOOGLE_FONTS_LINK}
{KATEX if has_math else ""}
<style>{css}</style>
</head>
<body>
<a class="back-link" href="analysis.html">&larr; Back to the analysis</a>
<div class="renball-mark"><span>ren</span><span class="ball">ball</span><span class="sep">METHODOLOGY · PROJECT {project_num}</span></div>
{body_html}
</body>
</html>
"""


# ════════════════════════════════════════════════════════════════════════
# Project-level entry points
# ════════════════════════════════════════════════════════════════════════
def project_num(project_dir: Path) -> str:
    m = re.match(r"^(\d+)", Path(project_dir).name)
    return m.group(1) if m else "??"


def build_methodology(project_dir: Path, *, pdf: bool = True,
                      print_theme: str = "light") -> None:
    """methodology.md -> methodology.html (always) -> methodology.pdf."""
    project_dir = Path(project_dir).resolve()
    md = project_dir / "methodology.md"
    html = project_dir / "methodology.html"
    if not md.exists():
        raise ExportError(f"{md} not found")
    num = project_num(project_dir)
    # The deployed HTML always carries the default (light) print theme, so a
    # reader's Ctrl+P matches the shipped PDF.
    html.write_text(build_methodology_html(md.read_text(encoding="utf-8"), project_num=num),
                    encoding="utf-8")
    print(f"[OK] {html.name}  ({html.stat().st_size / 1024:.0f} KB)")
    if not pdf:
        return
    if print_theme == "light":
        html_to_pdf(html, project_dir / "methodology.pdf")
    else:
        # Print a dark variant from a sibling temp file (same folder, same relative links)
        tmp = project_dir / "_methodology_print.html"
        tmp.write_text(build_methodology_html(md.read_text(encoding="utf-8"), project_num=num,
                                              print_theme=print_theme), encoding="utf-8")
        try:
            html_to_pdf(tmp, project_dir / "methodology.pdf")
        finally:
            tmp.unlink(missing_ok=True)


def build_slides_pdf(project_dir: Path) -> None:
    project_dir = Path(project_dir).resolve()
    pptx_to_pdf(project_dir / "slides.pptx", project_dir / "slides.pdf")


def build_all(project_dir: Path, *, only: Optional[str] = None,
              print_theme: str = "light") -> int:
    """Run the requested exports; returns the number of failures."""
    failures = 0
    print(f"== Renball PDF build: {Path(project_dir).name} ==")
    if only in (None, "methodology"):
        try:
            build_methodology(project_dir, print_theme=print_theme)
        except ExportError as e:
            failures += 1
            print(f"[FAIL] methodology: {e}")
    if only in (None, "slides"):
        problems = check_fonts(verbose=False)
        for p in problems:
            print(f"  [WARN] font preflight: {p} -- slides.pdf will use a fallback face")
        try:
            build_slides_pdf(project_dir)
        except ExportError as e:
            failures += 1
            print(f"[FAIL] slides: {e}")
    return failures


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Renball PDF pipeline")
    ap.add_argument("project", nargs="?", help="project folder, e.g. projects/01-penalty-analysis")
    ap.add_argument("--only", choices=["slides", "methodology"])
    ap.add_argument("--theme", choices=["light", "dark"], default="light",
                    help="methodology.pdf print theme (default: light)")
    ap.add_argument("--check-fonts", action="store_true")
    a = ap.parse_args(argv)
    if a.check_fonts or not a.project:
        print("== Brand font preflight ==")
        problems = check_fonts()
        print("All brand faces installed." if not problems else
              f"{len(problems)} problem(s) -- PowerPoint and matplotlib will substitute.")
        if not a.project:
            return 1 if problems else 0
    return 1 if build_all(Path(a.project), only=a.only, print_theme=a.theme) else 0


if __name__ == "__main__":
    sys.exit(main())
