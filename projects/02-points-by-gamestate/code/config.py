"""
Points by Gamestate (v3) — Configuration & Constants
Adds time-bin dimension to the value model.
"""
import os

# ── Paths ──────────────────────────────────────────────────────────────
# Paths come from env vars (Renball convention — see CLAUDE.md §9).
# Defaults match CK's local layout; never hardcode user-specific paths in committed code.
DATA_DIR = os.environ.get(
    "RENBALL_MATCH_DATA_PATH",
    r"C:\Users\Can Luca Köymen\OneDrive\Desktop\MONEYBALLYTICS\DATA\MATCH_DATA",
)
# OUTPUT_DIR defaults to the project folder (parent of code/), so build artefacts
# land under projects/02-points-by-gamestate/ next to data.json / dashboard.html.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get(
    "RENBALL_OUTPUT_DIR",
    os.path.dirname(_SCRIPT_DIR),  # → projects/02-points-by-gamestate/
)

# ── Gamestate range ────────────────────────────────────────────────────
MIN_GD = -7
MAX_GD = 7

KEEP_PAIRS = [(gd, gd + 1) for gd in range(MIN_GD, MAX_GD + 1)]
KEEP_SET = set(KEEP_PAIRS)
ORDER_MAP = {pair: i for i, pair in enumerate(KEEP_PAIRS)}

# ── Time bins ──────────────────────────────────────────────────────────
TIME_BINS = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
BIN_UNKNOWN = "unknown"

# ── CDN URLs for standalone HTML dashboard ─────────────────────────────
TABULATOR_CSS = "https://unpkg.com/tabulator-tables@6.2.5/dist/css/tabulator.min.css"
TABULATOR_JS = "https://unpkg.com/tabulator-tables@6.2.5/dist/js/tabulator.min.js"
XLSX_JS = "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"

# ── Branding ───────────────────────────────────────────────────────────
ANALYST_NAME = "Can-Luca Köymen"
BRAND_URL = "https://www.renball.com"
BRAND_NAME = "www.renball.com"
