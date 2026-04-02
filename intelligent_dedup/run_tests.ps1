# =============================================================================
# Intelligent Duplicate Finder - Full Test & Coverage Runner
# =============================================================================

param (
    [switch]$NoOpen
)

$VENV_PYTHON = ".\.venv\Scripts\python.exe"

if (-Not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "        Please run:  python -m venv .venv  and install requirements." -ForegroundColor Yellow
    exit 1
}

# ── Timestamped output directory ─────────────────────────────────────────────
$TIMESTAMP  = (Get-Date -Format "yyyy-MM-dd_HH-mm-ss")
$HIST_ROOT  = "coverage_history"
$RUN_DIR    = "$HIST_ROOT\$TIMESTAMP"
$HTMLCOV    = "$RUN_DIR\htmlcov"

New-Item -ItemType Directory -Path $RUN_DIR -Force | Out-Null

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Intelligent Dedup - Full Test and Coverage Suite" -ForegroundColor Cyan
Write-Host "  Run: $TIMESTAMP" -ForegroundColor DarkCyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Capture test start time ───────────────────────────────────────────────────
$START_TIME = [System.Diagnostics.Stopwatch]::StartNew()

# ── Run pytest ────────────────────────────────────────────────────────────────
#   --cov-report=html:<dir>    per-run HTML coverage
#   --cov-report=json:<file>   machine-readable coverage totals
#   --junitxml=<file>          JUnit XML for pass/fail counts
#   --cov-report=term-missing  terminal summary
& $VENV_PYTHON -m pytest `
    tests/ `
    -v `
    --tb=short `
    --cov=app `
    --cov=cli `
    --cov-branch `
    --cov-report=term-missing `
    --cov-report="html:$HTMLCOV" `
    --cov-report="json:$RUN_DIR\coverage.json" `
    "--junitxml=$RUN_DIR\junit.xml"

$EXIT_CODE = $LASTEXITCODE
$START_TIME.Stop()
$DURATION  = [math]::Round($START_TIME.Elapsed.TotalSeconds, 2)

Write-Host ""
if ($EXIT_CODE -eq 0) {
    Write-Host "[PASS] All tests passed in ${DURATION}s." -ForegroundColor Green
} else {
    Write-Host "[FAIL] One or more tests failed (exit code: $EXIT_CODE, ${DURATION}s)." -ForegroundColor Red
}

# ── Parse coverage % via Python (handles large/nested JSON reliably) ─────────
$COV_PCT = 0.0
$COV_JSON = "$RUN_DIR\coverage.json"
if (Test-Path $COV_JSON) {
    try {
        $pct_str = & $VENV_PYTHON -c "import json,sys; d=json.load(open(sys.argv[1])); print(round(d['totals']['percent_covered'],1))" $COV_JSON 2>$null
        if ($pct_str) { $COV_PCT = [double]$pct_str }
    } catch { $COV_PCT = 0.0 }
}

# ── Parse pass/fail counts from JUnit XML ────────────────────────────────────
$PASSED = 0; $FAILED = 0; $ERRORS = 0; $TOTAL = 0
$JUNIT = "$RUN_DIR\junit.xml"
if (Test-Path $JUNIT) {
    try {
        [xml]$junit_xml = Get-Content $JUNIT -Raw
        $suite = $junit_xml.testsuite
        if (-not $suite) { $suite = $junit_xml.testsuites.testsuite }
        if ($suite) {
            $TOTAL   = [int]$(if ($suite.tests)    { $suite.tests    } else { 0 })
            $FAILED  = [int]$(if ($suite.failures) { $suite.failures } else { 0 })
            $ERRORS  = [int]$(if ($suite.errors)   { $suite.errors   } else { 0 })
            $SKIPPED = [int]$(if ($suite.skipped)  { $suite.skipped  } else { 0 })
            $PASSED  = $TOTAL - $FAILED - $ERRORS - $SKIPPED
        }
    } catch {
        # JUnit parse failed - leave defaults
    }
}

# ── Write meta.json ───────────────────────────────────────────────────────────
$META = @{
    timestamp    = $TIMESTAMP
    exit_code    = $EXIT_CODE
    passed       = $PASSED
    failed       = ($FAILED + $ERRORS)
    errors       = $ERRORS
    total        = $TOTAL
    coverage_pct = $COV_PCT
    duration_sec = $DURATION
} | ConvertTo-Json -Compress
Set-Content -Path "$RUN_DIR\meta.json" -Value $META -Encoding UTF8
Write-Host "[INFO] Run saved to $RUN_DIR" -ForegroundColor DarkGray

# ── Rebuild dashboard and open in browser ────────────────────────────────────
Write-Host ""
Write-Host "[INFO] Generating coverage dashboard ..." -ForegroundColor Yellow
if ($NoOpen) {
    & $VENV_PYTHON generate_coverage_dashboard.py
} else {
    & $VENV_PYTHON generate_coverage_dashboard.py --open
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Coverage HTML (this run):  $HTMLCOV\index.html" -ForegroundColor Cyan
Write-Host "  Dashboard (all runs)    :  coverage_history\index.html" -ForegroundColor Cyan
Write-Host "  Coverage                :  $COV_PCT%" -ForegroundColor Cyan
Write-Host "  Tests                   :  $PASSED passed / $($FAILED+$ERRORS) failed" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

exit $EXIT_CODE
