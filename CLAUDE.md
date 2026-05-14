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
│   ├── methodology.md           ← Source for methodology.pdf.
│   ├── slides.pptx              ← Editable PowerPoint.
│   ├── slides.pdf               ← Exported PDF (final).
│   ├── methodology.pdf          ← Exported PDF (final).
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
5. **Download row**: links to `slides.pdf` and `methodology.pdf` near the top.

### Charts
- **Default library: Chart.js** (via CDN: `https://cdn.jsdelivr.net/npm/chart.js`).
- **Football-specific visuals (pitch maps, passing networks): D3.js**.
- Every chart must use the design tokens via the shared `chart-defaults.js` (grid color, font, accent).
- Charts read from `data/data.json` — never hardcode data in HTML.
- Each chart must have: a serif title above, mono caption below explaining context.

### Interactivity
- Filters (competition, season, etc.) at top of chart section.
- Hover tooltips always on.
- Mobile responsive — charts must reflow.

---

## 5. POWERPOINT (slides.pptx) RULES

Every project ships a slideshow. Rules:

### Branding
- Background: `--bg` (#080c08).
- Headlines: Instrument Serif, white/off-white.
- Body: DM Sans.
- Accent color: `--accent` (#c1ff72) for highlights, key numbers, divider lines.
- Logo top-left: "ren**ball**" — "ball" in accent.

### Slide Structure
1. **Title slide**: Project name (serif, big), subtitle in mono, date.
2. **Agenda / TL;DR**: 3-5 bullets, one key finding highlighted in accent.
3. **Context**: Why this question matters.
4. **Data & Method**: Sources, sample size, approach (1-2 slides max).
5. **Results**: One chart/insight per slide. Use mono captions.
6. **Discussion**: What it means.
7. **Conclusion**: Key takeaway + accent-highlighted headline number.
8. **Sources & Contact**: Last slide with renball.com.

### Export
- Always export as `slides.pdf` once finalized.
- Keep `slides.pptx` editable in the folder for future updates.

---

## 6. METHODOLOGY PDF RULES

Every project ships a `methodology.pdf` for technical depth.

### Source: `methodology.md`
Written in Markdown, converted to PDF on build.

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
- Match website design via the markdown PDF template (dark theme PDF when rendered).
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
  "has_methodology": true
}
```

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
Edit `methodology.md`. Export to PDF.

### Step 6 — Build slides
Edit `slides.pptx`. Export to PDF as `slides.pdf`.

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

CK works with large pickle files in `C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA\`. Examples:
- `MATCH_WAGES_FEATURES.pkl`
- `FULL_DICT_ROWS.pkl`
- `FULL_DATA_DICT.pkl`
- `ALL_TEAMS_MAPPED.xlsx`

**Rules:**
- **Never commit raw pickle files or large datasets to the repo.** Use `.gitignore`.
- The Python build script (`code/build.py`) loads raw data from the local READY_DATA folder, processes it, and outputs only the aggregated `data.json` needed for the dashboard.
- Sample/processed CSVs under ~5MB may be committed for transparency. Anything larger stays local.
- Always paths-as-variables — never hardcode absolute paths in committed code. Use `os.environ.get("RENBALL_DATA_PATH", "default/relative/path")`.

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
- Avoid jargon in card excerpts. Save technical depth for methodology.pdf.

---

## 12. NEVER DO

- Don't commit raw data files (pickles, large CSVs).
- Don't hardcode data in `analysis.html` — always read from `data/data.json`.
- Don't add inline `<style>` per project — use the shared `assets/css/design-tokens.css`.
- Don't break the design system — no new colors, fonts, or random spacing.
- Don't deviate from the 4-file deliverable per project (analysis.html, slides.pdf, methodology.pdf, config.json).
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
