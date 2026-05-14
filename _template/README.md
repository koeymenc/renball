# [Project Title]

[1–2 sentence project summary.]

## Files

- `analysis.html` — Interactive dashboard (live on website).
- `slides.pdf` — Presentation slideshow.
- `methodology.html` — Technical write-up, styled in Renball design tokens (generated from `methodology.md`).
- `code/build.py` — Python script that processes raw data into `data/data.json`.
- `data/data.json` — Pre-aggregated chart data consumed by the dashboard.
- `config.json` — Card metadata (mirrored in repo-root `projects.json`).
- `slides.pptx` / `methodology.md` — Editable sources for the PDFs.

## Rebuilding the data

```bash
python code/build.py
```

Requires raw data in the local `READY_DATA` folder (path set via `RENBALL_DATA_PATH` env var; defaults to CK's local path).

## Live on

[renball.com/projects/XX-project-name/analysis.html](https://renball.com/projects/XX-project-name/analysis.html)
