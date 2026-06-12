# Step-by-step: run and test lock + follow

Use **3 terminals** (or more) on Windows. Project root:

`C:\Users\RCA\Desktop\tempula\robotics_ne`

---

## Before you start (one-time)

| Item | What you need |
|------|----------------|
| ESP8266 | USB to PC, servo on **D5**, camera mounted on servo |
| Wi-Fi | ESP uses `kobbie-mainoo` (in firmware) |
| PC IP | `192.168.0.188` in `config.json` — ESP MQTT must point here |
| Face enrolled | `data/db/face_db.npz` with your name (e.g. Miguel) |
| Python | Use **`venv`** only |

---

## Phase 1 — Flash the ESP8266 (CLI)

### 1. Plug in the ESP8266

Connect USB. Note the COM port (often **COM3**).

### 2. Open PowerShell in the project folder

```powershell
cd C:\Users\RCA\Desktop\tempula\robotics_ne
```

### 3. Flash with arduino-cli

```powershell
.\scripts\flash-esp8266.ps1
```

If auto-detect fails:

```powershell
.\scripts\flash-esp8266.ps1 -Port COM3
```

This will:

1. Compile `C:\Users\RCA\Downloads\vision_servo`
2. Upload to the board
3. Open serial monitor at **115200 baud**

### 4. Confirm ESP is online (serial monitor)

You should see something like:

- WiFi connected
- MQTT connected to `192.168.0.188:1883`
- Subscribed to `vision/team313/movement`

Press **Ctrl+C** to leave the monitor when done.

**If CLI flash fails:** use Arduino IDE → open `C:\Users\RCA\Downloads\vision_servo\vision_servo.ino` → Board: **NodeMCU 1.0** → Upload → Serial Monitor 115200.

---

## Phase 2 — Enroll your face (once per person)

Skip if Miguel (or your name) is already in the database.

### 1. Stop the servo (so it doesn’t move during enrollment)

```powershell
cd C:\Users\RCA\Desktop\tempula\robotics_ne
.\scripts\stop-servo.ps1
```

### 2. Activate venv and enroll

```powershell
.\venv\Scripts\Activate.ps1
.\scripts\enroll.ps1 -Name Miguel
```

### 3. In the enrollment window

- Sit in front of the **overhead camera** (camera index **1** in config).
- Press **SPACE** at least **10 times** (different angles).
- Press **S** to save.
- Press **Q** to quit.

You should see: `data/db/face_db.npz` updated.

---

## Phase 3 — Start the PC services

### Terminal 1 — Mosquitto + backend + dashboard

```powershell
cd C:\Users\RCA\Desktop\tempula\robotics_ne
.\scripts\start-system.ps1
```

This starts:

- **Mosquitto** on `localhost:1883`
- **Backend** in a new window
- **Dashboard** at http://localhost:8080

Leave this running.

### Optional — check dashboard

Open http://localhost:8080 in a browser. You should see MQTT status updates when the vision node runs.

---

## Phase 4 — Run follow + lock vision node

Use the **new follow module** (search when lost, stop when centered, follow when moving).

### Terminal 2 — Follow-track vision

```powershell
cd C:\Users\RCA\Desktop\tempula\robotics_ne
.\venv\Scripts\Activate.ps1
.\scripts\run-follow-vision.ps1 -Name Miguel
```

Or directly:

```powershell
python -m src.follow_track.vision_node --name Miguel
```

A window titled **"Follow Track (Speaker Lock)"** opens.

---

## Phase 5 — Test locking, following, and re-acquire

### Test 1 — Initial lock (SEARCHING → LOCKED)

1. Sit in front of the camera.
2. On screen you should see **SCAN: Miguel** (orange).
3. When your face matches the enrolled name:
   - Green box around your face
   - Label **SPEAKER: Miguel**
   - Status **LOCKED**
4. In Terminal 2 you should see MQTT like:
   - `STOPPED` when your face is centered
   - `MOVE_LEFT` / `MOVE_RIGHT` when off-center
5. Servo should **pan to keep you centered**.

### Test 2 — Follow when you move

1. While locked, **move slowly left or right**.
2. Expect:
   - Green box stays on you
   - Commands alternate `MOVE_LEFT` / `MOVE_RIGHT`
   - Servo follows you
3. When you stop in the center:
   - Command becomes **`STOPPED`**
   - Servo holds position on your face

### Test 3 — Lose face → search → re-lock (REACQUIRING)

1. While locked, **step out of frame** or turn away quickly.
2. Expect:
   - **LOCKED | LOST** counter on screen
   - Phase **REACQUIRING**
   - MQTT **`SCAN`** — servo sweeps left/right searching
3. **Come back into view** (same enrolled person).
4. Expect:
   - Green box returns
   - **LOCK_ACQUIRED** in logs
   - **`STOPPED`** when centered, then follow again when you move

### Test 4 — Ignore other people

1. Have someone else stand in frame (not enrolled).
2. They should get an **ignored** box (yellow/gray), not green.
3. Servo should **not** lock onto them.

### Test 5 — Stop everything

- Press **Q** in the vision window to quit.
- Or run:

```powershell
.\scripts\stop-servo.ps1
```

---

## What to watch (quick checklist)

| Check | Pass? |
|-------|-------|
| ESP serial: WiFi + MQTT OK | ☐ |
| Dashboard shows movement updates | ☐ |
| Only enrolled person = green box | ☐ |
| Move left/right → servo follows | ☐ |
| Step out → `SCAN` sweeps | ☐ |
| Return → re-locks and stops on face | ☐ |
| `logs\operations_*.csv` has rows | ☐ |
| `logs\Miguel_actions_*.txt` has LOCK_ACQUIRED | ☐ |

---

## Terminal layout (recommended)

```
Terminal 1:  .\scripts\start-system.ps1          (Mosquitto + backend)
Terminal 2:  .\scripts\run-follow-vision.ps1 -Name Miguel   (camera + AI + MQTT)
ESP8266:     Already running from flash (USB power + WiFi)
Browser:     http://localhost:8080               (optional dashboard)
```

---

## Optional — test lock only (no servo)

Face lock UI without MQTT motor commands:

```powershell
.\venv\Scripts\Activate.ps1
python -m src.face_locking --name Miguel
```

---

## Optional — default vision node (old behavior)

If you want the original node instead of follow-track:

```powershell
.\scripts\run-vision.ps1 -Name Miguel
```

For lock + search + follow, use **`run-follow-vision.ps1`**.

---

## Common issues

| Problem | Fix |
|---------|-----|
| ESP won’t connect MQTT | PC and ESP on same Wi-Fi; broker IP = `192.168.0.188` in `.ino` |
| No camera | Try `--camera-index 0` or check `camera_index` in `config.json` |
| Servo moves during enroll | Run `.\scripts\stop-servo.ps1` first |
| “Face DB not found” | Run enroll again: `.\scripts\enroll.ps1 -Name Miguel` |
| COM port busy | Close Arduino Serial Monitor, then re-flash |
