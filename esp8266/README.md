# ESP8266 Servo Controller

Firmware subscribes to `vision/team313/movement` and drives an SG90 servo on **D5 (GPIO14)**.

## Flash options

### Arduino IDE (or Cursor + Arduino extension)

1. Install the **Arduino** extension in Cursor (recommended in `.vscode/extensions.json`).
2. Open `esp8266/vision_servo/vision_servo.ino`.
3. Install board support: **ESP8266 by ESP8266 Community**.
4. Install libraries: **PubSubClient**, **Servo**.
5. Edit Wi-Fi SSID/password and MQTT broker IP in the sketch.
6. Select board **NodeMCU 1.0 (ESP-12E Module)** and upload.

### PlatformIO (recommended in Cursor)

1. Install the **PlatformIO IDE** extension in Cursor.
2. Open the `esp8266/` folder.
3. Edit Wi-Fi/MQTT settings in `src/main.cpp`.
4. Run **Upload** from the PlatformIO toolbar, or:
   ```bash
   pio run -t upload
   pio device monitor
   ```

## Wiring (SG90)

| Servo | ESP8266 |
|-------|---------|
| Signal (orange) | D5 (GPIO14) |
| VCC (red) | VIN (5 V supply — use external USB/power, not 3.3 V only) |
| GND (brown) | GND |

## Accepted MQTT commands

| Status | Servo action |
|--------|----------------|
| `MOVE_LEFT` / `MOVED_LEFT` / `LEFT` | Pan left |
| `MOVE_RIGHT` / `MOVED_RIGHT` / `RIGHT` | Pan right |
| `STOPPED` / `STOP` / `CENTERED` | Hold position |
| `SCAN` / `NO_FACE` / `OUT_OF_FRAME` | Horizontal search sweep |

> **Note:** `esp8266/main.py` (MicroPython) is deprecated. Use the Arduino/PlatformIO firmware above.
