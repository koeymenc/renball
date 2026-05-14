# Renball — Football Data Research

Personal portfolio site for football analytics research projects.

## Folder Structure

```
renball/
├── index.html              ← Homepage (auto-reads projects.json)
├── projects.json           ← ★ THE ONLY FILE YOU EDIT TO ADD PROJECTS
├── projects/
│   ├── 01-pressing/
│   │   ├── config.json     ← Project metadata (same as projects.json entry)
│   │   ├── analysis.html   ← Interactive data analysis
│   │   └── slides.pdf      ← Presentation / slideshow
│   ├── 02-xg-model/
│   │   ├── config.json
│   │   ├── analysis.html
│   │   └── slides.pdf
│   └── ...
├── assets/
│   └── images/
└── README.md
```

## How to Add a New Project

### Step 1 — Create the project folder
```
projects/03-my-new-project/
├── analysis.html    (optional — your interactive research)
└── slides.pdf       (optional — your presentation)
```

### Step 2 — Add entry to projects.json
Open `projects.json` and add a new object to the array:
```json
{
  "folder": "03-my-new-project",
  "title": "My New Research Title",
  "date": "Mar 2026",
  "type": "HTML + PDF",
  "tags": ["EPL", "xG", "Pressing"],
  "filter": ["tactical", "xg"],
  "excerpt": "One or two sentences describing the research.",
  "finding": "The key result or headline number.",
  "has_html": true,
  "has_pdf": true
}
```

### Step 3 — Push to GitHub
```bash
git add .
git commit -m "Add project: My New Research Title"
git push
```
Site updates in ~1 minute.

## Fields Explained

| Field | Required | Description |
|-------|----------|-------------|
| `folder` | Yes | Folder name inside `projects/` |
| `title` | Yes | Display title on the card |
| `date` | Yes | e.g. "Mar 2026" |
| `type` | Yes | e.g. "HTML", "PDF", "HTML + PDF" |
| `tags` | Yes | Shown on the card (display labels) |
| `filter` | Yes | Used for filter buttons (lowercase) |
| `excerpt` | Yes | 1-2 sentence description |
| `finding` | No | Key result (green highlight box) |
| `has_html` | No | Set true if analysis.html exists |
| `has_pdf` | No | Set true if slides.pdf exists |

## Hosting

Hosted on GitHub Pages with custom domain `renball.com`.
