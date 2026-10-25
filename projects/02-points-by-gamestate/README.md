# Not All Goals Are Equal — Points by Gamestate

A time-aware expected-points (EP) model that prices every goal by the scoreline it changes and the minute it lands, estimated from every team-minute of the model sample — six top-flight leagues, seven seasons. Intervals from a match bootstrap, a held-out test on the last two seasons, and player boards with intervals.

## Files

- `analysis.html` — editorial page: state values, goal values, the opener by window, game state (upside vs downside of the next goal), EP by window, held-out calibration, robustness, player boards (EP collected, timing premium, EP per 90) with intervals, takeaways, limitations, the deck.
- `dashboard.html` — Tabulator dashboard reading `data/dashboard/manifest.json` + one lazy-loaded JSON per (dataset, view): Goals+Assists, Goalscorer, Assist, State values, Goal values.
- `methodology.md` → `methodology.html` / `methodology.pdf` — full method and results.
- `slides.pptx` / `slides.pdf` — the deck (shared slide master).
- `data/data.json` — every number the page, deck and X package show.
- `data/og_affected_matches.csv` — matches whose shot table is missing goals (own goals), for a later backfill.
- `config.json` — card metadata (mirrored in repo-root `projects.json`).

## Code (`code/`)

- `matches.py` — one pass over the match pickles: official scores, goals, per-match player minutes and birth dates; cached per league under `data/.cache/` (gitignored).
- `value_model.py` — team-minute counts, state and goal values, bootstrap weights, Brier scores.
- `build.py` — everything else: data quality, bootstrap, calibration, player boards, robustness, takeaways, dashboard payload.
- `dashboard_files.py` — writes the dashboard manifest + view files.
- `build_slides.py`, `build_pdfs.py`, `build_social.py`, `verify.py` — deck, PDFs, X package, numbers + standard check.
- `config.py`, `extraction.py`, `analysis.py` — shared helpers (also used by Project 03); `main.py`, `dashboard.py` — the original v3 pipeline.

## Rebuilding

```bash
python code/build.py          # data (first run reads the pickles, ~25 min; cached afterwards, ~3 min)
python code/build_slides.py   # slides.pptx
python code/build_pdfs.py     # methodology.html/.pdf + slides.pdf
python code/build_social.py   # X package images + preview (social/ stays local)
python code/verify.py         # must print VERIFY PASSED
```

Requires `RENBALL_MATCH_DATA_PATH` → folder with `match_data_final_<league>.pkl` (defaults to CK's local path).

## Live on

[renball.com/projects/02-points-by-gamestate/analysis.html](https://renball.com/projects/02-points-by-gamestate/analysis.html)
