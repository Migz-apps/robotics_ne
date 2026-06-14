# Sync ESP8266 MQTT broker host from config.json (public broker OR PC LAN IP).
$root = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $root "config.json"
$projectIno = Join-Path $root "esp8266\vision_servo\vision_servo.ino"

$cfg = Get-Content $configPath -Raw | ConvertFrom-Json

$wifiIp = (
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.InterfaceAlias -match 'Wi-Fi' -and
        $_.IPAddress -notmatch '^169\.' -and
        $_.IPAddress -notmatch '^172\.(1[6-9]|2[0-9]|3[01])\.' -and
        $_.IPAddress -notmatch '^127\.'
    } |
    Select-Object -First 1
).IPAddress

if ($cfg.mqtt_use_lan) {
    if (-not $wifiIp) {
        Write-Error "mqtt_use_lan=true but no Wi-Fi IPv4 found."
    }
    $brokerHost = $wifiIp
    Write-Host "MQTT mode: LAN ($brokerHost)" -ForegroundColor Cyan
} else {
    $brokerHost = $cfg.mqtt_broker
    Write-Host "MQTT mode: public broker ($brokerHost)" -ForegroundColor Cyan
    if ($wifiIp) { Write-Host "PC Wi-Fi IP: $wifiIp (not used for ESP while mqtt_use_lan=false)" -ForegroundColor DarkGray }
}

$cfg.pc_lan_ip = if ($wifiIp) { $wifiIp } else { $cfg.pc_lan_ip }
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($configPath, ($cfg | ConvertTo-Json -Depth 10), $utf8NoBom)

$ino = Get-Content $projectIno -Raw
$ino = $ino -replace 'const char\* mqtt_server = "[^"]+";', "const char* mqtt_server = `"$brokerHost`";"
[System.IO.File]::WriteAllText($projectIno, $ino, $utf8NoBom)

Write-Host "Updated ESP mqtt_server -> $brokerHost`:$($cfg.mqtt_port)" -ForegroundColor Green
