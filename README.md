# Ball and Plate

Control Lab Task 4: an ESP32 keeps a ball at a setpoint on a tilting plate, using a camera as the sensor and PID control. How it all fits together: [architecture.md](architecture.md).

The whole loop:

```
camera -> laptop: find the ball in mm -> ESP32: PID per axis -> 2 servos -> plate -> ball moves
```

The laptop measures and logs. The ESP32 does the control. The dashboard shows both.

## Setup (once)

From the project folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd data_logging/dashboard && npm install && cd ../..
```

Run everything with `.venv/bin/python` (Homebrew Python blocks installing packages globally).

## 1. Vision: find the ball

```bash
.venv/bin/python vision/vision.py
```

- `p` = drag a box over the black plate, then Enter (saved at once; a running `datalog.py` picks it up)
- threshold slider (in the `mask` window): move it until only the ball is white
- `q` = save the settings (box + threshold) to `vision/settings.json` and quit

Mac: if the camera doesn't open, allow it in System Settings → Privacy & Security → Camera for the app you run it from (e.g. VS Code), then restart that app.

## 2. Run a log

Without hardware:

```bash
.venv/bin/python esp/datalog.py run1 --mock
```

With the real rig:

```bash
.venv/bin/python esp/datalog.py run1
```

- Saves to `data_logging/runs/run1.csv` (no name = a name with the date and time).
- Also starts the web server for the dashboard at `http://127.0.0.1:8000`.
- The real mode opens the camera, sends `pos x y` to the ESP32 once per frame,
  and saves the data line the ESP32 sends back. Its `datalog camera` window shows
  what the controller sees: the green circle must be on the ball.
- `Ctrl+C` stops it.

The fake ESP32 (`esp/mock.py`) runs the same PID as the firmware on a simulated
ball, so the logger and the dashboard can be tested with no hardware at all.

While the logger runs, a line you type in that terminal goes to the ESP32, so you
can move the setpoint or retune without stopping the run:

```
sp 50 0          setpoint to x=50 mm, y=0 mm
pid 0.074 0 0.025   set kp ki kd (both axes)
```

## 3. Dashboard

Keep `datalog.py` running, and in a second terminal:

```bash
cd data_logging/dashboard
npm run dev
```

Then open `http://localhost:3000`.

## 4. Flash the ESP32

Arduino IDE:

1. Board: **ESP32 Dev Module**. Install the `esp32` board package if it is missing.
2. Library: **ESP32Servo** (Library Manager → search `ESP32Servo`). The ESP32 core
   does not include `Servo.h`, this library provides it.
3. Open `esp/esp.ino`. The other three files (`pid.ino`, `plate.ino`, `pid.h`) open
   as tabs next to it; keep them in the same folder.
4. Choose the port under Tools → Port and press Upload.

Wiring: servo X signal → GPIO 2, servo Y signal → GPIO 4, servos on their own
5 V supply, grounds joined with the ESP32.

Servo test (before the real sketch): open `esp/esptest/esptest.ino` and upload it.
No Serial Monitor needed: the plate sits flat for 2 s, then both servos move in
smooth sine waves through `PULSE_MIN`..`PULSE_MAX` (X every 4 s, Y every 5 s, so the
plate tilts every way) until you unplug the ESP32 or upload `esp.ino`.
It never goes outside `PULSE_MIN`..`PULSE_MAX`.

The settings at the top of `esp/esp.ino` (pins, servo pulses, direction, PID gains) are set for the standard rig. Check them on the bench:

| Setting | Where | How to check |
|---|---|---|
| Servo pins | `SERVO_X_PIN`, `SERVO_Y_PIN` | match your wiring |
| Servo level pulse | `PULSE_CENTER_X`, `PULSE_CENTER_Y` (1400 µs) | adjust each until its axis is level (phone level app) |
| Servo pulse limits | `PULSE_MIN`, `PULSE_MAX` (1150 / 1950 µs) | just short of where the plate hits the frame |
| Servo direction | `SERVO_DIR_X`, `SERVO_DIR_Y` | tilt +5°: the ball must roll toward +x / +y |
| Pulse per plate degree | `PULSE_PER_DEG` | send centre + 100 µs, read the tilt, `100 / tilt` |
| PID gains | `KP`, `KI`, `KD` | tune with `pid kp ki kd` over serial |
| Camera number | `CAMERA` in `vision/vision.py` | 0 = built-in webcam, 1 = USB webcam or iPhone |
| Plate size | `PLATE_W_MM`, `PLATE_H_MM` in `vision/vision.py` | measure the plate inside the box with a ruler |
| Plate box + threshold | `vision/settings.json` | run `vision.py`, `p` and the slider, then `q` |

## Files

```
vision/vision.py     ball in the picture -> x, y mm
esp/esp.ino          ESP32: settings, setup, loop, serial commands
esp/pid.ino          PID maths for one axis
esp/plate.ino        tilt angle -> servo pulse
esp/pid.h            the Pid type
esp/esptest/         servo test sketch: sweep or hold a pulse from the Serial Monitor
esp/datalog.py       laptop: camera -> ESP32, save CSV, serve the dashboard
esp/esp_usb.py       real ESP32 over USB
esp/mock.py          fake ESP32, no hardware needed
esp/test_datalog.py  check that datalog.py stays in step with the ESP32
data_logging/runs/   one CSV per run
data_logging/dashboard/  Next.js dashboard (Live, Runs, Setup)
```
