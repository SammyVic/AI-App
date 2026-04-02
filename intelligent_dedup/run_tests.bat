@echo off
REM =============================================================================
REM Intelligent Duplicate Finder - Full Test & Coverage Runner (batch)
REM =============================================================================
REM Runs ALL test files in tests/ and saves per-run artifacts to
REM coverage_history\<timestamp>\ then opens the history dashboard.
REM =============================================================================

set VENV_PYTHON=.\.venv\Scripts\python.exe

if not exist %VENV_PYTHON% (
    echo [ERROR] Virtual environment not found at .venv
    echo         Please run:  python -m venv .venv  and install requirements.
    exit /b 1
)

REM Build a timestamp string for this run
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set TIMESTAMP=%DT:~0,4%-%DT:~4,2%-%DT:~6,2%_%DT:~8,2%-%DT:~10,2%-%DT:~12,2%

set HIST_ROOT=coverage_history
set RUN_DIR=%HIST_ROOT%\%TIMESTAMP%
set HTMLCOV=%RUN_DIR%\htmlcov

if not exist %RUN_DIR% mkdir %RUN_DIR%

echo.
echo ============================================================
echo   Intelligent Dedup - Full Test and Coverage Suite
echo   Run: %TIMESTAMP%
echo ============================================================
echo.

REM Run pytest with per-run artifacts
%VENV_PYTHON% -m pytest ^
    tests/ ^
    -v ^
    --tb=short ^
    --cov=app ^
    --cov=cli ^
    --cov-branch ^
    --cov-report=term-missing ^
    --cov-report=html:%HTMLCOV% ^
    --cov-report=json:%RUN_DIR%\coverage.json ^
    --junitxml=%RUN_DIR%\junit.xml

set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE%==0 (
    echo [PASS] All tests passed.
) else (
    echo [FAIL] One or more tests failed. Exit code: %EXIT_CODE%
)

REM Write a minimal meta.json (PowerShell version writes full JSON)
REM For the dashboard we need at minimum the timestamp field
echo {"timestamp":"%TIMESTAMP%","exit_code":%EXIT_CODE%} > %RUN_DIR%\meta.json

REM Regenerate dashboard and open it
echo.
echo [INFO] Generating coverage dashboard ...
%VENV_PYTHON% generate_coverage_dashboard.py --open

echo.
echo ============================================================
echo   Coverage HTML (this run):  %HTMLCOV%\index.html
echo   Dashboard (all runs)    :  coverage_history\index.html
echo ============================================================
echo.

pause
exit /b %EXIT_CODE%
