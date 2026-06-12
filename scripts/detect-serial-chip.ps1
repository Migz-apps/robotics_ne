# Detect USB-serial chip (CH340 vs CP210x) and list COM ports.
# Run with ESP8266 plugged in via a DATA cable.

Write-Host "`n=== COM ports ===" -ForegroundColor Cyan
$ports = [System.IO.Ports.SerialPort]::getportnames()
if ($ports.Count -eq 0) { Write-Host "  (none)" -ForegroundColor Yellow }
else { $ports | ForEach-Object { Write-Host "  $_" } }

Write-Host "`n=== USB serial devices ===" -ForegroundColor Cyan
$patterns = @(
    @{ Name = "CH340 / CH341 (WCH, most NodeMCU clones)"; Match = "1A86|CH340|CH341|wch" }
    @{ Name = "CP210x (Silicon Labs)"; Match = "10C4|CP210|Silicon" }
    @{ Name = "FTDI"; Match = "0403|FTDI" }
    @{ Name = "Descriptor failed (bad cable / no data / faulty board)"; Match = 'VID_0000&PID_0002|Descriptor Request Failed' }
)

$devices = Get-PnpDevice -ErrorAction SilentlyContinue |
    Where-Object { $_.InstanceId -match "USB\\" -or $_.FriendlyName -match "CH340|CP210|Serial|UART" }

$found = $false
foreach ($p in $patterns) {
    $hits = $devices | Where-Object {
        $_.InstanceId -match $p.Match -or $_.FriendlyName -match $p.Match
    }
    if ($hits) {
        $found = $true
        Write-Host "`n  $($p.Name):" -ForegroundColor Green
        $hits | ForEach-Object {
            Write-Host "    $($_.FriendlyName)  [$($_.Status)]"
            Write-Host "    $($_.InstanceId)"
        }
    }
}

if (-not $found) {
    Write-Host "  No CH340, CP210, or failed-descriptor device found." -ForegroundColor Yellow
    Write-Host "  Plug in the ESP8266 with a DATA cable and run this script again."
}

Write-Host "`n=== Installed drivers (serial) ===" -ForegroundColor Cyan
pnputil /enum-drivers 2>$null | Select-String -Pattern "CH340|CH341|wch|CP210|Silicon" -Context 0,1

Write-Host "`nChip guide:" -ForegroundColor Cyan
Write-Host "  CH340  -> VID 1A86  -> driver: wch.cn CH341SER (installed on this PC)"
Write-Host "  CP210x -> VID 10C4  -> driver: Silicon Labs CP210x (installed on this PC)"
Write-Host "  If you see 'Descriptor Request Failed', try another USB cable/port first.`n"
