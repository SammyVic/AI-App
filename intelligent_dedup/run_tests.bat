@echo off
REM =============================================================================
REM Intelligent Duplicate Finder — Full Test & Coverage Runner (batch)
REM =============================================================================
REM Runs ALL test files in tests/ (including UI tests using unbound-method
REM pattern) and generates a full coverage report for the app module.
REM
REM Outputs:
REM   Terminal summary with missing lines
REM   HTML report at  htmlcov\index.html
REM   Plain-text snapshot at  coverage_report_<timestamp>.txt
REM =============================================================================

set VENV_PYTHON=.\.venv\Scripts\python.exe

if not exist %VENV_PYTHON% (
    echo [ERROR] Virtual environment not found at .venv
    echo         Please run:  python -m venv .venv  and install requirements.
    exit /b 1
)

echo.
echo ============================================================
echo   Intelligent Dedup - Full Test ^& Coverage Suite
echo ============================================================
echo.

REM Run all tests with branch coverage + dual report format
%VENV_PYTHON% -m pytest ^
    tests/ ^
    -v ^
    --tb=short ^
    --cov=app ^
    --cov=cli ^
    --cov-branch ^
    --cov-report=term-missing ^
    --cov-report=html:htmlcov ^
    --cov-report=term

set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE%==0 (
    echo [PASS] All tests passed.
) else (
    echo [FAIL] One or more tests failed. Exit code: %EXIT_CODE%
)

REM Save a timestamped plain-text snapshot
for /f "tokens=1-6 delims=/: " %%a in ("%DATE% %TIME%") do (
    set TIMESTAMP=%%c-%%a-%%b_%%d-%%e-%%f
)
set REPORT_FILE=coverage_report_%TIMESTAMP%.txt

echo.
echo [INFO] Saving plain-text snapshot to %REPORT_FILE% ...
%VENV_PYTHON% -m coverage report --show-missing > %REPORT_FILE%

echo.
echo ============================================================
echo   Coverage HTML report :  htmlcov\index.html
echo   Plain-text snapshot  :  %REPORT_FILE%
echo ============================================================
echo.

pause
exit /b %EXIT_CODE%
