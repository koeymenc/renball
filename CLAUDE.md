# CLAUDE.md — Renball Project Rules

This file is read by Claude Code at the start of every session. It defines all conventions, design rules, and workflows for the Renball research portfolio.

---

## 1. PROJECT OVERVIEW

**Renball** is a football data research portfolio hosted at https://renball.com via GitHub Pages. The owner, Can Luca Köymen ("CK"), is a data analyst in Zurich and Liverpool fan who publishes independent football analytics research as portfolio work toward a career as a data analyst in a professional football club.

**Repo:** https://github.com/koeymenc/renball
**Owner GitHub username:** koeymenc
**Local working folder:** `C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\Website\renball\`

---

## 2. SITE ARCHITECTURE

```
renball/
├── CLAUDE.md                    ← This file. Always read first.
├── index.html                   ← Homepage. Auto-generated cards from projects.json.
├── projects.json                ← Master list of all research projects.
├── CNAME                        ← Custom domain config (renball.com).
├── README.md                    ← Public-facing repo readme.
├── assets/
│   ├── css/
│   │   └── design-tokens.css    ← Shared design system (CSS variables).
│   ├── js/
│   │   └── chart-defaults.js    ← Chart.js global config (theme).
│   └── templates/
│       ├── methodology.md       ← Markdown template for methodology PDFs.
│       └── slides.pptx          ← PowerPoint master for slideshows.
├── _template/                   ← Scaffold for new projects. Copy this folder.
│   ├── analysis.html            ← Dashboard skeleton.
│   ├── code/
│   │   └── build.py             ← Python build script (raw data → data.json).
│   ├── data/
│   │   └── data.json            ← Pre-aggregated chart data.
│   ├── methodology.md           ← Source for methodology.html.
│   ├── methodology.html         ← Generated, styled, browser-readable (canonical deploy).
│   ├── slides.pptx              ← Editable PowerPoint.
│   ├── slides.pdf               ← Exported PDF (final, manual export from PowerPoint).
│   ├── config.json              ← Card metadata.
│   └── README.md                ← Project notes.
└── projects/
    ├── 01-penalty-analysis/     ← Each research project lives in its own folder.
    ├── 02-xg-model/
    └── ...
```

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

### Typography
```
--serif    'Instrument Serif', Georgia, serif       Headlines, titles
--sans     'DM Sans', system-ui, sans-serif         Body text
--mono     'JetBrains Mono', monospace              Labels, captions, data, metadata
```

**Rules:**
- Headlines and project titles: always `--serif`, italic for emphasis with `--accent` color.
- Body and descriptions: `--sans`.
- Labels, dates, tags, monospace anywhere data-like appears: `--mono`, uppercase, letter-spacing 0.08em-0.14em.
- Never use sans-serif for headlines or serif for monospace labels.

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

---

## 4. DASHBOARD STANDARDS

Every project gets an `analysis.html` dashboard. Rules:

### Structure
1. **Back link** to homepage (top left, mono uppercase).
2. **Hero header**: project title (serif large), date + tags meta line (mono).
3. **Key finding banner**: accent-glow box with the headline result.
4. **Sections**: Overview → Data & Methodology summary → Charts/Visuals → Findings → Conclusion.
5. **Download row**: links to `slides.pdf` and `methodology.html` near the top.

### Charts
- **Default library: Chart.js** (via CDN: `https://cdn.jsdelivr.net/npm/chart.js`).
- **Football-specific visuals (pitch maps, passing networks): D3.js**.
- Every chart must use the design tokens via the shared `chart-defaults.js` (grid color, font, accent, font sizes, layout).
- Charts read from `data/data.json` — never hardcode data in HTML.
- Each chart must have: a serif title above, mono caption below explaining context.
- **Use `RENBALL_HELPERS.niceRange(values, opts?)`** for the y-axis on percentage / proportion charts. Forcing `beginAtZero: true` + `suggestedMax: 100` crushes 60–85% variation flat — `niceRange` snaps to multiples of 5 (configurable), pads ±4 pp by default, and clamps to [0, 100]. Pass CI bounds too when the chart shows error whiskers.
- Default chart aspect ratio is `3:1` (wide, laptop-friendly height ~325px). Set globally in `chart-defaults.js` — don't override per-chart unless there's a good reason.

### Interactivity
- Filters (competition, season, etc.) at top of chart section.
- Hover tooltips always on.
- Mobile responsive — charts must reflow.

---

## 5. POWERPOINT (slides.pptx) RULES

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
R.finalize_deck(prs)          # stamps page numbers
prs.save("slides.pptx")
```

High-level slide functions available: `add_title_slide`, `add_section_slide`, `add_bullet_slide`, `add_two_column_slide`, `add_chart_slide`, `add_table_slide`, `add_quote_slide`, `add_closing_slide`. See the module docstring for full parameters.

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

The asterisks are stripped at render time; the marked segment becomes a separate Run with `italic=True` and `color=ACCENT`. The parser is exposed as `parse_accent_runs(text)` for callers building bespoke layouts.

### Slide structure (default narrative)
1. **Title slide** — project name (with optional italic accent phrase), subtitle in mono, date
2. **TL;DR / Agenda** — 3–5 bullets, one finding in accent
3. **Context** — why the question matters
4. **Data & Method** — sources, sample size, approach (1–2 slides max)
5. **Results** — one chart/insight per slide; mono captions
6. **Discussion** — what it means
7. **Conclusion** — key takeaway + accent-highlighted headline number
8. **Sources & Contact** — closing slide with `renball.com` in accent

Project-specific decks may insert extra slides (e.g. a "spotlight" callout on a player). Keep the overall arc.

### Export
- Generate `slides.pptx` programmatically: `python code/build_slides.py`
- Open in PowerPoint, refine if needed, then **manually export to `slides.pdf`** (File → Export → Create PDF/XPS). LibreOffice CLI conversion is supported as a fallback if `soffice` is on the path.
- Keep both `slides.pptx` and `slides.pdf` committed.

---

## 6. METHODOLOGY HTML RULES

**Standing rule (current toolchain):** Every project ships a `methodology.html` and **no methodology PDF**. The HTML is the sole canonical deploy artifact — readers open it directly in a browser, and anyone who wants a PDF can use the browser's print-to-PDF.

This rule applies until a proper Markdown→PDF toolchain is set up locally (WeasyPrint + GTK, or equivalent). Until then: do not commit a `methodology.pdf`, do not link to one from `analysis.html`, and `has_pdf` in `config.json` refers to `slides.pdf` only.

`methodology.html` is generated from `methodology.md` by `code/build_pdfs.py`, styled inline with the Renball design tokens (dark background, accent headlines, mono code blocks), and deployed alongside the dashboard.

### Source: `methodology.md`
Markdown is the single source of truth — write it there, regenerate the HTML with `python code/build_pdfs.py`.

### Structure
1. **Title + Author + Date**
2. **Abstract** (3-5 sentences)
3. **Research Question** (formal statement, null/alternative hypotheses if applicable)
4. **Data**
   - Sources (with URLs)
   - Sample size
   - Time period
   - Cleaning/filtering decisions
5. **Methodology**
   - Statistical tests used (with assumptions)
   - Feature engineering
   - Software stack
6. **Results** (with all numbers, p-values, effect sizes)
7. **Limitations**
8. **References**

### Style
- Renders with the dark Renball theme via the inline stylesheet in `build_pdfs.py`.
- Citations in footnotes.
- Code snippets in monospace.

---

## 7. CONFIG.JSON SCHEMA

Every project folder contains a `config.json`. Same schema as the entry in `projects.json` at repo root.

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

**`has_dashboard`** (optional, defaults to `false` if omitted): set to `true` when the project ships an interactive Tabulator-based `dashboard.html` alongside the editorial `analysis.html` (see §4 for the dual-page pattern). The homepage card uses this to render an explicit "Dashboard" link.

When adding a project, this same JSON object must also be appended to `projects.json` at the repo root.

---

## 8. WORKFLOW: ADDING A NEW PROJECT

### Step 1 — Copy the template
```bash
cp -r _template projects/02-my-new-project
```

### Step 2 — Update config.json
Edit `projects/02-my-new-project/config.json` with the project details.

### Step 3 — Place your raw Python analysis code
Put the original Python script in `code/`. Adapt it so it outputs:
- A `data.json` to `data/data.json` with all aggregated numbers needed for the dashboard.

### Step 4 — Customize the dashboard
Edit `analysis.html` — swap in project title, key finding text, and Chart.js configs that read from `data/data.json`.

### Step 5 — Write methodology
Edit `methodology.md`, then run `python code/build_pdfs.py` to regenerate `methodology.html`. No PDF (see §6).

### Step 6 — Build slides
Edit `slides.pptx`. Manually export to PDF as `slides.pdf` (File → Export → Create PDF/XPS in PowerPoint).

### Step 7 — Add to master projects list
Append the same `config.json` object to `projects.json` at repo root.

### Step 8 — Push
```bash
git add .
git commit -m "Add project: [project name]"
git push
```

Site updates in ~60 seconds.

---

## 9. RAW DATA HANDLING

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

---

## 10. DATA STRUCTURE CONVENTIONS

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

## 11. TONE & COPY

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

---

## 12. NEVER DO

- Don't commit raw data files (pickles, large CSVs).
- Don't hardcode data in `analysis.html` — always read from `data/data.json`.
- Don't add inline `<style>` per project — use the shared `assets/css/design-tokens.css`.
- Don't break the design system — no new colors, fonts, or random spacing.
- Don't deviate from the 4-file deliverable per project (analysis.html, slides.pdf, methodology.html, config.json). Some projects also ship a `dashboard.html` (full interactive Tabulator drill-down — see §4) as a 5th file.
- Don't commit a `methodology.pdf` until the toolchain is set up — methodology.html is the sole canonical artifact.
- Don't ship a project without a `finding` field in config.json — the green key-finding box is part of the brand.
- Don't write project titles longer than ~12 words.
- Don't commit `.pyc`, `__pycache__`, `.DS_Store`, or IDE files.

---

## 13. CLAUDE CODE WORKFLOW PROMPTS

When CK starts a new Claude Code session for a project, the conversation should follow:

1. CK shares the Python analysis code.
2. Claude Code:
   - Reads CLAUDE.md (this file).
   - Copies `_template/` to `projects/XX-name/`.
   - Updates `config.json` based on the analysis.
   - Adapts the Python code into `code/build.py` that writes `data/data.json`.
   - Runs the build script to generate `data.json`.
   - Customizes `analysis.html` to load and render the data with Chart.js.
   - Writes `methodology.md` based on the analysis logic.
   - Drafts slide content for `slides.pptx`.
   - Appends the new project to `projects.json` at repo root.
   - Asks CK to review before commit.
3. CK reviews dashboard locally, refines slides in PowerPoint, exports PDFs.
4. Git commit + push.
