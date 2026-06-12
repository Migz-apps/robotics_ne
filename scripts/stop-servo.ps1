. "$PSScriptRoot\venv-path.ps1"
& $ProjectPython -c "import paho.mqtt.client as m; c=m.Client(); c.connect('localhost',1883); c.publish('vision/team313/movement','{\"status\":\"STOPPED\"}'); c.disconnect(); print('STOP sent')"
