$script:ProjectRoot = Split-Path $PSScriptRoot -Parent
$script:ProjectVenv = Join-Path $ProjectRoot "venv"
$script:ProjectPython = Join-Path $ProjectVenv "Scripts\python.exe"
$script:ProjectPip = Join-Path $ProjectVenv "Scripts\pip.exe"
$script:ProjectActivate = Join-Path $ProjectVenv "Scripts\Activate.ps1"
