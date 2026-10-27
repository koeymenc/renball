# Renball · Football Data Research

Source of [renball.com](https://renball.com): football analytics research by Can Luca Köymen. Every project ships an editorial page, a methodology (HTML and PDF), a slide deck and, where the data supports it, an interactive dashboard. Every number on a page traces back to the project's `data/data.json`.

## Projects

| # | Project | Question |
|---|---|---|
| 01 | [Should the Fouled Player Take the Penalty Himself?](https://renball.com/projects/01-penalty-analysis/analysis.html) | Does a player fouled by the keeper convert his own penalty less often? |
| 02 | [Not All Goals Are Equal](https://renball.com/projects/02-points-by-gamestate/analysis.html) | What is a goal worth, given the score it changes and the minute it comes? |
| 03 | [The True Contributors](https://renball.com/projects/03-true-contributors/analysis.html) | Who adds the most expected points per 90, and how sure can a ranking be? |

## Layout

```
renball/
├── index.html          homepage; cards are built from projects.json
├── projects.json       one entry per project (identical to each project's config.json)
├── assets/             shared design tokens, chart defaults, slide master, PDF and QA tooling
└── projects/NN-slug/
    ├── analysis.html   editorial page (reads data/data.json)
    ├── dashboard.html  Tabulator explorer (reads data/dashboard/), where there is one
    ├── methodology.md  → methodology.html / methodology.pdf
    ├── slides.pptx     → slides.pdf
    ├── config.json
    ├── code/           build.py (raw data → data.json), build_slides.py, build_pdfs.py, verify.py
    └── data/
```

## Rebuilding a project

```bash
python projects/NN-slug/code/build.py         # needs the raw FBref pickles (not in this repo)
python projects/NN-slug/code/build_slides.py
python projects/NN-slug/code/build_pdfs.py    # PowerPoint (slides) and headless Chrome (methodology)
python projects/NN-slug/code/verify.py        # every printed number traces to data.json
```

Python 3.12 with `requirements.txt`. Raw data paths come from `RENBALL_MATCH_DATA_PATH` and `RENBALL_DATA_PATH`; raw data is never committed.

## Hosting

GitHub Pages with the custom domain `renball.com`.
