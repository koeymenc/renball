"""
Points by Gamestate (v3) — HTML Dashboard Builder
Extends v2 with timed transition datasets + transition heatmap view.
"""
import os
import json

import numpy as np
import pandas as pd
from urllib.request import urlopen

from config import TABULATOR_CSS, TABULATOR_JS, XLSX_JS, ANALYST_NAME, BRAND_URL, BRAND_NAME


# ═══════════════════════════════════════════════════════════════════════
#  DataFrame → JSON helpers
# ═══════════════════════════════════════════════════════════════════════

def _to_py(v):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        x = float(v)
        return None if np.isnan(x) else x
    if isinstance(v, float):
        return None if np.isnan(v) else v
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def df_to_records(df: pd.DataFrame) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    dfx = df.copy()
    dfx.columns = [str(c) for c in dfx.columns]
    return [{k: _to_py(v) for k, v in row.items()} for row in dfx.to_dict(orient="records")]


def dict_of_df_to_records(d: dict) -> dict:
    return {str(k): df_to_records(v) for k, v in d.items()
            if isinstance(v, pd.DataFrame) and not v.empty}


def nested_dict_df_to_records(d: dict) -> dict:
    out = {}
    for league, seasons in d.items():
        if not isinstance(seasons, dict):
            continue
        inner = {}
        for season, df in seasons.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                inner[str(season)] = df_to_records(df)
        if inner:
            out[str(league)] = inner
    return out


# ═══════════════════════════════════════════════════════════════════════
#  Column help
# ═══════════════════════════════════════════════════════════════════════

COLUMN_HELP = {
    "scoring_team": "Team that scored the goal.",
    "contributor": "Player credited (Goalscorer / Assist / Goals+Assists depending on dataset).",
    "goals_involved": "Count of credited events.",
    "exp_points_collected_timed": "Sum of EP increments using time-aware values (accounts for when in the match the goal was scored).",
    "exp_points_collected_untimed": "Sum of EP increments using time-agnostic values (v2 methodology).",
    "delta_ep_timed_vs_untimed": "Difference: timed EP minus untimed EP. Positive = player scores in more valuable minutes.",
    "delta_ep_minus_goals": "Timed EP collected minus goals involved.",
    "ratio_ep_per_goal": "Timed EP collected divided by goals involved.",
    "gd_before": "Goal difference for the scoring team before the goal.",
    "gd_after": "Goal difference for the scoring team after the goal.",
    "minute_bin": "15-minute time bin when the goal occurred.",
    "n": "Number of observed goal events.",
    "pW": "Probability the scoring team ultimately wins.",
    "pD": "Probability of draw.",
    "pL": "Probability the scoring team ultimately loses.",
    "exp_points": "Expected final points (3·pW + 1·pD).",
    "exp_points_collected": "Incremental EP for this transition.",
    "delta_exp_points": "EP delta from state value function (Approach A).",
    "minutes_played": "Total minutes played in scope (Top-5 leagues only; Eredivisie players show 0).",
    "ep_per_90": "Time-aware EP collected normalised per 90 minutes played. 0 when minutes_played is unavailable.",
}


# ═══════════════════════════════════════════════════════════════════════
#  Payload builder
# ═══════════════════════════════════════════════════════════════════════

def build_payload(
    scorer_tables, sca1_tables, ga_tables,
    scorer_totals, sca1_totals, ga_totals,
    transitions_pooled, transitions_by_league,
    transitions_pooled_timed, transitions_by_league_timed,
    heatmap_pooled, heatmap_by_league,
    created_at: str,
) -> dict:
    scorer_by_lg, scorer_by_ss, scorer_all = scorer_totals
    sca1_by_lg, sca1_by_ss, sca1_all = sca1_totals
    ga_by_lg, ga_by_ss, ga_all = ga_totals

    return {
        "meta": {"created_at": created_at},
        "columnHelp": COLUMN_HELP,
        "datasets": {
            "Goalscorer": {
                "Per League & Season": nested_dict_df_to_records(scorer_tables),
                "Totals by League": dict_of_df_to_records(scorer_by_lg),
                "Totals by Season": dict_of_df_to_records(scorer_by_ss),
                "All": {"All": df_to_records(scorer_all)},
            },
            "Assist": {
                "Per League & Season": nested_dict_df_to_records(sca1_tables),
                "Totals by League": dict_of_df_to_records(sca1_by_lg),
                "Totals by Season": dict_of_df_to_records(sca1_by_ss),
                "All": {"All": df_to_records(sca1_all)},
            },
            "Goals+Assists": {
                "Per League & Season": nested_dict_df_to_records(ga_tables),
                "Totals by League": dict_of_df_to_records(ga_by_lg),
                "Totals by Season": dict_of_df_to_records(ga_by_ss),
                "All": {"All": df_to_records(ga_all)},
            },
            "Transitions": {
                "Pooled": {"Pooled": df_to_records(transitions_pooled)},
                "By League": {lg: df_to_records(df) for lg, df in transitions_by_league.items()},
            },
            "Transitions (Timed)": {
                "Pooled": {"Pooled": df_to_records(transitions_pooled_timed)},
                "By League": {lg: df_to_records(df) for lg, df in transitions_by_league_timed.items()},
            },
            "Transition Heatmap": {
                "Pooled": {"Pooled": df_to_records(heatmap_pooled)},
                "By League": {lg: df_to_records(df) for lg, df in heatmap_by_league.items()},
            },
        },
    }


# ═══════════════════════════════════════════════════════════════════════
#  HTML template + writer
# ═══════════════════════════════════════════════════════════════════════

def _fetch_text(url: str) -> str:
    with urlopen(url) as r:
        return r.read().decode("utf-8")


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Points by Gamestate Dashboard (v3 — Time Bins)</title>
  __CSS_BLOCK__
  <style>
    :root {
      --bg:        #f5f6f8;
      --surface:   #ffffff;
      --border:    #e0e2e6;
      --text:      #1a1c20;
      --text-muted:#6b7280;
      --accent:    #2563eb;
      --accent-bg: #eff4ff;
      --header-bg: #111827;
      --header-fg: #f9fafb;
      --radius:    8px;
      --shadow:    0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04);
      --green:     #16a34a;
      --red:       #dc2626;
    }

    *, *::before, *::after { box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }

    .header {
      padding: 18px 24px;
      background: var(--header-bg);
      color: var(--header-fg);
    }
    .header .title {
      font-size: 20px; font-weight: 700; letter-spacing: -.3px;
    }
    .header .subtitle {
      font-size: 12px; color: #9ca3af; margin-top: 2px;
    }
    .header .badge {
      display: inline-block;
      background: var(--accent);
      color: #fff;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 10px;
      margin-left: 8px;
      vertical-align: middle;
    }
    .header a { color: #93c5fd; text-decoration: none; }
    .header a:hover { text-decoration: underline; }

    .toolbar {
      padding: 14px 24px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
      box-shadow: var(--shadow);
    }
    .toolbar .group { display: flex; gap: 6px; align-items: center; }
    .toolbar label.lbl {
      font-size: 11px; font-weight: 600; text-transform: uppercase;
      letter-spacing: .5px; color: var(--text-muted);
    }

    select, input[type="text"] {
      padding: 7px 10px; border: 1px solid var(--border);
      border-radius: var(--radius); font-size: 13px;
      background: var(--surface); min-width: 190px;
      transition: border-color .15s;
    }
    select:focus, input[type="text"]:focus {
      outline: none; border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-bg);
    }

    .btn {
      padding: 7px 14px; border: 1px solid var(--border);
      border-radius: var(--radius); font-size: 13px; font-weight: 500;
      background: var(--surface); cursor: pointer; transition: all .15s;
    }
    .btn:hover { background: var(--bg); border-color: #c0c4cc; }
    .btn-accent { background: var(--accent); color: #fff; border-color: var(--accent); }
    .btn-accent:hover { background: #1d4ed8; }

    .chk {
      display: flex; align-items: center; gap: 5px;
      font-size: 12px; color: var(--text-muted);
    }
    .chk input[type="checkbox"] { accent-color: var(--accent); }

    .meta-bar {
      padding: 6px 24px; font-size: 11px;
      color: var(--text-muted); background: var(--surface);
      border-bottom: 1px solid var(--border);
    }

    .content { padding: 20px 24px; }
    #table-title {
      font-size: 15px; font-weight: 700; margin: 0 0 12px; color: var(--text);
    }
    #table {
      border: 1px solid var(--border); border-radius: var(--radius);
      overflow: hidden; box-shadow: var(--shadow); background: var(--surface);
    }
    .tips { margin-top: 12px; font-size: 12px; color: var(--text-muted); }
    .tips b { color: var(--text); }

    .tabulator { border: none !important; font-size: 13px; }
    .tabulator .tabulator-header {
      background: #f8f9fb; border-bottom: 2px solid var(--border);
    }
    .tabulator .tabulator-header .tabulator-col {
      background: #f8f9fb; border-right: 1px solid var(--border);
    }
    .tabulator .tabulator-header .tabulator-col .tabulator-col-title {
      font-weight: 600; font-size: 12px;
    }
    .tabulator-row.tabulator-row-even { background: #fafbfc; }
    .tabulator .tabulator-footer { background: #f8f9fb; }
  </style>
</head>
<body>

  <div class="header">
    <div class="title">
      Points by Gamestate Dashboard
      <span class="badge">v3 — Time Bins</span>
    </div>
    <div class="subtitle">
      Produced by <a href="__BRAND_URL__" target="_blank" rel="noopener">__BRAND_NAME__</a>
      &mdash; get in touch (Analyst: __ANALYST_NAME__)
    </div>
  </div>

  <div class="toolbar">
    <div class="group">
      <label class="lbl" for="datasetSel">Dataset</label>
      <select id="datasetSel"></select>
    </div>
    <div class="group">
      <label class="lbl" for="viewSel">View</label>
      <select id="viewSel"></select>
    </div>
    <div class="group" id="keyWrap" style="display:none;">
      <label class="lbl" id="keyLabel" for="keySel">League</label>
      <select id="keySel"></select>
    </div>
    <div class="group" id="seasonWrap" style="display:none;">
      <label class="lbl" for="seasonSel">Season</label>
      <select id="seasonSel"></select>
    </div>
    <div class="group">
      <label class="lbl" for="searchBox">Search</label>
      <input id="searchBox" type="text" placeholder="type to filter rows..." />
    </div>
    <div class="chk">
      <input id="showCnt" type="checkbox" checked />
      <label for="showCnt">Show cnt_* columns</label>
    </div>
    <div class="chk">
      <input id="showEpBin" type="checkbox" checked />
      <label for="showEpBin">Show ep_bin_* columns</label>
    </div>
    <button class="btn" id="resetBtn">Reset filters</button>
    <button class="btn btn-accent" id="xlsxBtn">XLSX</button>
    <button class="btn" id="csvBtn">CSV</button>
  </div>

  <div class="meta-bar">Generated: <span id="genAt"></span></div>

  <div class="content">
    <div id="table-title"></div>
    <div id="table"></div>
    <div class="tips">
      Column filters support numeric operators:
      <b>&gt;</b>, <b>&gt;=</b>, <b>&lt;</b>, <b>&lt;=</b>, <b>=</b>, <b>!=</b>.
      Example: type <b>&gt;4</b> or <b>&lt;=0.7</b>.
      Click headers to sort. Hover for explanations.
    </div>
  </div>

  __JS_BLOCK__

  <script>
    const DASH = __PAYLOAD_JSON__;
    document.getElementById("genAt").textContent =
      (DASH.meta && DASH.meta.created_at) || "";

    const datasetSel = document.getElementById("datasetSel");
    const viewSel    = document.getElementById("viewSel");
    const keySel     = document.getElementById("keySel");
    const seasonSel  = document.getElementById("seasonSel");
    const keyWrap    = document.getElementById("keyWrap");
    const seasonWrap = document.getElementById("seasonWrap");
    const keyLabel   = document.getElementById("keyLabel");
    const showCnt    = document.getElementById("showCnt");
    const showEpBin  = document.getElementById("showEpBin");
    const searchBox  = document.getElementById("searchBox");

    let table = null;

    function setOptions(sel, opts, preferred) {
      const prev = sel.value;
      sel.innerHTML = "";
      for (const o of opts) {
        const el = document.createElement("option");
        el.value = o; el.textContent = o;
        sel.appendChild(el);
      }
      const pick =
        (preferred && opts.includes(preferred)) ? preferred :
        (prev && opts.includes(prev)) ? prev :
        (opts.length ? opts[0] : "");
      if (pick) sel.value = pick;
    }

    function isNested(obj) {
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
      const k1 = Object.keys(obj);
      if (!k1.length) return false;
      const v1 = obj[k1[0]];
      if (!v1 || typeof v1 !== "object" || Array.isArray(v1)) return false;
      const k2 = Object.keys(v1);
      return k2.length > 0 && Array.isArray(v1[k2[0]]);
    }
    function isKeyed(obj) {
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
      const k = Object.keys(obj);
      return k.length > 1 && Array.isArray(obj[k[0]]);
    }
    function isSingle(obj) {
      if (!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
      const k = Object.keys(obj);
      return k.length === 1 && Array.isArray(obj[k[0]]);
    }

    function smartFilter(hv, rv) {
      if (hv == null) return true;
      const h = String(hv).trim();
      if (!h) return true;
      const r = (rv == null) ? "" : rv;
      const m = h.match(/^(>=|<=|!=|>|<|=)\s*(-?\d+(?:\.\d+)?)\s*$/);
      if (m) {
        const op = m[1], x = parseFloat(m[2]), y = parseFloat(r);
        if (Number.isNaN(y)) return false;
        if (op === ">")  return y > x;
        if (op === ">=") return y >= x;
        if (op === "<")  return y < x;
        if (op === "<=") return y <= x;
        if (op === "=")  return y === x;
        if (op === "!=") return y !== x;
      }
      return String(r).toLowerCase().includes(h.toLowerCase());
    }

    function colTooltip(col) {
      const h = DASH.columnHelp || {};
      if (h[col]) return h[col];
      let m = /^cnt_(-?\d+)_to_(-?\d+)$/.exec(col);
      if (m) return `Events where scoring team moved from GD ${m[1]} to ${m[2]}.`;
      m = /^cnt_bin_(.+)$/.exec(col);
      if (m) return `Number of goal events in the ${m[1]} minute bin.`;
      m = /^ep_bin_(.+)$/.exec(col);
      if (m) return `Timed EP collected from goals in the ${m[1]} minute bin.`;
      return "";
    }

    /* Color formatter for delta columns */
    function deltaFormatter(cell) {
      const v = cell.getValue();
      if (v == null) return "";
      const num = parseFloat(v);
      if (Number.isNaN(num)) return String(v);
      const formatted = num.toFixed(3);
      if (num > 0.001)  return `<span style="color:var(--green);font-weight:600">+${formatted}</span>`;
      if (num < -0.001) return `<span style="color:var(--red);font-weight:600">${formatted}</span>`;
      return formatted;
    }

    function buildColumns(data) {
      const ds = datasetSel.value;
      const keys = data.length ? Object.keys(data[0]) : [];

      const baseOrder = [
        "scoring_team","contributor","goals_involved",
        "exp_points_collected_timed","exp_points_collected_untimed","delta_ep_timed_vs_untimed",
        "exp_points_collected",
        "gd_before","gd_after","minute_bin","n","pW","pD","pL","exp_points",
        "exp_points_collected","delta_exp_points",
        "delta_ep_minus_goals","ratio_ep_per_goal"
      ];

      const base = baseOrder.filter(k => keys.includes(k));
      const cnt_gd  = keys.filter(k => k.startsWith("cnt_") && !k.startsWith("cnt_bin_")).sort();
      const cnt_bin = keys.filter(k => k.startsWith("cnt_bin_")).sort();
      const ep_bin  = keys.filter(k => k.startsWith("ep_bin_")).sort();
      const rest    = keys.filter(k => !base.includes(k) && !cnt_gd.includes(k) &&
                                        !cnt_bin.includes(k) && !ep_bin.includes(k));

      let final = [...base, ...rest];
      if (showCnt.checked)   final = final.concat(cnt_gd).concat(cnt_bin);
      if (showEpBin.checked) final = final.concat(ep_bin);

      // Transitions: hide last 3 raw columns
      if (ds === "Transitions" && final.length >= 3) {
        final = final.slice(0, final.length - 3);
      }

      // Delta columns get color formatting
      const deltaCols = new Set([
        "delta_ep_timed_vs_untimed", "delta_ep_minus_goals", "delta_exp_points",
        "exp_points_collected"
      ]);

      return final.map(k => {
        const col = {
          title: k,
          field: k,
          headerTooltip: colTooltip(k),
          headerFilter: "input",
          headerFilterFunc: smartFilter,
          headerFilterPlaceholder: "filter...",
        };
        if (deltaCols.has(k)) col.formatter = deltaFormatter;
        return col;
      });
    }

    function setKeyLabel(ds, vw) {
      const v = (vw || "").toLowerCase();
      if (isNested(DASH.datasets[ds][vw]) || v.includes("league"))
        { keyLabel.textContent = "League"; return; }
      if (v.includes("season")) { keyLabel.textContent = "Season"; return; }
      keyLabel.textContent = "Key";
    }

    function updateSelectors() {
      const ds = datasetSel.value, vw = viewSel.value;
      const container = DASH.datasets[ds][vw];
      const prevKey = keySel.value, prevSeason = seasonSel.value;

      keyWrap.style.display = "none";
      seasonWrap.style.display = "none";
      setKeyLabel(ds, vw);

      if (isNested(container)) {
        setOptions(keySel, Object.keys(container).sort(), prevKey);
        keyWrap.style.display = "inline-flex";
        setOptions(seasonSel, Object.keys(container[keySel.value] || {}).sort(), prevSeason);
        seasonWrap.style.display = "inline-flex";
        return;
      }
      if (isKeyed(container)) {
        setOptions(keySel, Object.keys(container).sort(), prevKey);
        keyWrap.style.display = "inline-flex";
        return;
      }
      if (isSingle(container)) return;
      if (container && typeof container === "object" && !Array.isArray(container)) {
        const k = Object.keys(container).sort();
        if (k.length) { setOptions(keySel, k, prevKey); keyWrap.style.display = "inline-flex"; }
      }
    }

    function applySearch() {
      if (!table) return;
      const q = (searchBox.value || "").trim().toLowerCase();
      if (!q) { table.clearFilter(true); return; }
      table.setFilter(row => {
        for (const k in row) {
          const v = row[k];
          if (v != null && String(v).toLowerCase().includes(q)) return true;
        }
        return false;
      });
    }

    function getData() {
      const ds = datasetSel.value, vw = viewSel.value;
      const c = DASH.datasets[ds][vw];
      let data = [], title = `${ds} / ${vw}`;

      if (isNested(c)) {
        const lg = keySel.value, ss = seasonSel.value;
        data = (c[lg] && c[lg][ss]) ? c[lg][ss] : [];
        title += ` / ${lg} / ${ss}`;
      } else if (isKeyed(c)) {
        data = c[keySel.value] || [];
        title += ` / ${keySel.value}`;
      } else if (isSingle(c)) {
        const k = Object.keys(c)[0];
        data = c[k] || [];
        title += ` / ${k}`;
      }
      return { data, title };
    }

    function renderTable() {
      updateSelectors();
      const { data, title } = getData();
      document.getElementById("table-title").textContent =
        `${title}  (${data.length} rows)`;

      if (table) table.destroy();
      table = new Tabulator("#table", {
        data,
        columns: buildColumns(data),
        layout: "fitDataStretch",
        height: "74vh",
        movableColumns: true,
        pagination: true,
        paginationSize: 50,
        paginationSizeSelector: [25, 50, 100, 250, 500],
        downloadRowRange: "active",
      });
      applySearch();
    }

    function init() {
      setOptions(datasetSel, Object.keys(DASH.datasets), datasetSel.value);
      setOptions(viewSel, Object.keys(DASH.datasets[datasetSel.value]), viewSel.value);
      renderTable();
    }

    datasetSel.addEventListener("change", () => {
      setOptions(viewSel, Object.keys(DASH.datasets[datasetSel.value]), viewSel.value);
      renderTable();
    });
    viewSel.addEventListener("change", renderTable);
    keySel.addEventListener("change", () => {
      const ds = datasetSel.value, vw = viewSel.value;
      const c = DASH.datasets[ds][vw];
      if (isNested(c))
        setOptions(seasonSel, Object.keys(c[keySel.value] || {}).sort(), seasonSel.value);
      renderTable();
    });
    seasonSel.addEventListener("change", renderTable);
    showCnt.addEventListener("change", renderTable);
    showEpBin.addEventListener("change", renderTable);
    searchBox.addEventListener("input", applySearch);

    document.getElementById("resetBtn").addEventListener("click", () => {
      searchBox.value = "";
      if (table) { table.clearFilter(true); table.clearHeaderFilter(); table.clearSort(); }
    });

    function cleanName() {
      return (document.getElementById("table-title").textContent || "table")
        .replace(/\s+\(\d+ rows\)$/, "")
        .replace(/\s*\/\s*/g, "_")
        .replace(/[^a-zA-Z0-9_\-]/g, "_")
        .slice(0, 80);
    }

    document.getElementById("xlsxBtn").addEventListener("click", () => {
      if (table) table.download("xlsx", cleanName() + ".xlsx", { sheetName: "data" });
    });
    document.getElementById("csvBtn").addEventListener("click", () => {
      if (table) table.download("csv", cleanName() + ".csv");
    });

    init();
  </script>
</body>
</html>"""


def build_dashboard_html(payload: dict, out_html: str, standalone: bool = True):
    payload_json = json.dumps(payload, ensure_ascii=False)

    if standalone:
        try:
            css_tab = _fetch_text(TABULATOR_CSS)
            js_xlsx = _fetch_text(XLSX_JS)
            js_tab = _fetch_text(TABULATOR_JS)
            css_block = f"<style>\n{css_tab}\n</style>"
            js_block = f"<script>\n{js_xlsx}\n</script>\n<script>\n{js_tab}\n</script>"
        except Exception as e:
            print(f"Standalone embed failed, falling back to CDN: {e!r}")
            standalone = False

    if not standalone:
        css_block = f'<link rel="stylesheet" href="{TABULATOR_CSS}">'
        js_block = f'<script src="{XLSX_JS}"></script>\n<script src="{TABULATOR_JS}"></script>'

    html = (_HTML_TEMPLATE
            .replace("__CSS_BLOCK__", css_block)
            .replace("__JS_BLOCK__", js_block)
            .replace("__PAYLOAD_JSON__", payload_json)
            .replace("__BRAND_URL__", BRAND_URL)
            .replace("__BRAND_NAME__", BRAND_NAME)
            .replace("__ANALYST_NAME__", ANALYST_NAME))

    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    mode = "standalone (offline)" if standalone else "CDN (needs internet)"
    print(f"Saved HTML dashboard: {out_html}")
    print(f"  Mode: {mode}")
