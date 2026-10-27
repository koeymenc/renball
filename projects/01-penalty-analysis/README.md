# Should the Fouled Player Take the Penalty Himself?

Every penalty in the top 5 leagues from 2017-18 to 2023-24 linked to its own
taker, fouled player and conceding player. When the goalkeeper fouled the
taker and the taker took the kick himself, does conversion drop? A one-tailed
two-proportion test with intervals, power and an equivalence test, a logistic
regression with the taker's status, record and experience, a Bayesian check,
and two side findings on penalty takers (the established taker's edge and the
split-half repeatability of conversion).

## Files

- `analysis.html` — editorial page (live on the website).
- `methodology.md` → `methodology.html` / `methodology.pdf` — full method and results.
- `slides.pptx` → `slides.pdf` — the deck.
- `code/build.py` — reads `FULL_DICT_ROWS.pkl`, links penalties, runs the tests and writes `data/data.json` (bootstrap results cached in `data/.cache/`, keyed on a hash of their inputs).
- `code/build_slides.py`, `code/build_pdfs.py`, `code/build_social.py`, `code/verify.py` — deck, PDFs, X images + validation, numbers check.
- `config.json` — card metadata (mirrored in repo-root `projects.json`).

## Rebuilding

```bash
python code/build.py
python code/build_slides.py
python code/build_pdfs.py
python code/build_social.py
python code/verify.py
```

Requires `FULL_DICT_ROWS.pkl` in the local `READY_DATA` folder; override the path with `RENBALL_DATA_PATH`.

## Live on

[renball.com/projects/01-penalty-analysis/analysis.html](https://renball.com/projects/01-penalty-analysis/analysis.html)
