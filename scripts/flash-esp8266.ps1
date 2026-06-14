# Flash ESP8266 without Arduino IDE GUI — uses arduino-cli
# Plug ESP8266 via USB first, then run from project root:
#   .\scripts\flash-esp8266.ps1
# Optional: .\scripts\flash-esp8266.ps1 -Port COM3

param([string]$Port = "")

$root = Split-Path $PSScriptRoot -Parent
& "$PSScriptRoot\sync-mqtt-ip.ps1"
& "$PSScriptRoot\start-mosquitto.ps1"
New-NetFirewallRule -DisplayName "Mosquitto MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null

$cli = Join-Path $root "tools\arduino-cli.exe"
$sketch = "C:\Users\RCA\Downloads\vision_servo"
$projectIno = Join-Path $root "esp8266\vision_servo\vision_servo.ino"
$downloadIno = Join-Path $sketch "vision_servo.ino"
if (Test-Path $projectIno) {
    Copy-Item $projectIno $downloadIno -Force
    Write-Host "Synced firmware: $projectIno -> $downloadIno" -ForegroundColor DarkGray
}
$fqbn = "esp8266:esp8266:nodemcuv2"
$data = "$env:LOCALAPPDATA\Arduino15"
& $cli config set directories.data $data 2>$null
& $cli config set directories.user "$data\libraries" 2>$null

if (-not (Test-Path $cli)) {
    Write-Error "arduino-cli not found. Run setup first."
}

if (-not $Port) {
    Write-Host "Detecting serial ports..."
    & $cli board list
    $boards = & $cli board list --format json 2>$null | ConvertFrom-Json
    $esp = $boards | Where-Object { $_.matching_boards -and $_.port.address -match '^COM' } | Select-Object -First 1
    if ($esp) { $Port = $esp.port.address }
}

if (-not $Port) {
    Write-Host "Plug in ESP8266 USB cable, then run again."
    Write-Host "Or specify port: .\scripts\flash-esp8266.ps1 -Port COM3"
    exit 1
}

Write-Host "Compiling $sketch ..."
& $cli compile --fqbn $fqbn $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Uploading to $Port ..."
& $cli upload -p $Port --fqbn $fqbn $sketch
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Upload complete." -ForegroundColor Green
Write-Host "Opening serial monitor (115200). Press Ctrl+C to stop."
& $cli monitor -p $Port -b $fqbn --config baudrate=115200
