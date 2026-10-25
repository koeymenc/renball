"""
dashboard_files.py — write the Tabulator payload as a manifest + one JSON per (dataset, view)
===========================================================================================

Every file is compact JSON, floats rounded to 3 dp, sparse-encoded (numeric
zeros dropped except SPARSE_KEEP_KEYS) and, for contributor tables, with
short keys (cnt_X_to_Y -> g.X.Y, cnt_bin_X -> b.X, ep_bin_X -> e.X). The
manifest carries the key scheme, the column and dataset help, and each
file's size; dashboard.html fetches the manifest and lazy-loads each view.
"""
from __future__ import annotations

import json
from pathlib import Path

DATASET_DIRS = {
    "Goals+Assists": "goals_assists",
    "Goalscorer":    "goalscorer",
    "Assist":        "assist",
    "State values":  "state_values",
    "Goal values":   "goal_values",
}
CONTRIB_DATASETS = {"Goalscorer", "Assist", "Goals+Assists"}

# Never dropped by sparse encoding: identifiers and columns where 0 is a real value.
SPARSE_KEEP_KEYS = {
    "scoring_team", "contributor", "minute_bin", "gd", "gd_before", "gd_after",
    "goals_involved", "exp_points_collected_timed", "exp_points_collected_untimed",
    "exp_points_collected", "exp_points", "pW", "pD", "pL", "goals", "team_minutes", "matches",
    "ci_lo", "ci_hi", "sparse", "minutes_played", "ep_per_90",
}
# Pure functions of base columns; dashboard.html recomputes them.
DERIVED_DROP = {"delta_ep_timed_vs_untimed", "delta_ep_minus_goals", "ratio_ep_per_goal"}
KEY_SCHEME = {"cnt_gd_prefix": "g.", "cnt_bin_prefix": "b.", "ep_bin_prefix": "e."}


def _slug(s: str) -> str:
    out, prev = [], False
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
            prev = False
        elif not prev:
            out.append("_")
            prev = True
    return "".join(out).strip("_")


def _shorten_key(k: str) -> str:
    if k.startswith("cnt_bin_"):
        return KEY_SCHEME["cnt_bin_prefix"] + k[len("cnt_bin_"):]
    if k.startswith("ep_bin_"):
        return KEY_SCHEME["ep_bin_prefix"] + k[len("ep_bin_"):]
    if k.startswith("cnt_") and "_to_" in k:
        before, after = k[len("cnt_"):].split("_to_")
        return KEY_SCHEME["cnt_gd_prefix"] + f"{before}.{after}"
    return k


def _round(obj, nd: int = 3):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, nd) for v in obj]
    return obj


def _sparse_row(row: dict, contributor: bool) -> dict:
    out = {}
    for k, v in row.items():
        if contributor and k in DERIVED_DROP:
            continue
        if k in SPARSE_KEEP_KEYS:
            out[k] = v
        elif v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0):
            continue
        else:
            out[_shorten_key(k) if contributor else k] = v
    return out


def _sparse(view, contributor: bool):
    if isinstance(view, list):
        return [_sparse_row(r, contributor) for r in view]
    if isinstance(view, dict):
        return {k: _sparse(v, contributor) for k, v in view.items()}
    return view


def write(payload: dict, out_dir: Path) -> list[tuple[str, float]]:
    """Write manifest + view files; returns [(dataset / view, MB)] for any file over 5 MB."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.rglob("*.json"):
        stale.unlink()
    for d in sorted((p for p in out_dir.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    manifest = {
        "meta": payload.get("meta", {}),
        "columnHelp": payload.get("columnHelp", {}),
        "datasetHelp": payload.get("datasetHelp", {}),
        "always_keep": sorted(SPARSE_KEEP_KEYS),
        "derived_columns": sorted(DERIVED_DROP),
        "key_scheme": KEY_SCHEME,
        "datasets": {},
    }
    oversize = []
    for ds, slug in DATASET_DIRS.items():
        if ds not in payload["datasets"]:
            continue
        contrib = ds in CONTRIB_DATASETS
        views = {}
        for view, container in payload["datasets"][ds].items():
            rel = f"{slug}/{_slug(view)}.json"
            path = out_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_round(_sparse(container, contrib)), ensure_ascii=False,
                                       separators=(",", ":")), encoding="utf-8")
            kb = round(path.stat().st_size / 1024, 1)
            views[view] = {"file": rel, "size_kb": kb}
            if kb > 5 * 1024:
                oversize.append((f"{ds} / {view}", kb / 1024))
        manifest["datasets"][ds] = {"contributor": contrib, "views": views}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return oversize
