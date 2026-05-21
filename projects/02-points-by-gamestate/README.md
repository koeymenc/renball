# Not All Goals Are Equal — Points by Gamestate

A time-aware expected-points (EP) framework that prices every goal by both the goal-difference transition it produced and the minute it landed. 39,381 goals · six top-flight leagues · seven seasons.

## Files

- `analysis.html` — Editorial write-up: 4 stat callouts, state value table, EP heatmap, early-vs-late opener, total EP by minute bin, top-10 EP collectors, top-10 timed upgrades + Mário Rui spotlight, top-10 EP per 90, top-10 EP-by-bin distribution.
- `dashboard.html` — Full interactive Tabulator dashboard with lazy-loaded per-(dataset, view) JSON files (six datasets × up to four views; manifest at `data/dashboard/manifest.json`).
- `methodology.html` — Technical write-up styled in Renball tokens (generated from `methodology.md` by `code/build_pdfs.py`).
- `slides.pptx` / `slides.pdf` — Renball-branded 13-slide deck (built by `code/build_slides.py` against `assets/slides/renball_slide_master.py`).
- `config.json` — Card metadata (mirrored in repo-root `projects.json`).

## Source code (`code/`)

- `config.py`, `extraction.py`, `analysis.py`, `dashboard.py`, `main.py` — v3 Points-by-Gamestate analysis pipeline (per-league + pooled, untimed + timed).
- `build.py` — Renball orchestrator. Loads pickles, runs the pipeline, joins player minutes, emits `data/data.json` + `data/dashboard/` tree.
- `build_pdfs.py` — `methodology.md` → `methodology.html`.
- `build_slides.py` — `data/data.json` → `slides.pptx` (uses the shared `assets/slides/renball_slide_master.py`).

## Rebuilding

```bash
python code/build.py        # data
python code/build_pdfs.py   # methodology.html
python code/build_slides.py # slides.pptx
```

Requires:
- `RENBALL_MATCH_DATA_PATH` → folder containing `match_data_final_<league>.pkl` files (defaults to CK's local path).
- `RENBALL_DATA_PATH` → folder containing `FULL_DICT_ROWS.pkl` for player-minutes lookup (Top-5 leagues only).

## Live on

[renball.com/projects/02-points-by-gamestate/](https://renball.com/projects/02-points-by-gamestate/)
