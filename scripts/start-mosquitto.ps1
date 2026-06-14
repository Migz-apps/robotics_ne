# Starts project Mosquitto (works without fixing Windows service / admin)
$root = Split-Path $PSScriptRoot -Parent
$conf = Join-Path $root "mosquitto-run.conf"
$exe = "C:\Program Files\Mosquitto\mosquitto.exe"

if (-not (Test-Path $exe)) {
    Write-Error "Install Mosquitto from https://mosquitto.org/download/"
}

$listening = Get-NetTCPConnection -LocalPort 1883 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' }

if ($listening) {
    $brokerPid = $listening[0].OwningProcess
    $proc = Get-Process -Id $brokerPid -ErrorAction SilentlyContinue
    Write-Host "MQTT broker already listening on port 1883 ($($proc.ProcessName) pid $brokerPid)"
    exit 0
}

Stop-Service mosquitto -ErrorAction SilentlyContinue
Start-Process -FilePath $exe -ArgumentList "-c", "`"$conf`"" -WindowStyle Hidden
Start-Sleep 2

New-NetFirewallRule -DisplayName "Mosquitto MQTT 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null

if ((Test-NetConnection 127.0.0.1 -Port 1883 -WarningAction SilentlyContinue).TcpTestSucceeded) {
    Write-Host "Mosquitto started on 0.0.0.0:1883"
} else {
    Write-Error "Failed to start Mosquitto on port 1883"
}
