# run.ps1
$ErrorActionPreference = "Continue"

# Change directory to the location of this script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Starting Intelligent Dedup..." -ForegroundColor Cyan

# Check if the virtual environment exists and activate it
$venvPath = Join-Path $ScriptDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    . $venvPath
} else {
    Write-Host "Warning: Virtual environment not found at .venv. Proceeding with system python..." -ForegroundColor Yellow
}

# Launch the application
Write-Host "Launching main.py..." -ForegroundColor Cyan
python main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nApplication exited with an error code $LASTEXITCODE." -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
