# The True Contributors: Who Actually Moves the Table?

Every goal in the top 5 leagues from 2017-18 to 2023-24 priced by the expected
points it added (Project 02's team-minute model, unchanged) and credited to
the scorer, SCA1 and SCA2, once per player per goal. EP per 90 is pulled
toward each position's average by empirical Bayes; every rank carries a
plausible range.

## Files

- `analysis.html` — editorial page (live on the website).
- `dashboard.html` — Tabulator drill-down: players, player-seasons, award check, SCA2 board, decisive goals (lazy-loaded from `data/dashboard/`).
- `methodology.md` → `methodology.html` / `methodology.pdf` — full method and results.
- `slides.pptx` → `slides.pdf` — the deck.
- `code/build.py` — orchestrator: Project 02's extraction and value model → credits → boards → `data/data.json` + dashboard files.
- `code/players.py` — identity (name + birth date), credit tables, positions, bootstrap of player rates.
- `code/shrink.py` — empirical Bayes rates, rank intervals, repeatability.
- `code/build_slides.py`, `code/build_pdfs.py`, `code/build_social.py`, `code/verify.py` — deck, PDFs, X images + validation, numbers check.
- `data/static/actual_mvps.json` — actual player-of-the-season winners per league and season, each with its source URL.

## Rebuilding

```bash
python code/build.py        # ~3 min warm (Project 02's extraction cache), bootstrap cached in data/.cache/
python code/build_slides.py
python code/build_pdfs.py
python code/build_social.py
python code/verify.py
```

Requires `RENBALL_MATCH_DATA_PATH` (per-league match pickles, Project 02's source). The build stops if the goal prices it recomputes differ from Project 02's published `data.json`.

## Scope

Top 5 leagues only (the Eredivisie, used by Project 02's value model, is left out of the boards so every player is compared within the leagues the award check covers). The data end in 2023-24: the SCA2 data end there because the source discontinued them.

## Live on

[renball.com/projects/03-true-contributors/analysis.html](https://renball.com/projects/03-true-contributors/analysis.html)
