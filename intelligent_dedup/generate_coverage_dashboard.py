"""
generate_coverage_dashboard.py
================================================================================
Scans the coverage_history/ directory for past test runs and generates a
beautiful HTML dashboard (coverage_history/index.html) that lets the user
browse all runs, see trends, and drill into per-run coverage reports.

Usage:
    python generate_coverage_dashboard.py [--open]

Flags:
    --open    Open the generated dashboard in the default browser after build.
================================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from extract_test_docs import get_test_descriptions

HISTORY_DIR = Path(__file__).parent / "coverage_history"
DASHBOARD_FILE = HISTORY_DIR / "index.html"


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def load_runs() -> list[dict]:
    """Return a list of run metadata dicts, newest first."""
    runs: list[dict] = []
    if not HISTORY_DIR.exists():
        return runs

    docs = get_test_descriptions(Path(__file__).parent / "tests")

    for entry in sorted(HISTORY_DIR.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        meta_file = entry / "meta.json"
        junit_file = entry / "junit.xml"
        if not meta_file.exists():
            continue
        try:
            meta: dict = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            meta["_dir"] = entry.name
            meta["_htmlcov"] = entry.name + "/htmlcov/index.html"
            
            # Enrich with details from JUnit if missing or stale
            passed, failed, errors, dur, p_list, f_list = _parse_junit(entry, docs)
            meta["passed_list"] = p_list
            meta["failed_list"] = f_list
            
            runs.append(meta)
        except Exception:
            pass  # malformed run — skip

    return runs


def _parse_junit(run_dir: Path, global_docs: dict[str, str] = {}) -> tuple[int, int, int, float, list[dict], list[dict]]:
    """Return (passed, failed, errors, duration, passed_list, failed_list) from junit XML."""
    junit = run_dir / "junit.xml"
    passed_list = []
    failed_list = []
    if not junit.exists():
        return 0, 0, 0, 0.0, [], []
    try:
        tree = ET.parse(str(junit))
        root = tree.getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            return 0, 0, 0, 0.0, [], []
        
        total   = int(suite.get("tests",    0))
        failed_count = int(suite.get("failures", 0))
        errors_count = int(suite.get("errors",   0))
        skipped = int(suite.get("skipped",  0))
        dur     = float(suite.get("time",   0))
        passed_count = total - failed_count - errors_count - skipped

        for case in suite.findall("testcase"):
            name = case.get("name", "Unknown")
            classname = case.get("classname", "")
            failure = case.find("failure")
            
            # Simple description generation from name or docstring
            cls_only = classname.split(".")[-1]
            key_full = f"{cls_only}.{name}"
            desc = global_docs.get(key_full) or global_docs.get(name)
            
            if not desc:
                desc = name.replace("test_", "").replace("_", " ").title()
                
            # Heuristic for mapping test file to source file
            # e.g. tests.test_agents.TestRetentionAgent -> app/agents/retention_agent.py
            test_file_path = classname.replace(".", "/") + ".py"
            
            # Smart guess for "Tested Code File"
            tested_file = "Unknown"
            if "test_agents" in classname: 
                tested_file = "app/agents/retention_agent.py" if "Retention" in classname else "app/agents/reasoning_engine.py"
            elif "test_cli" in classname: tested_file = "cli.py"
            elif "test_engine" in classname:
                if "Scanner" in classname: tested_file = "app/engine/scanner.py"
                elif "Hasher" in classname: tested_file = "app/engine/hasher.py"
                else: tested_file = "app/engine/deduplicator.py"
            elif "test_ml" in classname:
                tested_file = "app/ml/vector_index.py" if "Vector" in classname else "app/ml/embedder.py"
            elif "test_models" in classname or "test_database" in classname: 
                tested_file = "app/models/database.py" if "database" in classname or "Repository" in classname else "app/models/repository.py"
            elif "test_viewmodels" in classname:
                tested_file = "app/viewmodels/results_viewmodel.py" if "Results" in classname else "app/viewmodels/scan_viewmodel.py"
            elif "test_main_window" in classname: tested_file = "app/views/main_window.py"
            elif "test_dialogs" in classname or "test_view" in classname:
                tested_file = "app/views/dialogs/load_session_dialog.py" if "LoadSession" in classname else "app/views/main_window.py"

            test_info = {
                "name": name,
                "class": classname,
                "desc": desc,
                "time": case.get("time", "0.000"),
                "file": test_file_path,
                "tested_file": tested_file,
                "status": "FAIL" if failure is not None else "PASS"
            }
            
            if failure is not None:
                test_info["error"] = failure.get("message", "Test failed")
                failed_list.append(test_info)
            else:
                passed_list.append(test_info)
                
        return passed_count, failed_count, errors_count, dur, passed_list, failed_list
    except Exception:
        return 0, 0, 0, 0.0, [], []


def _format_ts(ts_str: str) -> str:
    """Convert 2026-03-28_12-49-51 to 28/03/2026, 12:49:51."""
    if not ts_str: return "?"
    try:
        clean = ts_str.replace("T", " ").replace("_", " ")
        date_part = clean.split(" ")[0]
        time_part = clean.split(" ")[1] if " " in clean else "00:00:00"
        y, m, d = date_part.split("-")
        return f"{d}/{m}/{y}, {time_part.replace('-', ':')[:8]}"
    except Exception:
        return ts_str


def _parse_coverage_json(run_dir: Path) -> float:
    """Return total coverage % from coverage.json (0-100)."""
    cov_file = run_dir / "coverage.json"
    if not cov_file.exists():
        return 0.0
    try:
        data = json.loads(cov_file.read_text(encoding="utf-8-sig"))
        return round(data.get("totals", {}).get("percent_covered", 0.0), 1)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard HTML generation
# ─────────────────────────────────────────────────────────────────────────────

def _coverage_color(pct: float) -> str:
    if pct >= 80:
        return "#4caf50"
    if pct >= 60:
        return "#ff9800"
    return "#f44336"


def _status_badge(passed: int, failed: int, errors: int) -> str:
    if failed == 0 and errors == 0:
        return '<span class="badge badge-pass">PASS</span>'
    return '<span class="badge badge-fail">FAIL</span>'


def _sparkline_points(runs: list[dict], width: int = 220, height: int = 40) -> str:
    """Generate SVG polyline points for coverage trend (newest right)."""
    if len(runs) < 2:
        return ""
    values = [r.get("coverage_pct", 0.0) for r in reversed(runs)]
    n = len(values)
    max_v = max(values) or 100
    min_v = min(values)
    rng = max(max_v - min_v, 1)
    pts = []
    for i, v in enumerate(values):
        x = i / (n - 1) * width
        y = height - ((v - min_v) / rng) * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


def build_dashboard(runs: list[dict]) -> str:
    """Return complete HTML string for the dashboard."""

    total_runs = len(runs)
    latest = runs[0] if runs else {}
    latest_pct = latest.get("coverage_pct", 0.0)
    latest_passed = latest.get("passed", 0)
    latest_failed = latest.get("failed", 0)
    # Coverage trend data for Chart.js
    chart_labels = json.dumps([_format_ts(r.get("timestamp", "")) for r in reversed(runs)])
    chart_data   = json.dumps([r.get("coverage_pct", 0.0) for r in reversed(runs)])

    rows_html = ""
    for i, r in enumerate(runs):
        run_num = total_runs - i
        run_id  = r.get("_dir", str(i))
        ts      = r.get("timestamp", "")
        display_ts = _format_ts(ts)
        passed  = r.get("passed",  0)
        failed  = r.get("failed",  0)
        errors  = r.get("errors",  0)
        dur     = r.get("duration_sec", 0.0)
        pct     = r.get("coverage_pct", 0.0)
        col     = _coverage_color(pct)
        badge   = _status_badge(passed, failed, errors)
        htmlcov = r.get("_htmlcov", "#")
        is_latest = "row-latest" if i == 0 else ""
        
        test_details_url = run_id + "/test_details.html"
        rows_html += f"""
        <tr class="{is_latest}">
            <td class="num" style="text-align:left; color:var(--muted)">#{run_num}</td>
            <td>{display_ts}</td>
            <td>{badge}</td>
            <td class="num passed">
                <a class="detail-link" href="{test_details_url}">{passed}</a>
            </td>
            <td class="num failed">
                <a class="detail-link" href="{test_details_url}">{failed + errors}</a>
            </td>
            <td class="num">{passed + failed + errors}</td>
            <td>
                <div class="cov-bar-wrap">
                    <div class="cov-bar" style="width:{min(pct,100):.1f}%;background:{col}"></div>
                    <span class="cov-label" style="color:{col}">{pct:.1f}%</span>
                </div>
            </td>
            <td class="num">{dur:.1f}s</td>
            <td>
                <a class="btn-detail" href="{htmlcov}" title="Open coverage report">
                    View Report
                </a>
            </td>
        </tr>"""

    no_runs_msg = "" if runs else """
        <tr><td colspan="9" style="text-align:center;padding:40px;opacity:.5;">
            No test runs found yet. Run <code>run_tests.ps1</code> to get started.
        </td></tr>"""

    cov_color = _coverage_color(latest_pct)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intelligent Dedup - Test Coverage Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:        #0d1117;
    --surface:   #161b22;
    --surface2:  #1e2530;
    --border:    #30363d;
    --text:      #e6edf3;
    --muted:     #8b949e;
    --accent:    #58a6ff;
    --pass:      #3fb950;
    --fail:      #f85149;
    --warn:      #d29922;
    --radius:    12px;
    --shadow:    0 8px 32px rgba(0,0,0,.45);
  }}

  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 24px;
  }}

  /* ── Header ─────────────────────────────────────────────── */
  .header {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }}
  .header-logo {{
    font-size: 28px;
    line-height: 1;
  }}
  .header-titles h1 {{
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -.3px;
    background: linear-gradient(135deg,#58a6ff,#bc8cff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .header-titles p {{
    font-size: 13px;
    color: var(--muted);
    margin-top: 2px;
  }}
  .header-refresh {{
    margin-left: auto;
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--accent);
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-family: inherit;
    transition: background .15s;
  }}
  .header-refresh:hover {{ background: var(--surface); }}

  .header-run {{
    background: #238636;
    border: 1px solid rgba(240,246,252,0.1);
    color: #ffffff;
    padding: 8px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    transition: background 0.2s, transform 0.1s;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .header-run:hover {{ background: #2ea043; }}
  .header-run:active {{ transform: scale(0.98); }}
  .header-run:disabled {{
    background: var(--surface2);
    color: var(--muted);
    cursor: not-allowed;
    opacity: 0.7;
  }}
  .header-run .icon {{ font-size: 16px; }}

  @keyframes pulse {{
    0% {{ transform: scale(1); opacity: 1; }}
    50% {{ transform: scale(1.05); opacity: 0.8; }}
    100% {{ transform: scale(1); opacity: 1; }}
  }}
  .running {{ animation: pulse 1.5s infinite; }}

  /* ── Terminal Section ────────────────────────────────────── */
  .terminal-section {{
    background: #000000;
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-top: 28px;
    padding: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow);
  }}
  .terminal-header {{
    background: #1e1e1e;
    padding: 8px 16px;
    border-bottom: 1px solid #333;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .terminal-header .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .terminal-body {{
    background: #000;
    color: #d4d4d4;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    padding: 16px;
    height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.5;
  }}
  .terminal-entry {{ margin-bottom: 4px; }}
  .terminal-entry.info {{ color: #58a6ff; }}
  .terminal-entry.error {{ color: #f85149; }}
  .terminal-entry.success {{ color: #3fb950; }}
  .terminal-entry.cmd {{ color: #d29922; font-weight: bold; }}

  /* ── KPI Cards ───────────────────────────────────────────── */
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }}
  .kpi {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px 24px;
    position: relative;
    overflow: hidden;
    transition: transform .2s, box-shadow .2s;
  }}
  .kpi:hover {{ transform: translateY(-2px); box-shadow: var(--shadow); }}
  .kpi::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--kpi-color, var(--accent));
    border-radius: var(--radius) var(--radius) 0 0;
  }}
  .kpi-label {{
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .8px;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .kpi-value {{
    font-size: 36px;
    font-weight: 700;
    line-height: 1;
    color: var(--kpi-color, var(--text));
  }}
  .kpi-sub {{
    font-size: 12px;
    color: var(--muted);
    margin-top: 6px;
  }}

  /* ── Chart Section ───────────────────────────────────────── */
  .chart-section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 28px;
  }}
  .section-title {{
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title span {{ color: var(--muted); font-weight: 400; font-size: 12px; }}
  .chart-wrap {{ height: 200px; position: relative; }}

  /* ── History Table ───────────────────────────────────────── */
  .table-section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 480px; /* Approximately 6-7 rows including header */
  }}
  .table-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 24px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }}
  .table-scroll-wrap {{
    overflow-y: auto;
    flex: 1;
  }}
  .run-count {{
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  thead th {{
    background: var(--surface2);
    color: var(--muted);
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .6px;
    padding: 12px 16px;
    text-align: left;
    white-space: nowrap;
  }}
  tbody tr {{
    border-top: 1px solid var(--border);
    transition: background .12s;
  }}
  tbody tr:hover {{ background: var(--surface2); }}
  tbody tr.row-latest {{
    background: rgba(88,166,255,.055);
    border-left: 3px solid var(--accent);
  }}
  tbody td {{
    padding: 13px 16px;
    vertical-align: middle;
  }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .passed {{ color: var(--pass); font-weight: 600; }}
  .failed {{ color: var(--fail); font-weight: 600; }}

  /* ── Badges ──────────────────────────────────────────────── */
  .badge {{
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .5px;
    padding: 3px 9px;
    border-radius: 4px;
  }}
  .badge-pass {{ background: rgba(63,185,80,.18); color: var(--pass); }}
  .badge-fail {{ background: rgba(248,81,73,.18); color: var(--fail); }}

  /* ── Coverage Bar ────────────────────────────────────────── */
  .cov-bar-wrap {{
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 140px;
  }}
  .cov-bar {{
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    min-width: 0;
    max-width: 100px;
    position: relative;
    overflow: visible;
  }}
  .cov-label {{
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }}

  /* ── Detail Links ────────────────────────────────────────── */
  .detail-link {{
    color: inherit;
    text-decoration: underline dotted;
    text-underline-offset: 4px;
    cursor: pointer;
    transition: color 0.15s;
  }}
  .detail-link:hover {{
    color: var(--accent) !important;
  }}

  /* ── Detail Button ───────────────────────────────────────── */
  .btn-detail {{
    display: inline-block;
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--accent);
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
    transition: background .15s, border-color .15s;
  }}
  .btn-detail:hover {{
    background: rgba(88,166,255,.1);
    border-color: var(--accent);
  }}

  /* ── Generated timestamp ─────────────────────────────────── */
  .footer {{
    text-align: center;
    color: var(--muted);
    font-size: 11px;
    margin-top: 24px;
  }}

  /* ── Animations ──────────────────────────────────────────── */
  @keyframes fadeIn {{
    from {{ opacity:0; transform:translateY(12px); }}
    to   {{ opacity:1; transform:translateY(0); }}
  }}
  .kpi, .chart-section, .table-section {{
    animation: fadeIn .35s ease both;
  }}
  .chart-section {{ animation-delay: .05s; }}
  .table-section {{ animation-delay: .10s; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-logo">🔍</div>
  <div class="header-titles">
    <h1>Intelligent Dedup &ndash; Coverage Dashboard</h1>
    <p>Test history and code coverage trends across all runs</p>
  </div>
  <div class="header-actions" style="margin-left: auto; display: flex; gap: 10px;">
    <!-- Hidden latest run marker for polling -->
    <div id="latestRunMarker" style="display:none" data-id="{latest.get('_dir', '')}"></div>
    <button id="runTestsBtn" class="header-run" onclick="runTests()">
       <span class="icon">🚀</span> Run Tests
    </button>
    <button class="header-refresh" onclick="location.reload()">&#8635; Refresh</button>
  </div>
</div>

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi" style="--kpi-color:{cov_color}">
    <div class="kpi-label">Latest Coverage</div>
    <div class="kpi-value">{latest_pct:.1f}<small style="font-size:18px">%</small></div>
    <div class="kpi-sub">Branch + line coverage</div>
  </div>
  <div class="kpi" style="--kpi-color:var(--pass)">
    <div class="kpi-label">Tests Passed</div>
    <div class="kpi-value">{latest_passed}</div>
    <div class="kpi-sub">Last run</div>
  </div>
  <div class="kpi" style="--kpi-color:{'var(--fail)' if latest_failed else 'var(--pass)'}">
    <div class="kpi-label">Tests Failed</div>
    <div class="kpi-value">{latest_failed}</div>
    <div class="kpi-sub">Last run</div>
  </div>
  <div class="kpi" style="--kpi-color:var(--accent)">
    <div class="kpi-label">Total Runs</div>
    <div class="kpi-value">{total_runs}</div>
    <div class="kpi-sub">Stored in history</div>
  </div>
</div>

<!-- Trend Chart -->
<div class="chart-section">
  <div class="section-title">Coverage Trend <span>over time</span></div>
  <div class="chart-wrap">
    <canvas id="trendChart"></canvas>
  </div>
</div>

<!-- History Table -->
<div class="table-section">
  <div class="table-header">
    <div class="section-title" style="margin:0">Run History</div>
    <div class="run-count">{total_runs} run{'s' if total_runs != 1 else ''}</div>
  </div>
  <div class="table-scroll-wrap">
  <table>
    <thead>
      <tr>
        <th class="num" style="text-align:left">Run #</th>
        <th>Timestamp</th>
        <th>Status</th>
        <th class="num">Passed</th>
        <th class="num">Failed</th>
        <th class="num">Total</th>
        <th>Coverage</th>
        <th class="num">Duration</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
      {no_runs_msg}
    </tbody>
  </table>
  </div>
</div>

<!-- Terminal Output -->
<div class="terminal-section">
  <div class="terminal-header">
    <div class="dot" style="background:#ff5f56"></div>
    <div class="dot" style="background:#ffbd2e"></div>
    <div class="dot" style="background:#27c93f"></div>
    <span style="margin-left:8px">Test Execution Console Output</span>
  </div>
  <div id="terminal" class="terminal-body">
    <div class="terminal-entry info">Ready to run tests. Console output will appear here...</div>
  </div>
</div>

    </div>
</div>

<div class="footer">
  Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} &bull; Intelligent Dedup Coverage Dashboard
</div>

<script>
const labels = {chart_labels};
const data   = {chart_data};

if (labels.length > 0) {{
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (window.trendChartInstance) window.trendChartInstance.destroy();
  window.trendChartInstance = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels,
      datasets: [{{
        label: 'Coverage %',
        data,
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88,166,255,0.08)',
        borderWidth: 2,
        pointRadius: data.length < 20 ? 4 : 2,
        pointBackgroundColor: '#58a6ff',
        fill: true,
        tension: 0.35,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: '#1e2530',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#8b949e',
          callbacks: {{
            label: ctx => ` ${{ctx.parsed.y.toFixed(1)}}% coverage`,
          }}
        }}
      }},
      scales: {{
        x: {{
          grid: {{ color: '#30363d' }},
          ticks: {{ color: '#8b949e', maxTicksLimit: 8, maxRotation: 30 }},
        }},
        y: {{
          min: 0, max: 100,
          grid: {{ color: '#30363d' }},
          ticks: {{
            color: '#8b949e',
            callback: v => v + '%',
          }},
        }}
      }}
    }}
  }});
}} else {{
  document.querySelector('.chart-wrap').innerHTML =
    '<p style="text-align:center;line-height:200px;color:var(--muted);font-size:13px">No data yet - run the test suite first</p>';
}}

function escapeHTML(str) {{
  const p = document.createElement('p');
  p.textContent = str;
  return p.innerHTML;
}}

async function syncDashboard(isAuto = false) {{
    const marker = document.getElementById('latestRunMarker');
    const oldId = marker ? marker.dataset.id : '';
    
    try {{
        const res = await fetch(window.location.pathname + '?t=' + Date.now());
        const html = await res.text();
        const parser = new DOMParser();
        const newDoc = parser.parseFromString(html, 'text/html');
        
        const newMarker = newDoc.querySelector('#latestRunMarker');
        const newId = newMarker ? newMarker.dataset.id : '';
        
        if (newId !== oldId || !isAuto) {{
            if (isAuto) console.log('[dashboard] New run detected: ' + newId);
            
            const newKpi = newDoc.querySelector('.kpi-grid');
            const newTable = newDoc.querySelector('.table-section');
            const newChart = newDoc.querySelector('.chart-wrap');
            
            if (newKpi) document.querySelector('.kpi-grid').innerHTML = newKpi.innerHTML;
            if (newTable) document.querySelector('.table-section').innerHTML = newTable.innerHTML;
            if (newChart) document.querySelector('.chart-wrap').innerHTML = newChart.innerHTML;
            if (marker && newMarker) marker.dataset.id = newId;

            const scripts = newDoc.querySelectorAll('script');
            scripts.forEach(s => {{
               if (s.textContent.includes('const labels =')) {{
                   try {{ eval(s.textContent); }} catch(e) {{ console.error('Chart update failed', e); }}
               }}
            }});
            
            if (isAuto && document.getElementById('terminal')) {{
                const term = document.getElementById('terminal');
                term.innerHTML += `<div class="terminal-entry info">Auto-sync: New run detected (${{newId}}).</div>`;
                term.scrollTop = term.scrollHeight;
            }}
        }}
    }} catch (err) {{
        console.error('Dashboard sync failed:', err);
    }}
}}

function runTests() {{
  const btn = document.getElementById('runTestsBtn');
  const term = document.getElementById('terminal');
  const originalText = btn.innerHTML;

  if (window.location.protocol === 'file:') {{
    term.innerHTML = '<div class="terminal-entry error">❌ ERROR: Interactive features disabled.</div>';
    term.innerHTML += '<div class="terminal-entry">The "Run Tests" button requires a local server to execute scripts.</div>';
    term.innerHTML += '<div class="terminal-entry info">To enable this feature:</div>';
    term.innerHTML += '<div class="terminal-entry">1. Run the server: <code>python serve_dashboard.py</code></div>';
    term.innerHTML += '<div class="terminal-entry">2. Open the dashboard at: <a href="http://localhost:5000" style="color:#58a6ff">http://localhost:5000</a></div>';
    alert("Please run 'python serve_dashboard.py' and open the dashboard via http://localhost:5000 to use this feature.");
    return;
  }}
  
  btn.disabled = true;
  btn.classList.add('running');
  btn.innerHTML = '<span class="icon">⌛</span> Running Tests...';
  
  term.innerHTML = '<div class="terminal-entry cmd">> powershell.exe -File ./run_tests.ps1 -NoOpen</div>';
  term.innerHTML += '<div class="terminal-entry info">Starting test execution sequence...</div>';
  term.scrollTop = term.scrollHeight;

  fetch('/run-tests', {{ method: 'POST' }})
    .then(async response => {{
      const data = await response.json();
      const escapedOutput = escapeHTML(data.output || 'No output captured.');
      term.innerHTML += `<div class="terminal-entry">${{escapedOutput}}</div>`;
      
      if (response.ok && (data.status === "success" || data.code === 0)) {{
        term.innerHTML += '<div class="terminal-entry success">Tests completed successfully. Syncing dashboard...</div>';
        btn.innerHTML = '<span class="icon">✅</span> Done! Syncing...';
        
        await syncDashboard(false);
        
        setTimeout(() => {{
            btn.innerHTML = originalText;
            btn.disabled = false;
            btn.classList.remove('running');
        }}, 2000);
      }} else {{
        throw new Error(data.error || 'Test run failed');
      }}
      term.scrollTop = term.scrollHeight;
    }})
    .catch(err => {{
      console.error(err);
      term.innerHTML += `<div class="terminal-entry error">Error: ${{err.message}}</div>`;
      btn.innerHTML = '<span class="icon">❌</span> Error. Try Again?';
      btn.disabled = false;
      btn.classList.remove('running');
      term.scrollTop = term.scrollHeight;
      setTimeout(() => {{ if (!btn.classList.contains('running')) btn.innerHTML = originalText; }}, 5000);
    }});
}}

// Background polling for external runs (every 10 seconds)
setInterval(() => syncDashboard(true), 10000);
setTimeout(() => syncDashboard(true), 2000);
</script>
</body>
</html>
"""

def build_test_details_page(run_meta: dict) -> str:
    """Generate a standalone HTML page for test details."""
    passed = run_meta.get("passed_list", [])
    failed = run_meta.get("failed_list", [])
    all_tests = failed + passed  # Failed first
    ts = run_meta.get("timestamp", "Unknown").replace("T", " ").replace("_", " ")[:19]
    
    rows = ""
    for i, t in enumerate(all_tests):
        status_cls = "status-pass" if t["status"] == "PASS" else "status-fail"
        err_div = f'<div class="test-error">{t["error"]}</div>' if t.get("error") else ""
        rows += f"""
        <tr>
            <td class="num">{i+1}</td>
            <td><span class="status-badge {status_cls}">{t["status"]}</span></td>
            <td class="desc-cell">
                <div class="test-desc">{t["desc"]}</div>
                {err_div}
            </td>
            <td class="mono">{t["name"]}</td>
            <td class="mono">{t["class"]}</td>
            <td class="mono">{t["file"]}</td>
            <td class="mono">{t["tested_file"]}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test Details - {ts}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3;
    --muted: #8b949e; --accent: #58a6ff; --pass: #3fb950; --fail: #f85149;
  }}
  body {{ 
    font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); 
    margin: 0; padding: 40px; line-height: 1.5; overflow-y: auto;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 30px; }}
  .btn-back {{
    text-decoration: none; background: var(--surface); border: 1px solid var(--border);
    color: var(--accent); padding: 10px 20px; border-radius: 8px; font-weight: 600;
    transition: background 0.2s;
  }}
  .btn-back:hover {{ background: #1e2530; }}
  h1 {{ margin: 0; font-size: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }}
  th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }}
  th {{ background: #1e2530; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .num {{ text-align: center; color: var(--muted); width: 40px; }}
  .status-badge {{ padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 10px; }}
  .status-pass {{ background: rgba(63,185,80,0.15); color: var(--pass); }}
  .status-fail {{ background: rgba(248,81,73,0.15); color: var(--fail); }}
  .mono {{ font-family: 'Consolas', monospace; color: #79c0ff; font-size: 12px; word-break: break-all; }}
  .desc-cell {{ min-width: 300px; }}
  .test-desc {{ font-weight: 600; margin-bottom: 4px; color: #fff; }}
  .test-error {{ background: #21262d; padding: 10px; border-radius: 6px; color: #ff7b72; font-family: monospace; font-size: 12px; white-space: pre-wrap; margin-top: 8px; border: 1px solid #30363d; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Test Execution Details &mdash; {ts}</h1>
    <a href="../index.html" class="btn-back">&larr; Back to Dashboard</a>
  </div>
  <table>
    <thead>
      <tr>
        <th class="num">#</th>
        <th>Status</th>
        <th>Description</th>
        <th>Test Name</th>
        <th>Class Name</th>
        <th>Test File Path</th>
        <th>Tested Module</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>
</body>
</html>
"""



def inject_back_button_into_report(htmlcov_dir: Path):
    """Inject a fixed 'Back to Dashboard' button into the coverage HTML report."""
    index_file = htmlcov_dir / "index.html"
    if not index_file.exists(): return
    try:
        content = index_file.read_text(encoding="utf-8")
        if 'id="back-to-dash"' in content: return
        
        btn_html = """
    <style>
        #back-to-dash {
            position: fixed; top: 10px; right: 10px; z-index: 10000;
            background: #161b22; color: #58a6ff; border: 1px solid #30363d;
            padding: 8px 16px; border-radius: 6px; text-decoration: none;
            font-family: sans-serif; font-weight: bold; font-size: 13px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }
        #back-to-dash:hover { background: #1e2530; border-color: #58a6ff; }
    </style>
    <a id="back-to-dash" href="../../index.html">&larr; Back to Dashboard</a>
    """
        if "<body>" in content:
            new_content = content.replace("<body>", "<body>" + btn_html)
            index_file.write_text(new_content, encoding="utf-8")
        elif "<body" in content: # Handle body with attributes
            # Very simple inject after body tag
            parts = content.split(">", 1)
            # This is risky, let's just find first > after <body
            body_idx = content.find("<body")
            if body_idx != -1:
                end_idx = content.find(">", body_idx)
                if end_idx != -1:
                    new_content = content[:end_idx+1] + btn_html + content[end_idx+1:]
                    index_file.write_text(new_content, encoding="utf-8")
    except Exception as e:
        print(f"[dashboard] Could not inject back button: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate and optionally open coverage dashboard")
    parser.add_argument("--open", action="store_true", help="Open dashboard in default browser")
    args = parser.parse_args()

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    
    # 1. Build individual detail pages and inject back buttons
    for r in runs:
        run_dir = HISTORY_DIR / r["_dir"]
        details_html = build_test_details_page(r)
        (run_dir / "test_details.html").write_text(details_html, encoding="utf-8")
        
        # Also inject back button into htmlcov if it exists
        inject_back_button_into_report(run_dir / "htmlcov")
        
        print(f"[dashboard] Generated details and injected report links for: {r['_dir']}")

    # 2. Build index
    html = build_dashboard(runs)
    DASHBOARD_FILE.write_text(html, encoding="utf-8")
    print(f"[dashboard] Written: {DASHBOARD_FILE}")

    if args.open:
        url = DASHBOARD_FILE.resolve().as_uri()
        print(f"[dashboard] Opening: {url}")
        webbrowser.open(url)


if __name__ == "__main__":
    main()
