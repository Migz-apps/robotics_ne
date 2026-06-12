# Run as Administrator:
#   cd C:\Users\RCA\Desktop\tempula\robotics_ne\scripts
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup-mosquitto-lan.ps1

$ErrorActionPreference = "Stop"
$mosquittoDir = "C:\Program Files\Mosquitto"
$mainConf = Join-Path $mosquittoDir "mosquitto.conf"

# Mosquitto 2.x does not support include_file — append LAN listener directly.
$content = Get-Content $mainConf -Raw
$content = $content -replace "`r?`ninclude_file robotics_ne.conf`r?`n?", "`n"

if ($content -notmatch "listener 1883 0\.0\.0\.0") {
    $content = $content.TrimEnd() + @"

# --- robotics_ne: allow ESP8266 on LAN ---
listener 1883 0.0.0.0
allow_anonymous true
"@
}

Set-Content -Path $mainConf -Value $content -Encoding UTF8

# Validate config before restart
& (Join-Path $mosquittoDir "mosquitto.exe") -c $mainConf -v 2>&1 | Select-Object -First 3
if ($LASTEXITCODE -ne 0) {
    Write-Error "mosquitto.conf failed validation. Fix manually before restarting."
}

Restart-Service mosquitto
Start-Sleep 2

New-NetFirewallRule -DisplayName "Mosquitto MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -ErrorAction SilentlyContinue | Out-Null

Write-Host "`nService:" (Get-Service mosquitto).Status
Write-Host "Listening ports:"
netstat -an | Select-String ":1883"
