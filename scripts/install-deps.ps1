# venv already has packages — no install needed.
. "$PSScriptRoot\venv-path.ps1"
Write-Host "Using existing venv at $ProjectVenv" -ForegroundColor Green
& $ProjectPython -c "import cv2, mediapipe, onnxruntime, paho.mqtt.client, pandas; print('All packages OK')"
