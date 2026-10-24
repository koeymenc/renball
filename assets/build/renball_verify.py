"""
renball_verify.py — every figure traces to data.json
====================================================

Two checks, one command. Both run per project via a thin code/verify.py.

1. NUMBERS (fails on any mismatch)
   Every number printed in the project's copy must equal a numeric value in
   data/data.json at the precision shown — or that value x100 when a
   proportion is shown as a percent — or be covered by an explicit allow-rule
   that carries a reason. Copy sources:

     analysis.html   DOM text *after* JS runs (headless Chrome), so numbers
                     formatted in JS are checked too
     dashboard.html  static help text (its tables come from dashboard JSON)
     methodology.md  prose + tables (code spans and blocks skipped)
     slides.pptx     every text frame, table cell and group
     social/         thread, posts, alt hooks, captions, alt text, guide
     data.json       sentence-like strings (takeaways, findings)
     config.json     title / excerpt / finding

   Derived figures (ratios, totals, differences) must be written into
   data.json by build.py — the page may not compute a number the verifier
   can't trace. Bare integers below 13 and years are ignored (counts of
   leagues, seasons, slides); decimals, percentages and pp never are.

2. STANDARD (errors fail, warnings print)
   Deliverables present, fresh (PDF newer than its source), consistent
   (config.json == projects.json entry, has_dashboard matches reality),
   takeaways well-formed, X package valid.

Per-project wrapper (code/verify.py):

    import renball_verify as V
    ALLOW = [
        (r"\\b85th minute", "illustrative minute in the hook, not a data claim"),
    ]
    sys.exit(V.main(PROJECT_DIR, allow=ALLOW))

CLI:
    python code/verify.py              # both checks
    python code/verify.py --report     # also list every matched number + path
    python code/verify.py --static     # skip headless render (raw HTML text)
"""

from __future__ import annotations

import argparse
import bisect
import functools
import html.parser
import json
import math
import re
import sys
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "assets" / "social"))

MIN_BARE_INT = 13

# Spans blanked before tokenising: never data claims
_BLANK = [re.compile(p) for p in (
    r"\b(?:19|20)\d{2}\s*[-–/]\s*(?:19|20)?\d{2}\b",           # seasons 2017-2018, 2023-24
    r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?",                    # ISO dates / timestamps
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b",                             # clock times
    r"https?://\S+",
    r"\b[\w.-]+\.(?:com|org|net|io|html|json|md|py|mjs|js|css|pdf|png|pptx|csv|pkl|txt)\b(?:/\S*)?",
    r"(?:\.\./|\./)?(?:projects|assets|code|data|social|images)/\S+",   # repo paths
    r"#[0-9a-fA-F]{3,8}\b",                                      # hex colours
    r"\[\^?\d+\]",                                               # footnote refs
    r"\bv?\d+\.\d+\.\d+\b",                                      # versions
)]

_NUM = re.compile(
    r"(?<![\w.,])(?P<sign>[-+−–])?"
    r"(?:(?P<int>\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?P<frac>\.\d+)?|(?P<bare>\.\d+))"
    r"(?P<suf>\s?%|\s?pp\b|\s?p\.p\.|×|x(?!\w)|k(?!\w))?(?!\w)")

DEFAULT_ALLOW: list[tuple[str, str]] = [
    (r"\b(?:80|90|95|99)\s?%\s*(?:CIs?\b|C\.I\.|confidence|credible|Wilson|Newcombe|bootstrap|HDI|HPD|"
     r"prediction|uncertainty|intervals?)", "interval level"),
    (r"(?:CI|confidence|credible|interval)s?\s*(?:level\s*)?(?:of\s*|at\s*)?\(?(?:80|90|95|99)\s?%",
     "interval level"),
    (r"(?:α|alpha)\s*(?:=|of)?\s*0?\.\d+", "significance level"),
    (r"\bp\s*[<≤>≥]\s*0?\.\d+", "p-value threshold"),
    (r"\b(?:80|90)\s?%\s*power|\bpower\s*(?:of\s*)?(?:80|90)\s?%", "power target"),
    (r"\b[Pp]roject\s*\d+\b|RESEARCH\s*·\s*\d+", "project number"),
    (r"(?m)^\s*\d{1,3}\s*/\s*\d{1,3}\s*$", "page / post counter"),
    (r"\b(?:1600|1080)\s*[x×]\s*(?:900|1350)\b", "image size"),
    (r"\bPython\s*\d+(?:\.\d+)*", "software version"),
    (r"\b\d+\s*/\s*280\b|\b280\s*(?:characters|chars)\b", "X character limit"),
    (r"\b90\s*(?:minutes|mins?)\b|\b90\+", "match length"),
    (r"\b(?:top|Top|TOP)[ -]?5\b", "league scope"),
]


# ════════════════════════════════════════════════════════════════════════
# Truth set
# ════════════════════════════════════════════════════════════════════════
class Truth:
    """Numeric leaves of data.json, searchable at any display precision."""

    def __init__(self, data):
        self.paths: list[str] = []
        vals: list[tuple[float, int]] = []
        for path, v in self._leaves(data, "$"):
            i = len(self.paths)
            self.paths.append(path)
            vals.append((abs(v), i))
            vals.append((abs(v) * 100, i))       # proportion shown as a percent
            vals.append((abs(v) / 100, i))       # percent shown as a proportion
        vals.sort()
        self._v = [v for v, _ in vals]
        self._i = [i for _, i in vals]

    @staticmethod
    def _leaves(node, path):
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            if math.isfinite(node):
                yield path, float(node)
        elif isinstance(node, dict):
            for k, v in node.items():
                yield from Truth._leaves(v, f"{path}.{k}")
        elif isinstance(node, list):
            for k, v in enumerate(node):
                yield from Truth._leaves(v, f"{path}[{k}]")

    def __len__(self) -> int:
        return len(self.paths)

    def find(self, x: float, tol: float) -> Optional[str]:
        lo = bisect.bisect_left(self._v, x - tol)
        if lo < len(self._v) and self._v[lo] <= x + tol:
            return self.paths[self._i[lo]]
        return None

    def nearest(self, x: float) -> tuple[float, str]:
        i = bisect.bisect_left(self._v, x)
        cands = [j for j in (i - 1, i) if 0 <= j < len(self._v)]
        j = min(cands, key=lambda k: abs(self._v[k] - x))
        return self._v[j], self.paths[self._i[j]]


# ════════════════════════════════════════════════════════════════════════
# Copy extraction
# ════════════════════════════════════════════════════════════════════════
class _TextParser(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "code"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth_skip = 0
        self.stack: list[tuple[str, bool]] = []
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        skip = tag in self.SKIP or dict(attrs).get("data-verify") == "skip"
        if tag in ("br", "img", "meta", "link", "input", "hr", "wbr", "source"):
            return
        self.stack.append((tag, skip))
        self.depth_skip += skip

    def handle_endtag(self, tag):
        while self.stack:
            t, skip = self.stack.pop()
            self.depth_skip -= skip
            if t == tag:
                break

    def handle_data(self, data):
        if not self.depth_skip and data.strip():
            self.chunks.append(" ".join(data.split()))


def html_text(markup: str) -> list[str]:
    p = _TextParser()
    p.feed(markup)
    return p.chunks


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@functools.lru_cache(maxsize=1)
def _server() -> str:
    handler = functools.partial(_QuietHandler, directory=str(REPO_ROOT))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def rendered_html(page: Path) -> str:
    """
    DOM after JS (fetch(data.json), templating) via headless Chrome. The
    browser locale is pinned to en-GB (the site's number format); pages must
    pin it too — renball_qa.mjs catches pages that don't.
    """
    import renball_pdf
    url = f"{_server()}/{page.resolve().relative_to(REPO_ROOT).as_posix()}"
    res = renball_pdf.headless_chrome(["--lang=en-GB", "--accept-lang=en-GB",
                                       "--virtual-time-budget=12000", "--dump-dom", url], timeout=90)
    if "<body" not in res.stdout:
        raise RuntimeError(f"headless render of {page.name} failed: {res.stderr[-300:]}")
    return res.stdout


_MD_STRIP = [
    (re.compile(r"```.*?```", re.S), " "),
    (re.compile(r"`[^`\n]+`"), " "),
    (re.compile(r"<!--.*?-->", re.S), " "),
    (re.compile(r"\]\([^)]*\)"), "]"),
    (re.compile(r"(?m)^\s*(?:[-*+]\s+)?\d+[.)]\s+"), ""),           # list numbering
    (re.compile(r"(?m)^#+\s*(?:§\s*)?\d+(?:\.\d+)*\.?\s"), ""),       # numbered headings
]


def md_text(raw: str) -> str:
    for rx, rep in _MD_STRIP:
        raw = rx.sub(rep, raw)
    return raw


def pptx_text(path: Path) -> list[tuple[str, str]]:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    def walk(shapes):
        for sh in shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                yield from walk(sh.shapes)
            elif getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        yield cell.text
            elif getattr(sh, "has_text_frame", False) and sh.has_text_frame:
                yield sh.text_frame.text

    out = []
    for n, slide in enumerate(Presentation(str(path)).slides, start=1):
        for t in walk(slide.shapes):
            if t.strip():
                out.append((f"slide {n}", t))
    return out


def _sentences(node, path="$") -> Iterable[tuple[str, str]]:
    if isinstance(node, str):
        if len(node.split()) >= 6:
            yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _sentences(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _sentences(v, f"{path}[{i}]")


def collect_copy(project_dir: Path, data: dict, *, render: bool = True) -> list[tuple[str, str, str]]:
    """(source, location, text) for every piece of copy in the project."""
    pd = project_dir
    out: list[tuple[str, str, str]] = []

    page = pd / "analysis.html"
    if page.exists():
        markup = rendered_html(page) if render else page.read_text(encoding="utf-8")
        out += [("analysis.html", "rendered" if render else "static", t) for t in html_text(markup)]
    dash = pd / "dashboard.html"
    if dash.exists():
        out += [("dashboard.html", "static", t) for t in html_text(dash.read_text(encoding="utf-8"))]
    meth = pd / "methodology.md"
    if meth.exists():
        for i, line in enumerate(md_text(meth.read_text(encoding="utf-8")).splitlines(), start=1):
            if line.strip():
                out.append(("methodology.md", f"line {i}", line))
    slides = pd / "slides.pptx"
    if slides.exists():
        out += [("slides.pptx", loc, t) for loc, t in pptx_text(slides)]
    if (pd / "social").exists():
        import renball_social
        pkg = renball_social.Package.load(pd)
        out += [("social", loc, t) for loc, t in pkg.all_text()]
        guide = pd / "social" / "posting_guide.md"
        if guide.exists():
            out += [("social", "posting_guide.md", md_text(guide.read_text(encoding="utf-8")))]
    out += [("data.json", path, t) for path, t in _sentences(data)]
    cfg = pd / "config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text(encoding="utf-8"))
        out += [("config.json", k, c[k]) for k in ("title", "excerpt", "finding") if c.get(k)]
    return out


# ════════════════════════════════════════════════════════════════════════
# Numbers check
# ════════════════════════════════════════════════════════════════════════
@dataclass
class Hit:
    source: str
    loc: str
    token: str
    value: float
    status: str             # matched | allowed | unmatched
    detail: str
    context: str


def _blank(text: str) -> str:
    for rx in _BLANK:
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


def scan(text: str, truth: Truth, allow: list[tuple[re.Pattern, str]]) -> list[tuple]:
    t = _blank(text)
    allowed_spans = [(m.start(), m.end(), why) for rx, why in allow for m in rx.finditer(t)]
    hits = []
    for m in _NUM.finditer(t):
        intpart, frac, bare, suf = m.group("int"), m.group("frac"), m.group("bare"), (m.group("suf") or "").strip()
        digits = (intpart or "0").replace(",", "")
        x = float(digits + (frac or bare or ""))
        dec = len((frac or bare or ".")[1:])
        if not frac and not bare and not suf:
            if x < MIN_BARE_INT and "," not in (intpart or ""):
                continue
            if 1900 <= x <= 2099 and len(digits) == 4 and "," not in intpart:
                continue
        tol = 0.5 * 10 ** -dec + 1e-9
        if suf == "k":
            x, tol = x * 1000, 500 * 10 ** -dec
        why = next((w for s, e, w in allowed_spans if s <= m.start() and m.end() <= e), None)
        ctx = text[max(0, m.start() - 45):m.end() + 35].replace("\n", " ")
        token = m.group(0).strip()
        if why:
            hits.append((token, x, "allowed", why, ctx))
            continue
        path = truth.find(x, tol)
        if path:
            hits.append((token, x, "matched", path, ctx))
        else:
            near, npath = truth.nearest(x)
            hits.append((token, x, "unmatched", f"nearest {near:g} at {npath}", ctx))
    return hits


def check_numbers(project_dir: Path, *, allow: Iterable[tuple[str, str]] = (),
                  render: bool = True, report: bool = False) -> int:
    data = json.loads((project_dir / "data" / "data.json").read_text(encoding="utf-8"))
    truth = Truth(data)
    rules = [(re.compile(p, re.I), why) for p, why in [*DEFAULT_ALLOW, *allow]]
    hits: list[Hit] = []
    for source, loc, text in collect_copy(project_dir, data, render=render):
        for token, x, status, detail, ctx in scan(text, truth, rules):
            hits.append(Hit(source, loc, token, x, status, detail, ctx))

    bad = [h for h in hits if h.status == "unmatched"]
    print(f"== Numbers check: {project_dir.name} ==")
    print(f"  truth: {len(truth)} numeric values in data.json")
    by_src: dict[str, list[int]] = {}
    for h in hits:
        c = by_src.setdefault(h.source, [0, 0, 0])
        c[("matched", "allowed", "unmatched").index(h.status)] += 1
    for src, (m, a, u) in by_src.items():
        print(f"  [{'OK ' if not u else '!! '}] {src:<15} {m:>4} matched  {a:>3} allowed  {u:>3} unmatched")
    if report:
        for h in hits:
            if h.status != "unmatched":
                print(f"      {h.status:<8} {h.token:>12}  {h.source}:{h.loc}  <- {h.detail}")
    for h in bad:
        print(f"  [FAIL] {h.source} {h.loc}: '{h.token}'  ({h.detail})")
        print(f"         ...{h.context}...")
    return len(bad)


# ════════════════════════════════════════════════════════════════════════
# Standard check
# ════════════════════════════════════════════════════════════════════════
AUDIENCE_KEYS = ("coaches", "managers", "clubs", "agents")
EVIDENCE_KEYS = ("strong", "moderate", "exploratory")
REQUIRED_FILES = ("analysis.html", "config.json", "data/data.json", "methodology.md",
                  "methodology.html", "methodology.pdf", "slides.pptx", "slides.pdf")
FRESHNESS = (("slides.pdf", "slides.pptx"), ("methodology.html", "methodology.md"),
             ("methodology.pdf", "methodology.html"), ("slides.pptx", "data/data.json"))


def check_standard(project_dir: Path) -> int:
    pd = project_dir
    errors, warnings = [], []
    for f in REQUIRED_FILES:
        if not (pd / f).exists():
            errors.append(f"missing {f}")
    for newer, older in FRESHNESS:
        a, b = pd / newer, pd / older
        if a.exists() and b.exists() and a.stat().st_mtime < b.stat().st_mtime:
            warnings.append(f"{newer} is older than {older} -- rebuild/re-export it")

    data = json.loads((pd / "data" / "data.json").read_text(encoding="utf-8")) \
        if (pd / "data" / "data.json").exists() else {}
    tk = data.get("takeaways")
    if not isinstance(tk, dict):
        errors.append("data.json has no 'takeaways' object (four audiences)")
    else:
        for aud in AUDIENCE_KEYS:
            items = tk.get(aud)
            if not isinstance(items, list):
                errors.append(f"takeaways.{aud} missing (use [] for 'no defensible claim')")
                continue
            for i, it in enumerate(items):
                if it.get("evidence") not in EVIDENCE_KEYS:
                    errors.append(f"takeaways.{aud}[{i}].evidence = {it.get('evidence')!r}")
                if not it.get("text"):
                    errors.append(f"takeaways.{aud}[{i}] has no text")
                elif len(it["text"]) > 170:
                    warnings.append(f"takeaways.{aud}[{i}] is {len(it['text'])} chars "
                                    "(keep <= 140 so the slide card fits)")
            if len(items) > 2:
                warnings.append(f"takeaways.{aud} has {len(items)} items (slide fits 2)")

    cfg_path = pd / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not cfg.get("finding"):
            errors.append("config.json has no 'finding'")
        entries = {p["folder"]: p for p in json.loads((REPO_ROOT / "projects.json").read_text(encoding="utf-8"))}
        if pd.name not in entries:
            errors.append("project missing from projects.json")
        elif entries[pd.name] != cfg:
            diff = sorted(k for k in set(cfg) | set(entries[pd.name]) if cfg.get(k) != entries[pd.name].get(k))
            errors.append(f"config.json != projects.json entry (fields: {', '.join(diff)})")
        if bool(cfg.get("has_dashboard")) != (pd / "dashboard.html").exists():
            errors.append("config.has_dashboard disagrees with dashboard.html on disk")

    page = pd / "analysis.html"
    if page.exists():
        src = page.read_text(encoding="utf-8")
        for needle, what in (("renball-components.js", "shared components script"),
                             ('data-renball="slide-viewer"', "embedded slide viewer"),
                             ("renderTakeaways", "takeaways grid"),
                             ("methodology.pdf", "methodology PDF link"),
                             ("slides.pdf", "slides PDF link")):
            if needle not in src:
                errors.append(f"analysis.html lacks the {what} ({needle})")

    if (pd / "social").exists():
        import renball_social
        errors += [f"X package: {e}" for e in renball_social.validate(
            renball_social.Package.load(pd), verbose=False)]
    else:
        errors.append("social/ X package missing")

    print(f"== Standard check: {pd.name} ==")
    for w in warnings:
        print(f"  [WARN] {w}")
    for e in errors:
        print(f"  [FAIL] {e}")
    if not errors and not warnings:
        print("  [OK ] all deliverables present, fresh and consistent")
    return len(errors)


def main(project_dir: Path, *, allow: Iterable[tuple[str, str]] = (),
         argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=f"Verify {Path(project_dir).name}")
    ap.add_argument("--report", action="store_true", help="list matched numbers with their data.json paths")
    ap.add_argument("--static", action="store_true", help="skip the headless render of analysis.html")
    ap.add_argument("--numbers-only", action="store_true")
    ap.add_argument("--standard-only", action="store_true")
    a = ap.parse_args(argv)
    project_dir = Path(project_dir).resolve()
    fails = 0
    if not a.standard_only:
        fails += check_numbers(project_dir, allow=allow, render=not a.static, report=a.report)
    if not a.numbers_only:
        fails += check_standard(project_dir)
    print("VERIFY PASSED" if not fails else f"VERIFY FAILED ({fails} problem(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python assets/build/renball_verify.py projects/XX-name [--report] [--static]")
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), argv=sys.argv[2:]))
