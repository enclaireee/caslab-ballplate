# Ball and Plate

Control Lab Task 4: an ESP32 keeps a ball at the centre of a tilting plate, using a camera as the sensor and PID control. How it all fits together: [architecture.md](architecture.md).

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

- `p` = drag a box over the plate, then Enter (saved at once)
- threshold slider (in the `mask` window): move it until only the ball is white
- `q` = save the box and threshold to `vision/settings.json` and quit

`datalog.py` reads the settings once at startup, so stop it before changing them.

Mac: if the camera doesn't open, allow it in System Settings → Privacy & Security → Camera for the app you run it from (e.g. VS Code), then restart that app.

## 2. Run a log

```bash
.venv/bin/python esp/datalog.py run1
```

- Opens the camera and finds the ball in mm.
- Sends `pos x y` to the ESP32 once per frame, or `pos none` when the ball is hidden.
- Saves the data line the ESP32 sends back to `data_logging/runs/run1.csv`.
- Serves the dashboard's data at `http://127.0.0.1:8000`.

No name = a name made from the date and time. `Ctrl+C` stops it.

The setpoint is fixed at the plate centre, `(0, 0)`. The PID gains and the servo settings are constants at the top of `esp/esp.ino`; change them there and reflash the board.

## 3. Dashboard

Keep `datalog.py` running, and in a second terminal:

```bash
cd data_logging/dashboard
npm run dev
```

Then open `http://localhost:3000`.

The Live page reads the newest CSV every 0.5 s (the logger appends one line per frame). The Runs page opens any saved run.

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
No Serial Monitor needed: the plate sits flat for 2 s, then glides to the extreme
of each of the 8 directions (`PULSE_MIN`/`PULSE_MAX` per axis), back to flat in
between, holding each for 1 s, until you unplug the ESP32 or upload `esp.ino`.
It never goes outside `PULSE_MIN`..`PULSE_MAX`.

`esp/espreset/espreset.ino` is the smallest sketch: it sends both servos to the
centre pulse once, prints `# espreset: center pulse X=... Y=...`, and stops.
Upload it to level the plate after a test.

The settings at the top of `esp/esp.ino` (pins, servo pulses, direction, PID gains) are set for the standard rig. Check them on the bench:

| Setting | Where | How to check |
|---|---|---|
| Servo pins | `SERVO_X_PIN`, `SERVO_Y_PIN` | match your wiring |
| Servo level pulse | `PULSE_CENTER_X`, `PULSE_CENTER_Y` (1400 µs) | adjust each until its axis is level (phone level app) |
| Servo pulse scale | `SERVO_US_MIN`, `SERVO_US_MAX` (500 / 2500 µs) | the servo's full travel, only used by `attach()` |
| Servo pulse limits | `PULSE_MIN`, `PULSE_MAX` (1150 / 1950 µs) | just short of where the plate hits the frame |
| Servo direction | `SERVO_DIR_X`, `SERVO_DIR_Y` | tilt +5°: the ball must roll toward +x / +y |
| Pulse per plate degree | `PULSE_PER_DEG` | send centre + 100 µs, read the tilt, `100 / tilt` |
| PID gains | `KP`, `KI`, `KD` in `esp/esp.ino` | tune on the bench, then reflash |
| Camera number | `CAMERA` in `vision/vision.py` | 0 = built-in webcam, 1 = USB webcam or iPhone |
| Plate size | `PLATE_W_MM`, `PLATE_H_MM` in `vision/vision.py` | measure the plate inside the box with a ruler |
| Plate box + threshold | `vision/settings.json` | run `vision.py`, `p` and the slider, then `q` |

`PULSE_PER_DEG = 100` and the 250 × 250 mm plate are nominal values, not measured
yet. Every tilt limit and every mm value depends on them.

## Files

```
vision/vision.py     ball in the picture -> x, y mm
esp/esp.ino          ESP32: settings, setup, loop, pos command
esp/pid.ino          PID maths for one axis
esp/plate.ino        tilt angle -> servo pulse
esp/pid.h            the Axis and PID types
esp/esptest/         servo test sketch: every extreme tilt, then flat, forever
esp/esptest2/        servo test from the Serial Monitor: test X+ / X+Y- / stop / flat
esp/espreset/        reset sketch: plate level, then stops
esp/datalog.py       laptop: camera -> ESP32, save CSV, serve the dashboard
esp/esp_usb.py       real ESP32 over USB
data_logging/runs/   one CSV per run
data_logging/dashboard/  Next.js dashboard (Live, Runs, Setup)
analysis/            analysis reports and the evidence behind them
```
