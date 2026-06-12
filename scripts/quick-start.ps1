. "$PSScriptRoot\venv-path.ps1"
if (-not (Test-Path $ProjectPython)) { & "$PSScriptRoot\install-deps.ps1" }
& "$PSScriptRoot\start-system.ps1"
Write-Host "`nNext: .\scripts\enroll.ps1 -Name Miguel" -ForegroundColor Green
Write-Host "Then: .\scripts\run-vision.ps1 -Name Miguel" -ForegroundColor Green
