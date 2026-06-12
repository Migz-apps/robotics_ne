# Registers your local ESP8266 package (Downloads) with Arduino IDE 2
# No Boards Manager download needed.
# Run once:
#   cd C:\Users\RCA\Desktop\tempula\robotics_ne\scripts
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\link-esp8266-arduino.ps1

$src = "C:\Users\RCA\Downloads\esp8266"
$dest = "$env:LOCALAPPDATA\Arduino15\packages\esp8266"

if (-not (Test-Path "$src\hardware\esp8266\3.1.2\boards.txt")) {
    Write-Error "ESP8266 core not found at $src"
}

New-Item -ItemType Directory -Path "$env:LOCALAPPDATA\Arduino15\packages" -Force | Out-Null

if (Test-Path $dest) {
    $item = Get-Item $dest -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Remove-Item $dest -Force
    } elseif (Test-Path "$dest\hardware\esp8266\3.1.2\boards.txt") {
        Write-Host "ESP8266 already registered at $dest"
        exit 0
    } else {
        Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
}

cmd /c mklink /J "$dest" "$src" | Out-Null
if (-not (Test-Path "$dest\hardware\esp8266\3.1.2\boards.txt")) {
    Write-Error "Link failed. Try running PowerShell as Administrator."
}

Write-Host "OK: Arduino IDE will use $src"
Write-Host "Restart Arduino IDE, then:"
Write-Host "  Tools -> Board -> esp8266 -> NodeMCU 1.0 (ESP-12E Module)"
