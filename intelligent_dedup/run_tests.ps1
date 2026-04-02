# =============================================================================
# Intelligent Duplicate Finder - Full Test & Coverage Runner
# =============================================================================
# Runs ALL test files in tests/ (including UI tests using the unbound-method
# pattern) and generates a complete coverage report for the app module.
#
# Outputs:
#   Terminal summary with missing lines  (--cov-report=term-missing)
#   HTML report at  htmlcov\index.html
#   Plain-text snapshot at  coverage_report_<timestamp>.txt
# =============================================================================

$VENV_PYTHON = ".\.venv\Scripts\python.exe"

if (-Not (Test-Path $VENV_PYTHON)) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "        Please run:  python -m venv .venv  and install requirements." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Intelligent Dedup - Full Test and Coverage Suite" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Core flags:
#   --cov=app            coverage for the entire app package
#   --cov=cli            coverage for top-level cli.py
#   --cov-branch         branch coverage (catches both True/False paths)
#   --cov-report=term-missing  terminal summary with uncovered line numbers
#   --cov-report=html:htmlcov  full HTML report in htmlcov/
# All test_*.py files in tests/ are collected automatically by pytest.
# QApplication-dependent tests use the unbound-method pattern so they
# run safely without a real display server.
# ---------------------------------------------------------------------------

& $VENV_PYTHON -m pytest `
    tests/ `
    -v `
    --tb=short `
    --cov=app `
    --cov=cli `
    --cov-branch `
    --cov-report=term-missing `
    --cov-report=html:htmlcov `
    --cov-report=term

$EXIT_CODE = $LASTEXITCODE

Write-Host ""

if ($EXIT_CODE -eq 0) {
    Write-Host "[PASS] All tests passed." -ForegroundColor Green
} else {
    Write-Host "[FAIL] One or more tests failed (exit code: $EXIT_CODE)." -ForegroundColor Red
}

# Save a timestamped plain-text coverage summary for reference
$TIMESTAMP = (Get-Date -Format "yyyy-MM-dd_HH-mm-ss")
$REPORT_FILE = "coverage_report_$TIMESTAMP.txt"
Write-Host ""
Write-Host "[INFO] Saving plain-text coverage snapshot to $REPORT_FILE ..." -ForegroundColor Yellow

& $VENV_PYTHON -m coverage report --show-missing | Tee-Object -FilePath $REPORT_FILE

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Coverage HTML report:  htmlcov\index.html" -ForegroundColor Cyan
Write-Host "  Plain-text snapshot :  $REPORT_FILE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

exit $EXIT_CODE
