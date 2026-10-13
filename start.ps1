# EduEagle - Student Success & Intervention Orchestration Platform
# Startup script for Windows PowerShell

$ErrorActionPreference = "Stop"

$pythonPath = "C:\msys64\ucrt64\bin\python.exe"

if (-not (Test-Path $pythonPath)) {
    $found = where.exe python | Select-Object -First 1
    if ($found) {
        $pythonPath = $found
    } else {
        Write-Error "Python executable not found. Please ensure Python is installed."
        exit 1
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       EduEagle: Student Success & Intervention Engine    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Using Python runtime at: $pythonPath" -ForegroundColor DarkGray

# Check database
if (-not (Test-Path "edueagle.db")) {
    Write-Host "Initializing database & seeding realistic university cohort data..." -ForegroundColor Yellow
    & $pythonPath database.py
}

Write-Host "`nLaunching web server on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to terminate the server anytime.`n" -ForegroundColor DarkYellow

& $pythonPath server.py

