# Start MQTT broker + backend for testing
$root = Split-Path $PSScriptRoot -Parent

Write-Host "=== Starting Mosquitto ===" -ForegroundColor Cyan
& "$PSScriptRoot\start-mosquitto.ps1"

Write-Host "`n=== Starting backend (new window) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; npm start"

Write-Host "`n=== Ready ===" -ForegroundColor Green
Write-Host "1. Dashboard: http://localhost:8080"
Write-Host "2. Enroll: cd '$root'; .\scripts\enroll.ps1 -Name YOUR_NAME"
Write-Host "3. Vision: cd '$root'; .\scripts\run-vision.ps1 -Name YOUR_NAME"
Write-Host "4. ESP8266 MQTT broker IP must be: 192.168.0.188"
