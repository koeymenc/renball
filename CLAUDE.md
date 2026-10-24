# CLAUDE.md — Renball Project Rules

This file is read by Claude Code at the start of every session. It defines all conventions, design rules, and workflows for the Renball research portfolio.

---

## 1. PROJECT OVERVIEW

**Renball** is a football data research portfolio hosted at https://renball.com via GitHub Pages. The owner, Can Luca Köymen ("CK"), is a quantitative investment strategist in Zurich and Liverpool fan building Renball as his football-analytics CV, aiming for an analytics role at a professional club.

**The bar:** work a club's head of analytics would respect — statistical rigour, honest uncertainty, clear decisions for practitioners. CK publishes 1–2 research projects per week and builds an audience on X, so every project also ships a ready-to-post X package (§4).

**Repo:** https://github.com/koeymenc/renball
**Owner GitHub username:** koeymenc
**Local working folder:** `C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\Website\renball\`
**New project?** Follow §4 — §4.8 has the full workflow with checkpoints. `/renball-project` (`.claude/commands/renball-project.md`, local only — `.claude/` is untracked) is a shortcut for the same steps.

---

## 2. SITE ARCHITECTURE

```
renball/
├── CLAUDE.md                    ← This file. Always read first.
├── index.html                   ← Homepage. Auto-generated cards from projects.json.
├── projects.json                ← Master list of all research projects.
├── CNAME                        ← Custom domain config (renball.com).
├── README.md                    ← Public-facing repo readme.
├── requirements.txt             ← Pinned venv (.venv/, Python 3.12).
├── .claude/commands/
│   └── renball-project.md       ← /renball-project — the full standard, step by step.
├── assets/
│   ├── css/design-tokens.css    ← Design tokens + shared components (takeaways, evidence pills, slide viewer).
│   ├── js/chart-defaults.js     ← Chart.js global theme + RENBALL_HELPERS.niceRange.
│   ├── js/renball-components.js ← RENBALL.renderTakeaways() + PDF.js slide viewer.
│   ├── slides/renball_slide_master.py  ← Canonical deck builder (§6), incl. add_takeaways_slide.
│   ├── build/renball_pdf.py     ← PDFs: PowerPoint COM (slides) + headless Chrome (methodology); font preflight.
│   ├── build/renball_verify.py  ← Numbers check + standard check (§4.6).
│   ├── build/renball_qa.mjs     ← Headless page QA, desktop + 390 px phone (Node 22, no npm).
│   ├── social/renball_chart_style.py   ← matplotlib theme + X image export (1600×900, 1080×1350).
│   ├── social/renball_social.py ← X package: parser, X character count, validation, preview.html.
│   └── templates/               ← Legacy methodology/slides templates.
├── _template/                   ← Scaffold for new projects. Copy this folder.
│   ├── analysis.html            ← Page skeleton incl. takeaways, limitations, slide viewer.
│   ├── config.json              ← Card metadata.
│   ├── methodology.md           ← Source for methodology.html / .pdf.
│   ├── README.md
│   ├── code/build.py            ← Raw data → data/data.json (incl. takeaways).
│   ├── code/build_slides.py     ← data.json → slides.pptx (shared master).
│   ├── code/build_pdfs.py       ← Thin wrapper → renball_pdf.
│   ├── code/build_social.py     ← Chart images + X package validation + preview.
│   ├── code/verify.py           ← Thin wrapper → renball_verify (per-project ALLOW rules).
│   └── social/                  ← Thread / posts / alt text / posting guide skeletons.
└── projects/
    ├── 01-penalty-analysis/     ← Each research project lives in its own folder.
    ├── 02-points-by-gamestate/
    └── 03-true-contributors/
```

Generated per project: `data/data.json`, `methodology.html`, `methodology.pdf`, `slides.pptx`, `slides.pdf`, `social/images/*`, `social/preview.html`. `projects/*/social/` is gitignored — X drafts stay private.

---

## 3. DESIGN SYSTEM

The entire site uses one consistent design language. Never deviate.

### Color Palette
```
--bg              #080c08    Main background (deep pitch green-black)
--bg-elevated     #0e150e    Elevated surfaces (slightly lighter bg)
--bg-card         #111a11    Cards, panels
--bg-card-hover   #162016    Card hover state
--surface         #1a261a    Highest surface
--border          #1e2e1e    Subtle borders
--border-light    #2d3d2d    Hover/active borders
--text            #e8efe8    Main text (off-white)
--text-secondary  #8fa68f    Secondary text (muted green-grey)
--text-muted      #5a735a    Muted text (timestamps, labels)
--accent          #c1ff72    Primary accent (lime green)
--accent-dim      #8fbf45    Accent dim (hover states)
--accent-glow     rgba(193,255,114,0.06)  Subtle accent backgrounds
```
Chart series palette (chart-defaults.js / renball_chart_style.py): `#c1ff72 #72c1ff #ff72c1 #ffc172 #a472ff #72ffd4`.

### Typography
```
--serif    'Instrument Serif', Georgia, serif       Headlines, titles
--sans     'DM Sans', system-ui, sans-serif         Body text
--mono     'JetBrains Mono', monospace              Labels, captions, data, metadata
```

**Rules:**
- Headlines and project titles: always `--serif`, italic for emphasis with `--accent` color.
- Instrument Serif has one weight: never let the browser fake-bold or fake-italicise it. `design-tokens.css` sets `:where(h1…h6) { font-weight: 400; font-synthesis: none; }`; any other element set in `--serif` gets the same two declarations.
- Body and descriptions: `--sans`.
- Labels, dates, tags, monospace anywhere data-like appears: `--mono`, uppercase, letter-spacing 0.08em-0.14em.
- Never use sans-serif for headlines or serif for monospace labels.

**Local fonts:** web pages load Google Fonts; PowerPoint renders with fonts installed in Windows; matplotlib uses the bundled static TTFs in `assets/fonts/` (OFL, sources in its README). Instrument Serif **Regular and Italic**, DM Sans and JetBrains Mono must be installed for the current user — `python assets/build/renball_pdf.py --check-fonts` checks. A missing Instrument Serif Regular makes every slide headline italic (the accent emphasis disappears). Known quirk: PowerPoint files the variable JetBrains Mono under the name "Calibri" in exported PDFs while drawing the correct glyphs.

### Layout Principles
- Max content width: 1300px.
- Section padding: 6rem 3rem (desktop), 4rem 1.5rem (mobile).
- Card padding: 2rem.
- Grain texture overlay: always present (SVG noise fixed at z-index 9999, opacity 0.03).
- Subtle gradient backgrounds on hero sections with radial accent glow.
- Pitch-inspired decorative elements (circles, lines) at low opacity on hero areas.

### Component Patterns
- **Project cards**: 1px border, dark bg, project number in `--serif` 3rem top-right corner, key finding in accent-glow box with left border, tags in mono pills at bottom.
- **Buttons / CTAs**: solid accent background, dark text, uppercase mono label, 0.85rem padding.
- **Pills/tags**: 1px border, mono uppercase 0.65rem, 0.35rem padding.
- **Filter buttons**: same as pills but interactive with active state filled in accent.
- **Evidence pills**: Strong = accent fill; Moderate = accent-dim outline + accent text; Exploratory = dashed muted outline. Always with the 3-step meter (■■■ / ■■□ / ■□□) so the label never relies on colour alone.

---

## 4. THE RENBALL RESEARCH STANDARD

Every project — now and future — ships all of the following. `code/verify.py` enforces it.

### 4.1 Deliverables
| # | Deliverable | Produced by |
|---|---|---|
| 1 | `analysis.html` — editorial story | hand-written, numbers from `data.json` (§5) |
| 2 | `dashboard.html` — Tabulator explorer, **where the data supports it** | `code/dashboard.py` / `build.py` (§5) |
| 3 | `methodology.md` → `methodology.html` + `methodology.pdf` | `code/build_pdfs.py` → `renball_pdf` (§7) |
| 4 | `slides.pptx` → `slides.pdf`, PDF embedded as a slide viewer on `analysis.html` | `code/build_slides.py` (§6), `code/build_pdfs.py` |
| 5 | "Who should care" takeaways — page, slides **and** X thread | `data.json["takeaways"]` (§4.3) |
| 6 | `social/` X package | hand-written copy + `code/build_social.py` (§4.5) |
| 7 | `config.json` + identical `projects.json` entry | §8 |
| 8 | Numbers check — every figure traces to `data.json` | `code/verify.py` (§4.6) |

### 4.2 Rigour checklist (what a head of analytics will ask)
- **Effect sizes with intervals**, not just p-values. Wilson for proportions, bootstrap where no closed form exists.
- **Null results are bounded:** report power / minimum detectable effect, and use an equivalence test (TOST) before saying "no difference". "Not significant" alone is never the finding.
- **Confounders named and, where feasible, controlled** (regression / mixed model with the obvious covariates: player quality, league, season, home/away, game state). Say which ones aren't.
- **Small cells flagged** (n shown everywhere; sparse cells visually muted). Per-league splits of a small sample are exploratory by default.
- **Rankings carry uncertainty:** shrink rates toward the mean (empirical Bayes) instead of hand-picked minute filters; show rank intervals.
- **Repeatability before "skill":** season-to-season / split-half correlation decides whether a metric describes players or noise.
- **Out-of-sample where a model predicts** (held-out seasons, calibration / Brier score).
- **Multiple comparisons acknowledged** when many cells are tested.
- **Data provenance stated** — source, coverage, gaps (e.g. "SCA2 ends in 2023-24: source discontinued").
- **Plain language on the page, full detail in the methodology.** Every new method gets a one-paragraph lay explanation on `analysis.html`.
- **Limitations section** on the page, in the slides and in the X thread.

### 4.3 Four audiences + evidence labels
Takeaways live in `data.json["takeaways"]`, composed in `build.py` from computed values (f-strings — never hand-typed numbers):
```json
"takeaways": {
  "intro": "optional one-liner",
  "coaches":  [{"text": "<= 140 chars", "evidence": "strong|moderate|exploratory", "basis": "n = 3,857 · 95% CI …"}],
  "managers": [...], "clubs": [...], "agents": [...]
}
```
| Key | Audience | Focus |
|---|---|---|
| `coaches` | Coaches | Training & tactics |
| `managers` | Managers | Match-day decisions: substitutions, game management |
| `clubs` | Clubs | Recruitment, contracts, sporting directors |
| `agents` | Agents | How to position a player |

Max 2 takeaways per audience. `[]` renders "No defensible claim for this audience from this study" — say that rather than invent one.

**Evidence labels** (definitions also in `renball-components.js` and every methodology's "Evidence labels" section):
- **Strong** — large sample; the 95% interval excludes zero (or, for a "no effect" claim, sits inside a pre-stated equivalence margin); survives the main controls; holds across leagues or seasons.
- **Moderate** — consistent direction and plausible size, with one gap: interval touches zero, single method or sample, or partial replication.
- **Exploratory** — small samples, interval comfortably includes zero, untested confounders, or a pattern found by looking rather than tested. A question worth asking, not advice.

Never overclaim: when in doubt, label down.

### 4.4 Page structure additions
`analysis.html` (on top of §5): download row incl. `METHODOLOGY · PDF`; `<section class="proj" id="takeaways">` rendered by `RENBALL.renderTakeaways(el, data.takeaways)`; a **Limitations** section; **The deck** section with `<div class="slide-viewer" data-renball="slide-viewer" data-src="slides.pdf">` (PDF.js, lazy, works on mobile); `<script src="../../assets/js/renball-components.js">`. Format every number with the pinned **en-GB** locale (`toLocaleString('en-GB', …)` / `Intl.NumberFormat('en-GB', …)`, grouping 3,857) — never `undefined` or the default, which prints 3,857 as "3.857" for German/Swiss visitors.

### 4.5 X package (`projects/XX/social/`, gitignored)
- `thread.md` — one deep-dive thread, **12–18 posts**, each ≤ 280 characters *as X counts them* (URLs and bare domains = 23; `→ … ≥` = 2). Post 1 stands alone: hook + headline number + chart. Then the question, method in plain language, one finding per post, the four-audience takeaways with evidence labels, limitations, and a final post with the renball.com link and CK's handle **@renball** (set once in `renball_social.DEFAULT_HANDLE`). `[image: images/x.png]` lines mark images.
- `posts/NN-slug.md` — **5–8 standalone posts**, one finding each: `## Post`, `## Alt hook`, `## Image`, `## Caption`.
- `images/` — every chart as PNG via `renball_chart_style` (one chart = one idea, phone-legible; `save()` warns below ~9 css px on a 390 px phone). `alt_text.md` — alt text for every image (`## images/<file>`).
- `posting_guide.md` — posting order and spacing across the week, time windows framed as **experiments**, 5 likely objections with prepared replies (from the limitations), who to engage (analytics community; no spam-tagging players or clubs), what to pin, metrics to track. No unverifiable claims about the X algorithm.
- `preview.html` — generated by `code/build_social.py`; open locally.
- Tone: confident, evidence-led, slightly playful. No hype, no claims beyond the data, football language a coach would use.

### 4.6 Numbers check (`code/verify.py`)
Fails if any number printed in `analysis.html` (rendered DOM, after JS), `dashboard.html` (static text), `methodology.md`, `slides.pptx`, `social/` or `config.json` doesn't equal a numeric value in `data.json` at the precision shown (×100 / ÷100 for proportion ↔ percent). Derived figures (ratios, totals, differences) go **into `data.json` via `build.py`** — the page never computes a number the verifier can't trace. Allow-rules are only for non-claims (CI levels, α, illustrative minutes) and always carry a reason. It also checks the standard: deliverables present, PDFs fresher than sources, `config.json` == `projects.json` entry, `has_dashboard` truthful, takeaways well-formed, X package valid.

### 4.7 Toolchain (CK's Windows machine)
- Python: repo `.venv/` (3.12) — always `.venv/Scripts/python.exe`. ASCII-only `print()`s (cp1252 console), or set `PYTHONIOENCODING=utf-8`.
- Slides PDF: installed PowerPoint via COM (`pywin32`); ~20 s per deck; opens read-only, so a deck open in PowerPoint is fine — but close `slides.pdf` in any viewer first.
- Methodology PDF: headless Chrome (`--print-to-pdf`, throwaway profile). Light print theme by default (white paper, dark masthead band, lime only as highlighter/rules); `--theme dark` for a dark variant. Math: `$$…$$` / `\(…\)` render with KaTeX.
- Page QA: `node assets/build/renball_qa.mjs <pages…>` — desktop + 390 px phone, console errors, failed requests, horizontal overflow, full-page screenshots.
- Local server for manual review: `.venv/Scripts/python.exe -m http.server 8811 --bind 127.0.0.1` from repo root (port 8765 belongs to another local app).

### 4.8 Workflow and checkpoints (self-contained — `/renball-project` is only a local shortcut)
Every project session follows these phases. **Stop at each checkpoint and wait for CK.**

**Phase 0 — orient.** Read this file. Next free project number in `projects/`. `renball_pdf.py --check-fonts`. Read CK's code end to end; note the data source and the **unit of analysis** (matches vs penalties vs player-seasons) — every sample size must name its unit.

**Phase A — scaffold + analysis.** `cp -r _template projects/NN-slug`; adapt the analysis into `code/build.py` (env-var paths, existing data only); apply every item of the rigour checklist (§4.2), recording *done / n.a. / not feasible + why*; write every displayed number (derived ones too) and the `takeaways` into `data.json`.
> ✋ **Checkpoint A — findings before polish:** headline result with its interval, the rigour table, proposed takeaways + evidence labels with the reasoning for each label, proposed title / finding / excerpt, anything that weakens the story.

**Phase B — deliverables.** `analysis.html` (§4.4, §5) → `dashboard.html` if warranted → `methodology.md` (§7) → `code/build_slides.py` (look at every slide as PNG via `renball_pdf.pptx_to_pngs`) → `code/build_pdfs.py` (read the font audit) → X package (§4.5) + `code/build_social.py` → `config.json` + `projects.json` → `code/verify.py` must print `VERIFY PASSED` → `node assets/build/renball_qa.mjs <pages>` must pass (desktop + 390 px).
> ✋ **Checkpoint B — local review:** serve on 8811 and give CK the page URLs, `social/preview.html`, the post-count table, verify + QA summaries and any judgement calls.

**Phase C — ship.** Re-run verify + QA; `git status` shows no raw data, no `social/`, no `_diag*`, no file > 5 MB; show the commit summary.
> ✋ **Checkpoint C:** commit + push only after CK says **"go"**.

Fixing a live project follows the same phases. Until renball.com has an audience (CK's call, October 2026), corrections are made in place: page, slides and methodology show the current method and numbers, with no correction notes and no references to earlier versions. Once it has an audience, a correction that changes a published claim gets a dated "Correction" note on the page and in the methodology (`.notice` in `design-tokens.css`) — never a silent edit.

---

## 5. DASHBOARD STANDARDS

Every project gets an `analysis.html` page. Rules:

### Structure
1. **Back link** to homepage (top left, mono uppercase).
2. **Hero header**: project title (serif large), date + tags meta line (mono).
3. **Key finding banner**: accent-glow box with the headline result.
4. **Sections**: Overview → Data & Methodology summary → Charts/Visuals → Findings → Who should care → Limitations → Conclusion → The deck (§4.4).
5. **Download row**: links to `slides.pdf`, `methodology.html` and `methodology.pdf` near the top.

### Dual-page pattern
Where the data supports exploration (player/team tables, many cells), ship `dashboard.html` alongside: a Tabulator drill-down reading `data/dashboard/manifest.json` + lazy-loaded chunks (§10). It needs an intro panel, a "how to read this" note per view and column tooltips. Set `has_dashboard: true` in `config.json`.

### Charts
- **Default library: Chart.js** (via CDN: `https://cdn.jsdelivr.net/npm/chart.js`).
- **Football-specific visuals (pitch maps, passing networks): D3.js**.
- Every chart must use the design tokens via the shared `chart-defaults.js` (grid color, font, accent, font sizes, layout).
- Charts read from `data/data.json` — never hardcode data in HTML.
- Each chart must have: a serif title above, mono caption below explaining context.
- **Use `RENBALL_HELPERS.niceRange(values, opts?)`** for the y-axis on percentage / proportion charts. Forcing `beginAtZero: true` + `suggestedMax: 100` crushes 60–85% variation flat — `niceRange` snaps to multiples of 5 (configurable), pads ±4 pp by default, and clamps to [0, 100]. Pass CI bounds too when the chart shows error whiskers. (Python twin for slides / X images: `renball_chart_style.nice_range`.)
- Default chart aspect ratio is `3:1` (wide, laptop-friendly height ~325px). Set globally in `chart-defaults.js` — don't override per-chart unless there's a good reason.
- Show uncertainty: CI whiskers or bands wherever an estimate is plotted.

### Interactivity
- Filters (competition, season, etc.) at top of chart section.
- Hover tooltips always on.
- Mobile responsive — charts must reflow. Check with `renball_qa.mjs` (390 px).

---

## 6. POWERPOINT (slides.pptx) RULES

Every project ships a slideshow built programmatically with python-pptx.

### Canonical builder: `assets/slides/renball_slide_master.py`

**Never reimplement styling in a per-project `build_slides.py`.** Import from the shared module and use its high-level slide builders. The module owns all Renball design tokens, fonts, matplotlib equivalents, page numbering, the wordmark, and the standard slide layouts. If a project needs a bespoke layout, drop down to the low-level primitives (`add_blank_slide`, `add_text`, `add_rect`, `new_chart`, etc.) — still imported from the same module.

```python
# code/build_slides.py
import sys
from pathlib import Path
SHARED = Path(__file__).resolve().parents[3] / "assets" / "slides"
sys.path.insert(0, str(SHARED))
import renball_slide_master as R

prs = R.create_deck()
R.add_title_slide(prs, "Not All Goals Are Equal", subtitle="…", project_num="02")
R.add_bullet_slide(prs, "TL;DR", ["Bullet 1", "Bullet 2", "Bullet 3"])
# … more slides …
R.add_takeaways_slide(prs, d["takeaways"])     # four audiences + evidence labels
R.finalize_deck(prs)          # stamps page numbers
prs.save("slides.pptx")
```

High-level slide functions available: `add_title_slide`, `add_section_slide`, `add_bullet_slide`, `add_two_column_slide`, `add_chart_slide`, `add_table_slide`, `add_quote_slide`, `add_takeaways_slide`, `add_closing_slide`. See the module docstring for full parameters. `new_chart()` uses the brand fonts via `renball_chart_style` (DM Sans text, JetBrains Mono ticks).

### Branding (enforced by the module)
- 16:9 (13.333" × 7.5")
- **Strict slide zones** (constants exported from the module):
  - `TITLE_AREA_TOP=0.4` – `TITLE_AREA_BOTTOM=1.3` — eyebrow + serif title + accent underline
  - `BODY_TOP=1.6` – `BODY_BOTTOM=6.8` — charts, cards, tables, bullet lists, custom layouts
  - `CAPTION_TOP=6.5` – `CAPTION_BOTTOM=6.8` — mono caption row (inside body zone)
  - `FOOTER_TOP=6.9` – `FOOTER_BOTTOM=7.4` — logo bottom-left, page number bottom-right
- Background: `BG` (#080c08)
- Headlines: Instrument Serif, `TEXT` (#e8efe8). **Accent phrases** marked with `*…*` in the title string render in `ACCENT` (#c1ff72), italic.
- Body: DM Sans, `TEXT_SECONDARY` (#8fa68f)
- Captions / eyebrows / labels: JetBrains Mono uppercase, `TEXT_MUTED` (#5a735a) by default; `ACCENT` for emphasis
- **Bottom-left:** ren·ball wordmark ("ball" in accent), 16pt
- **Bottom-right:** page number in muted mono (auto-stamped by `finalize_deck`; title + closing slides skipped)
- Every text run sets `font.name` explicitly — the module never relies on PowerPoint's theme default
- Charts: matplotlib palette via `MPL_*` constants; `add_chart_slide` auto-fits the figure inside the body zone (preserves aspect ratio, clamps height)

#### Accent runs in titles

Wrap any phrase in asterisks to mark it for italic + accent rendering:

```python
R.add_title_slide(prs, "Not All Goals Are *Equal*.")
R.add_section_slide(prs, "01", "Why the *late* equaliser matters")
R.add_bullet_slide(prs, "What this *changes*", bullets=[...])
```

The asterisks are stripped at render time; the marked segment becomes a separate Run with `italic=True` and `color=ACCENT`. The parser is exposed as `parse_accent_runs(text)` for callers building bespoke layouts. The same convention works in X image titles (`renball_chart_style`).

### Slide structure (default narrative)
1. **Title slide** — project name (with optional italic accent phrase), subtitle in mono, date
2. **TL;DR / Agenda** — 3–5 bullets, one finding in accent
3. **Context** — why the question matters
4. **Data & Method** — sources, sample size, approach (1–2 slides max)
5. **Results** — one chart/insight per slide; mono captions; intervals shown
6. **Who should care** — `add_takeaways_slide` (four audiences, evidence labels)
7. **Limitations** — what this can't tell you
8. **Conclusion** — key takeaway + accent-highlighted headline number
9. **Sources & Contact** — closing slide with `renball.com` in accent

Project-specific decks may insert extra slides (e.g. a "spotlight" callout on a player). Keep the overall arc.

### Export
- Generate `slides.pptx` programmatically: `python code/build_slides.py`
- Optionally refine in PowerPoint, then export: `python code/build_pdfs.py --only slides` (drives the installed PowerPoint via COM — no manual export, no LibreOffice).
- The export prints the fonts the PDF embedded and warns when a brand face was substituted.
- Keep both `slides.pptx` and `slides.pdf` committed.

---

## 7. METHODOLOGY RULES

Every project ships `methodology.md` (source of truth) → `methodology.html` (screen, dark theme) → `methodology.pdf` (print, light theme). One command: `python code/build_pdfs.py --only methodology`.

`methodology.html` loads the brand fonts from Google Fonts, has a back link to the analysis and a readable measure on screen; its `@media print` stylesheet is the PDF (white paper, dark masthead band, page numbers in the footer), so a reader's Ctrl+P matches the shipped PDF. Display math `$$…$$` and inline `\(…\)` render with KaTeX.

### Structure
1. **Title + Author + Date**
2. **Abstract** (3-5 sentences)
3. **Research Question** (formal statement, null/alternative hypotheses if applicable)
4. **Data**
   - Sources (with URLs)
   - Sample size (and the unit of analysis — matches vs penalties vs player-seasons)
   - Time period
   - Cleaning/filtering decisions
5. **Methodology**
   - Statistical tests used (with assumptions — and whether they hold)
   - Feature engineering
   - Software stack
6. **Results** (with all numbers, intervals, p-values, effect sizes, power / MDE)
7. **Practical takeaways** — the four audiences, with the **Evidence labels** definitions (§4.3)
8. **Limitations**
9. **References**

### Style
- Citations in footnotes (`[^1]`).
- Code snippets in monospace.
- Every number must trace to `data.json` (`code/verify.py` checks methodology.md too).

---

## 8. CONFIG.JSON SCHEMA

Every project folder contains a `config.json`. Same schema as the entry in `projects.json` at repo root — `verify.py` fails if they differ.

```json
{
  "folder": "01-penalty-analysis",
  "title": "The GK's Self-Inflicted Penalty: A Conversion Rate Analysis",
  "date": "May 2026",
  "type": "HTML + PDF",
  "tags": ["Top 5 Leagues", "Penalties", "Hypothesis Test"],
  "filter": ["tactical", "set-pieces"],
  "excerpt": "Does the goalkeeper's own foul affect penalty conversion? Two hypothesis tests across 5 leagues over multiple seasons.",
  "finding": "No statistically significant difference — neither GK fouling nor self-won penalties affect conversion.",
  "has_html": true,
  "has_pdf": true,
  "has_methodology": true,
  "has_dashboard": false
}
```

- **`has_pdf`**: `slides.pdf` exists (methodology.pdf is now always part of the standard).
- **`has_dashboard`** (optional, defaults to `false` if omitted): set to `true` when the project ships an interactive Tabulator-based `dashboard.html` alongside the editorial `analysis.html` (see §5 dual-page pattern). The homepage card uses this to render an explicit "Dashboard" link.

When adding a project, this same JSON object must also be appended to `projects.json` at the repo root.

---

## 9. WORKFLOW: ADDING A NEW PROJECT

The `/renball-project` command runs this end to end with checkpoints. Manually:

1. **Scaffold** — `cp -r _template projects/04-my-new-project`
2. **Config** — edit `config.json` (title ≤ 12 words, `finding` required).
3. **Analysis** — adapt CK's Python into `code/build.py`; output `data/data.json` with every number the copy needs (derived figures included) and `takeaways`. Run the rigour checklist (§4.2).
4. **Page** — customise `analysis.html` (Chart.js from `data.json`, takeaways, limitations, slide viewer).
5. **Dashboard** — only if the data supports exploration (§5).
6. **Methodology** — write `methodology.md`.
7. **Slides** — `code/build_slides.py` → `slides.pptx`.
8. **PDFs** — `python code/build_pdfs.py` (methodology.html/.pdf + slides.pdf).
9. **X package** — write `social/*.md`, then `python code/build_social.py` (images + validation + preview).
10. **Verify** — `python code/verify.py` must pass; `node assets/build/renball_qa.mjs projects/XX/analysis.html` must pass.
11. **List it** — append the `config.json` object to `projects.json`.
12. **Review + push** — CK reviews locally; commit + push only after CK says go.
```bash
git add .
git commit -m "Add project: [project name]"
git push
```
Site updates in ~60 seconds.

---

## 10. RAW DATA HANDLING

CK works with large pickle files in two source directories:
- `C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA\` — aggregate / feature pickles (e.g. `MATCH_WAGES_FEATURES.pkl`, `FULL_DICT_ROWS.pkl`, `FULL_DATA_DICT.pkl`, `ALL_TEAMS_MAPPED.xlsx`).
- `C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\DATA\MATCH_DATA\` — per-league match-event pickles `match_data_final_<league>.pkl` (Premier-League, Serie-A, Bundesliga, La-Liga, Ligue-1, Eredivisie). Files containing `CHECK` in the name are ignored.

**Rules:**
- **Never commit raw pickle files or large datasets to the repo.** Use `.gitignore`.
- The Python build script (`code/build.py`) loads raw data from the local source folder, processes it, and outputs only the aggregated artefacts the front-end needs — `data/data.json` for the editorial page, plus a `data/dashboard/` tree if the project ships a Tabulator dashboard.
- **5 MB limit is per individual file**, not per project. Sample/processed JSON/CSV under ~5 MB may be committed for transparency. Anything larger should be **split across multiple files** with a `manifest.json` listing them — every chunk stays under the cap and the front-end lazy-loads on demand. The Project 02 dashboard demonstrates this: `data/dashboard/manifest.json` + per-`(dataset, view)` JSONs in dataset-named subfolders, each ≤ ~4 MB. To shrink large tabular payloads, combine: compact JSON (no whitespace), 3-decimal float rounding, sparse encoding (drop numeric-zero keys), short keys (`cnt_X_to_Y` → `g.X.Y`, etc.) reconstructed client-side, and dropping derived columns the front-end can recompute. Sparse keys + the recompute spec belong in the manifest so the dashboard JS can decode without out-of-band knowledge.
- Always paths-as-variables — never hardcode absolute paths in committed code. Standard env vars:
  - `RENBALL_DATA_PATH` → READY_DATA folder.
  - `RENBALL_MATCH_DATA_PATH` → MATCH_DATA folder.
  Read them with `os.environ.get("...", "<sensible default>")`.
- **Scope:** use the data already on disk; new scraping is a separate, explicit decision.

---

## 11. DATA STRUCTURE CONVENTIONS

CK's typical data structures (from existing analyses):

### Top-level dicts
- `FULL_DICT_ROWS` — Nested dict by competition, then `ROWS_DICTS_SPECIALS` and `ROWS_DICTS_SUMMARY`, each keyed by season → DataFrame.
- `FULL_DATA_DICT` — Similar structure.
- `MATCH_WAGES_FEATURES` — Match-level features with wage data.

### Competition keys
`PL` (Premier League), `SERIEA` (Serie A), `BUNDESLIGA`, `LALIGA`, `LIGUE1`.

### Common DataFrame columns
- Identification: `Competition`, `Season`, `match_id`, `Player`, `team_name`, `team_id`, `opposition_name`, `opposition_id`.
- Context: `date`, `dayofweek`, `gameweek`, `site` (home/away), `team_formation`, `opposition_formation`, `score`, `outcome`, `attendance`.
- Performance: `xg_scored`, `xg_conceded`, `goals_scored`, `goals_conceded`, `Min`, `Min Match Weight`.
- Position: `Pos` (with values like `GK`, `DF`, `MF`, `FW`).
- Penalty-specific: `Performance_PK`, `Performance_PKatt`, `Performance_PKwon`, `Performance_PKcon`.

---

## 12. TONE & COPY

CK's voice on the site is direct, evidence-led, and slightly playful. Examples:
- "No punditry — just evidence."
- "Shedding light on myths of the beautiful game."
- "Just a Liverpool fan that loves football and decoding the beautiful game with his laptop."

When writing project copy:
- Lead with the finding, not the method.
- Use mono captions for numbers and stats.
- Keep excerpts to 1-2 sentences.
- One headline number per project, in accent color.
- Avoid jargon in card excerpts. Save technical depth for methodology.html.
- Say what the uncertainty is in plain words ("could be anywhere from −12 to +6 pp"), never hide it behind "not significant".
- Football language a coach would use. No hype, no claims beyond the data.

---

## 13. NEVER DO

- Don't commit raw data files (pickles, large CSVs).
- Don't hardcode data in `analysis.html` — always read from `data/data.json`. Don't compute a displayed figure in JS that `data.json` doesn't hold.
- Don't hand-type a number into copy (page, slides, methodology, X) — compose it from `data.json`; `verify.py` will fail.
- Don't add inline `<style>` per project for shared components — they live in `assets/css/design-tokens.css`.
- Don't break the design system — no new colors, fonts, or random spacing.
- Don't ship a project missing any Research Standard deliverable (§4.1). `dashboard.html` is the only optional one, and only when the data doesn't support exploration.
- Don't label a takeaway Strong unless it meets the definition (§4.3). When in doubt, label down.
- Don't present "not significant" as "no effect" — bound it (power / MDE / equivalence).
- Don't ship a project without a `finding` field in config.json — the green key-finding box is part of the brand.
- Don't write project titles longer than ~12 words.
- Don't commit `projects/*/social/` drafts, `.pyc`, `__pycache__`, `.DS_Store`, or IDE files.
- Don't tag players, clubs or journalists on X to borrow reach; don't make claims about the X algorithm — frame timing as experiments.
- Don't push until CK has reviewed and said go.

---

## 14. CLAUDE CODE WORKFLOW

When CK starts a new project session, run `/renball-project` (or follow §9). The shape:

1. CK shares the Python analysis code / question.
2. Claude Code reads this file, scaffolds from `_template/`, adapts the analysis into `code/build.py`, applies the rigour checklist (§4.2), and **pauses** with the results and proposed takeaways + evidence labels.
3. After CK agrees the findings: page, dashboard (if warranted), methodology, slides, PDFs, X package, verify, QA — then **pauses** with local URLs (`http://127.0.0.1:8811/projects/XX/analysis.html`) and `social/preview.html`.
4. CK reviews; Claude shows the commit summary; push only after "go".
