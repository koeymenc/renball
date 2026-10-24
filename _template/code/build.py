"""
build.py — Renball project build script
─────────────────────────────────────────

Reads raw analysis data (pickles, CSVs) from the local READY_DATA folder,
runs the project-specific analysis, and writes a single aggregated
`data.json` file consumed by analysis.html.

Convention:
- Raw data path comes from env var RENBALL_DATA_PATH (default below).
- Output is always written to: <project_folder>/data/data.json
- This file must NEVER hardcode user-specific paths in committed code.

Usage:
    python code/build.py

"""

import json
import os
import pickle
from pathlib import Path

# ── Config ─────────────────────────────────────────────────
DEFAULT_DATA_PATH = r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\READY_DATA"
DATA_PATH = Path(os.environ.get("RENBALL_DATA_PATH", DEFAULT_DATA_PATH))

# Output: project_folder/data/data.json (relative to this script)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_DIR / "data" / "data.json"


# ── Helpers ────────────────────────────────────────────────
def load_pickle(name: str):
    """Load a pickle from READY_DATA."""
    path = DATA_PATH / f"{name}.pkl"
    with open(path, "rb") as f:
        return pickle.load(f)


def write_data(payload: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"✓ Wrote {OUTPUT_PATH.relative_to(PROJECT_DIR)} ({size_kb:.1f} KB)")


# ── Main analysis ─────────────────────────────────────────
def main() -> None:
    """
    Replace this with the project's actual analysis pipeline.

    Required output structure for analysis.html:
        {
            "stat1": "...",            # top stat callouts
            "stat2": "...",
            "stat3": "...",
            "chart1": {
                "labels": [...],
                "values": [...],
            },
            "chart2": {
                "labels": [...],
                "seriesA": [...],
                "seriesB": [...],
            },
            # ...add more chart blocks as needed
        }
    """

    # Example skeleton — replace with real analysis
    payload = {
        "generated_at": None,  # build.py can fill with datetime.now().isoformat()
        "stat1": "—",
        "stat2": "—",
        "stat3": "—",
        "chart1": {"labels": [], "values": []},
        "chart2": {"labels": [], "seriesA": [], "seriesB": []},
    }

    # Who should care — rendered on the page (renball-components.js), on a
    # slide (add_takeaways_slide) and quoted in the X thread. Compose the text
    # here from computed values (f-strings) so every number traces to this
    # file; code/verify.py fails on any hand-typed figure. Evidence labels:
    # strong | moderate | exploratory (definitions: CLAUDE.md §4.3). Keep each
    # text <= 140 chars, <= 2 per audience; [] means "no defensible claim".
    payload["takeaways"] = {
        "intro": "[One line: who this helps and how confident we are.]",
        "coaches":  [{"text": "[Training / tactics takeaway]", "evidence": "moderate",
                      "basis": "[n = … · 95% CI …]"}],
        "managers": [{"text": "[Match-day decision takeaway]", "evidence": "exploratory",
                      "basis": "[…]"}],
        "clubs":    [],
        "agents":   [],
    }

    write_data(payload)


if __name__ == "__main__":
    main()
