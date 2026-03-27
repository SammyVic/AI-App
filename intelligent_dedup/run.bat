@echo off
TITLE Intelligent Dedup Application Launch

REM Change directory to the location of this script
cd /d "%~dp0"

echo Starting Intelligent Dedup...

REM Check if the virtual environment exists and activate it
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ".venv\Scripts\activate.bat"
) else (
    echo Warning: Virtual environment not found at .venv. Proceeding with system python...
)

REM Launch the application
echo Launching main.py...
python main.py

REM Keep the window open if there's an error
if %errorlevel% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
