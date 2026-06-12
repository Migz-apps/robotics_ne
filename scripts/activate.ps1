. "$PSScriptRoot\venv-path.ps1"
if (-not (Test-Path $ProjectPython)) {
    Write-Error "venv missing. Run: python -m venv venv"
}
. $ProjectActivate
Write-Host "Using venv (Python)" -ForegroundColor Green
