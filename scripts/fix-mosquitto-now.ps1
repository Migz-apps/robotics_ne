# Quick fix — run as Administrator (one time)
$mainConf = "C:\Program Files\Mosquitto\mosquitto.conf"
$c = Get-Content $mainConf -Raw
$c = $c -replace "`r?`ninclude_file robotics_ne.conf`r?`n?", "`n"
if ($c -notmatch "listener 1883 0\.0\.0\.0") {
    $c = $c.TrimEnd() + "`r`nlistener 1883 0.0.0.0`r`nallow_anonymous true`r`n"
}
Set-Content $mainConf $c -Encoding UTF8
Restart-Service mosquitto
Start-Sleep 2
Get-Service mosquitto
netstat -an | Select-String ":1883"
