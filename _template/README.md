# [Project Title]

[1–2 sentence project summary.]

## Files (the Renball Research Standard — see CLAUDE.md §4)

- `analysis.html` — Editorial story: findings, "Who should care" takeaways, limitations, embedded slide viewer.
- `dashboard.html` — Interactive Tabulator explorer (only where the data supports it).
- `methodology.md` → `methodology.html` + `methodology.pdf` — Technical write-up (`code/build_pdfs.py`).
- `slides.pptx` → `slides.pdf` — Deck built by `code/build_slides.py`, exported via PowerPoint.
- `data/data.json` — Every number the page, slides, methodology and X copy use (written by `code/build.py`).
- `config.json` — Card metadata (mirrored in repo-root `projects.json`).
- `social/` — X package (gitignored drafts): thread, standalone posts, images, alt text, posting guide, preview.
- `code/verify.py` — Fails if any printed number doesn't trace to `data.json` or a deliverable is missing.

## Build order

```bash
python code/build.py          # raw data -> data/data.json (incl. takeaways)
python code/build_slides.py   # -> slides.pptx
python code/build_pdfs.py     # -> methodology.html/.pdf + slides.pdf
python code/build_social.py   # -> social/images + preview.html (validates the X package)
python code/verify.py         # numbers + standard check — must pass before commit
```

Use the repo venv (`.venv/Scripts/python.exe`). Raw data comes from the local `READY_DATA` /
`MATCH_DATA` folders via `RENBALL_DATA_PATH` / `RENBALL_MATCH_DATA_PATH`.

## Live on

[renball.com/projects/XX-project-name/analysis.html](https://renball.com/projects/XX-project-name/analysis.html)
