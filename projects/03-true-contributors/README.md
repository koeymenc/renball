# The True Contributors: Who Actually Moves the Table?

Applies project 02's expected-points (EP) value model to discover and rank
players whose true contribution diverges from their box-score reputation.
Scorer, assist-creator (SCA1) and pre-assist-creator (SCA2) all credited.

## Files

- `analysis.html` — Editorial dashboard (live on website).
- `dashboard.html` — Full Tabulator drill-down across all 7 ranking datasets (lazy-loaded from `data/dashboard/`).
- `slides.pdf` — Presentation slideshow.
- `methodology.html` — Technical write-up, styled in Renball design tokens (generated from `methodology.md`).
- `code/build.py` — Orchestrator. Runs project 02's pipeline + this project's enrichments.
- `code/enrich.py` — Player metadata loaders, SCA2 + three-layer merge, Q1...Q7 rankings.
- `data/data.json` — Editorial payload consumed by `analysis.html`.
- `data/dashboard/manifest.json` + `data/dashboard/<dataset>/<view>.json` — Per-view JSONs for the full dashboard.
- `data/static/actual_mvps.json` — **Manually curated** lookup of real-world POTY winners (annotations on Q2 grid).
- `config.json` — Card metadata (mirrored in repo-root `projects.json`).

## Rebuilding the data

```bash
python code/build.py
```

Requires:
- `RENBALL_MATCH_DATA_PATH` -> per-league match-event pickles (project 02's source).
- `RENBALL_DATA_PATH` -> `READY_DATA/` folder with `FULL_DICT_ROWS.pkl` (for minutes / position / age enrichment).

Defaults match CK's local layout (see `code/build.py`); never hardcode user-specific paths.

## Scope caveat

The seven research questions span six leagues (Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie) and all available seasons. **Per-90 calculations** (Q1a, Q1b, Q2, Q5, Q6 per-90, Q7) are **Top-5 only** because `FULL_DICT_ROWS.pkl` doesn't cover Eredivisie minutes. Absolute-EP boards (Q3, Q4, Q6 absolute) include all six leagues. Every dashboard view carries `scope` + `scope_note` metadata to make this explicit.

## Live on

[renball.com/projects/03-true-contributors/analysis.html](https://renball.com/projects/03-true-contributors/analysis.html)
