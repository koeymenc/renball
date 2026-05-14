# 01 — The GK's Self-Inflicted Penalty

Two-proportion z-tests across the top 5 European leagues asking: does the goalkeeper's own foul affect penalty conversion, and does the taker who won the penalty convert at a different rate?

## Files

- `analysis.html` — Interactive Chart.js dashboard.
- `slides.pdf` — Presentation slideshow (built from `slides.pptx`, added separately).
- `methodology.html` — Technical write-up, styled in Renball design tokens (built from `methodology.md` via `code/build_pdfs.py`).
- `code/build.py` — Reads `FULL_DICT_ROWS.pkl` from `READY_DATA`, runs the analysis, writes `data/data.json`.
- `data/data.json` — Aggregated chart data consumed by the dashboard.
- `config.json` — Card metadata (mirrored in repo-root `projects.json`).

## Rebuilding the data

```powershell
python code/build.py
```

Requires `FULL_DICT_ROWS.pkl` in the local `READY_DATA` folder. Override the path with the `RENBALL_DATA_PATH` env var if needed.

## Live on

[renball.com/projects/01-penalty-analysis/analysis.html](https://renball.com/projects/01-penalty-analysis/analysis.html)
