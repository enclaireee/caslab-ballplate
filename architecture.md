# Ball and Plate: Architecture

Control Lab Task 4. Keep the ball at a setpoint on a tilting plate. Code is written to be easy for a beginner to read and to explain to the aslab.

## The whole system

```
 camera ──picture──> laptop: vision finds ball -> x,y mm
                        │  ^
               "pos x y" │  │ data lines (CSV text)
                        v  │
                      ESP32: PID ──angle──> 2 servos ──tilt──> plate ──> ball moves
                                                                          │
 camera sees the ball again <─────────────────────────────────────────────┘

 laptop: datalog.py ──saves──> data_logging/runs/*.csv
              │
              └──web server (127.0.0.1:8000)──> Next.js dashboard (localhost:3000)
```

- **Sensor:** webcam straight above the plate. **Black plate, white ball.** The laptop finds the ball.
- **Actuator:** 2 servos (MG90S), one for the X axis and one for Y.
- **Controller:** PID per axis, running **on the ESP32** (the laptop only measures, logs and shows).
- **Data logging:** the ESP32 prints one line per sample. `datalog.py` saves the lines to CSV and serves them to the dashboard.
- **Dashboard:** a Next.js website. The Live page shows the ball as it moves. The Runs page opens a saved run and calculates the step response numbers.

| Assignment requirement | Covered by |
|---|---|
| ESP32 + sensor + actuator + logging | ESP32, camera, servos, `esp/datalog.py` |
| Closed loop, not on/off | PID |
| Continuous variable | ball position in mm |
| Step response from logged data | nudge the ball off the setpoint, save the CSV, read the response on the Runs page |

## Folders

```
vision/              find the ball (Python + OpenCV)
  vision.py          picture -> ball x, y in mm; also imported by datalog.py
  settings.json      plate box, corners and threshold, written when you press q
esp/                 everything that talks to the ESP32
  esp.ino            ESP32 code: setup(), loop(), settings at the top, pos command
  pid.ino            PID math for one axis
  plate.ino          tilt angle -> servo pulse
  pid.h              the Axis and PID types the two files share
  datalog.py         laptop: camera -> pos -> ESP32, save CSV, serve the dashboard
  esp_usb.py         real ESP32 over USB: sendLine() + readLine()
  esptest/           servo test sketch
  espreset/          plate-level reset sketch
data_logging/        logged data and the website
  runs/              saved CSV files, one per run (made by datalog.py)
  dashboard/         Next.js dashboard: Live page (/) + Runs page (/runs) + Setup
analysis/            analysis reports and the evidence behind them
```

## Vision (how the ball is found)

1. Cut the picture to the plate area (ignore everything outside).
2. Grayscale, light blur, then threshold: bright pixels become white, the rest black.
3. Biggest white blob = ball. Too small = noise, so "no ball".
4. Blob centre in pixels -> mm. (0,0) is the plate centre, x goes right, y goes up.

The plate corners are four points, clockwise from top-left. The default is the plate box; dragging a new box with `p` replaces them. `updatePerspective()` builds the pixel-to-mm matrix once, when the corners or plate size change, and `toMm()` reuses it for every frame.

## ESP32 loop

The camera decides the pace. Every time a `pos` line arrives from the laptop (one per camera frame, ~30 per second), the ESP32 does **one control step**:

1. `dt` = seconds since the previous accepted `pos` line (from `millis()`). After boot, a timeout or `pos none`, `dt = 0`.
2. `error = setpoint - position`, for each axis.
3. `speed` = change in position divided by `dt`, but only when `0 < dt <= 0.2 s` and a previous position exists. Otherwise `speed = 0`, so a gap or a setpoint jump never kicks the plate.
4. `u = kp*error + ki*integral - kd*speed`, limited per axis to the tilt the servo pulse window allows (`setTiltLimits`, −5.5°..+2.5° now).
   - The integral only changes when `ki != 0` and `dt` is normal.
   - The integral stops growing while `u` is at the limit (anti-windup).
5. Convert tilt to a servo pulse: `center + direction * pulse_per_deg * u` microseconds, kept inside `PULSE_MIN`..`PULSE_MAX`.
6. Print one data line.

Running PID only when a new position arrives (instead of on a fixed 100 Hz timer) means the derivative never sees the same position twice, so it doesn't spike.

Safety: `hold()` moves both servos to level, calls `resetPID()` (integral 0, previous position `NAN`) and clears the `dt` reference. It runs at boot, on `pos none`, and when no `pos` line came for 500 ms. The ESP32 then prints a `#` message instead of a data line, so `datalog.py` is never left waiting.

## Servo pulse and tilt (source of truth)

Every piece of code that turns a tilt into a servo pulse follows these rules. Change them here first, then in the code.

| Name | Value | Meaning |
|---|---|---|
| `SERVO_US_MIN`..`SERVO_US_MAX` | 500..2500 µs | The servo's own full scale. Only passed to `attach()`. |
| `PULSE_MIN`..`PULSE_MAX` | 1150..1950 µs | Our limit (the plate's mechanical stops), enforced in our code. Never send a pulse outside it. |
| `PULSE_CENTER_X/Y` | 1400 µs | Plate level. Not the middle of 1150..1950. |
| `PULSE_PER_DEG` | 100.0 µs/° (test value, not measured yet) | Pulse per degree of **plate** tilt (not servo degrees). |
| `SERVO_DIR_X/Y` | -1 | Sign: +tilt must push the ball towards +x / +y. |

- **Pulses are absolute µs.** ESP32Servo's `writeMicroseconds()` sends the value as-is. The `attach(min, max)` range is not a scale for it, only a clamp. Never use `write(angle)`.
- **Timer setup is identical in all three sketches:** `ESP32PWM::allocateTimer(0/1)`, `setPeriodHertz(50)`, `attach()`, then `setTimerWidth(16)`. The width must come after `attach()`, because `attach()` resets it. 16-bit gives 0.3 µs pulse steps; the 10-bit default rounds small PID corrections away.
- **Tilt -> pulse:** `pulse = center + dir * PULSE_PER_DEG * tilt`, clamped to `PULSE_MIN..PULSE_MAX` (`tiltToPulse`, `esp/plate.ino`).
- **Tilt limits are per axis and not symmetric.** `setTiltLimits()` (`esp/plate.ino`) inverts the line above at both pulse limits and is the only place that writes `pid.x/y.tiltMin/tiltMax`. Now: (1150-1400)/(-100) = +2.5° and (1950-1400)/(-100) = -5.5°, so -5.5..+2.5°. The PID clamps to this range and freezes its integral there (`axisStep`, `esp/pid.ino`). Never hard-code a tilt limit: it changes with every center, window, `PULSE_PER_DEG` or `SERVO_DIR` value.
- **The PID works in plate degrees and mm.** KP is °/mm, so its real effect depends on `PULSE_PER_DEG` (servo side) and on `PLATE_W_MM`/`PLATE_H_MM` against the plate box in `vision/settings.json` (camera side). If either is off, the gains are off.
- **Copies that must match `esp/esp.ino`:** `esp/esptest/esptest.ino`, `esp/esptest2/esptest2.ino` and `esp/espreset/espreset.ino` (pins, scale, window, centers). Update them in the same change.

## Serial format (115200 baud, plain text)

Laptop to ESP32:

```
pos 12.5 -3.0    ball position in mm (every camera frame)
pos none         ball not found
```

There are no other commands. The setpoint and the PID gains are constants at the top of `esp/esp.ino`.

ESP32 to laptop, one CSV line per sample:

```
t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg
12340,12.5,-3.0,0.0,0.0,-1.20,0.40
```

Lines starting with `#` are messages (boot, no ball, timeout). The laptop prints them but does not save them.

## datalog.py (the backend)

Only one program can open the ESP32's USB port, so `datalog.py` is the only program that talks to it. Each loop:

1. take one camera frame, find the ball in mm,
2. send `pos x y` (or `pos none`) through `Esp.sendLine()`,
3. read the reply with `Esp.readLine()`; print any `#` messages, and save data lines to `data_logging/runs/<name>.csv`.

`readReply()` keeps reading until it sees a data line, `# no ball`, or nothing at all, so a skipped message cannot leave the laptop one line behind. `isDataLine()` accepts only 7 fields that all convert with `float()`.

`esp_usb.py` gives it three functions: `sendLine(text)`, `readLine()` and `clearBuffer()`. `readLine()` strips NUL bytes and decodes with `errors="ignore"`; `clearBuffer()` throws away startup noise after the camera and web server are ready.

```bash
.venv\Scripts\python esp\datalog.py run1       # real ESP32 + camera
```

On Windows, `vision.py` opens the camera with DirectShow (`cv2.CAP_DSHOW`), because the default backend queues up to 3 frames, which adds control delay.

Web server (Python built-in `http.server`, only reachable from this laptop):

| Address | Gives |
|---|---|
| `http://127.0.0.1:8000/runs` | list of saved CSV names, oldest first: `["run1.csv", "run2.csv"]` |
| `http://127.0.0.1:8000/runs/run1.csv` | one saved CSV file |

Every answer has `Access-Control-Allow-Origin: *`, because the browser blocks a page on port 3000 from reading port 8000 otherwise.

## Dashboard (Next.js, `data_logging/dashboard/`)

- **Live page (`/`):** polls `/runs` and the newest CSV every 500 ms with `useLiveData`. It keeps the last 500 samples (~10 s) and draws the plate view, the tilt gauge, and x vs. setpoint and y vs. setpoint. If no new CSV body arrives for 2 s, the status pill falls back to "No signal" (the logger stopped).
- **Runs page (`/runs`):** loads `/runs`, you pick one, loads the CSV, finds where the setpoint jumps, and shows the chart and the step response numbers:

| Number | Meaning |
|---|---|
| Rise time | time from 10% to 90% of the jump |
| Overshoot | how far past the setpoint it goes, in % of the jump |
| Settling time | time until it stays within ±5% of the jump |
| Steady-state error | setpoint minus the average position over the last 1 s |

`parseCsv()` lives in `app/config.ts` and is shared by both pages. It strips NUL bytes, skips header and `#` lines, and keeps only rows of 7 finite numbers.

The plate drawing and the gauge use `PLATE_HALF_MM = 125` and `TILT_DISPLAY_MAX_DEG = 6` from `app/config.ts`. `PLATE_HALF_MM` must equal half of `PLATE_W_MM` / `PLATE_H_MM` in `vision/vision.py`; the two files describe the same physical plate.

## How to run (laptop)

- `.venv\Scripts\python vision\vision.py`: camera only, shows where the ball is. Use it to set up the camera.
- `.venv\Scripts\python esp\datalog.py run1`: logs to `data_logging/runs/run1.csv` and starts the web server. Ctrl+C stops it.
- `npm run dev` in `data_logging/dashboard/`: the dashboard at `http://localhost:3000`.

Use the project's `.venv` Python (`.venv\Scripts\python ...`). Python libraries: `opencv-python`, `pyserial`. Nothing else.

## Bench calibration (values in `esp/esp.ino` and `vision/settings.json`)

| Setting | How to find it |
|---|---|
| Camera number (`CAMERA` in `vision.py`) | 0 = built-in webcam, 1 = USB webcam |
| Plate box in the picture | run `vision.py`, press `p`, drag a box over the plate (saved to `vision/settings.json` on `q`). Redo it after switching or moving the webcam: the file stores pixel positions from the old camera |
| Threshold | slider in `vision.py` until only the ball is white (saved on `q`) |
| Plate size (mm) | ruler; change `PLATE_W_MM` / `PLATE_H_MM` in `vision.py` |
| ESP32 USB port name | found automatically; pass `--port COM3` if the wrong one is picked (Device Manager → Ports (COM & LPT), or Arduino IDE → Tools → Port) |
| Servo pins (`SERVO_X_PIN`, `SERVO_Y_PIN`) | from your friend's wiring |
| Servo level pulses (`PULSE_CENTER_X`, `PULSE_CENTER_Y`, now 1400 µs) | adjust each until its axis is level (phone level app) |
| Servo pulse scale (`SERVO_US_MIN`, `SERVO_US_MAX`, 500 / 2500 µs) | the servo's full travel, only used by `attach()` |
| Servo pulse limits (`PULSE_MIN`, `PULSE_MAX`, now 1150 / 1950 µs) | just short of where the plate hits the frame |
| Servo direction (`SERVO_DIR_X`, `SERVO_DIR_Y`) | tilt +5°, the ball should roll toward +x / +y |
| Pulse per plate degree (`PULSE_PER_DEG`) | send centre + 100 µs, read the tilt, `100 / tilt` |

## Tuning

Start with `ki = 0`. Raise `kp` until the ball responds, then raise `kd` until it stops wobbling. The camera adds ~50–150 ms of delay, so expect to need more `kd` and a gentler `kp` than a delay-free model would suggest. Add a little `ki` only if the ball settles off target. The gains are constants at the top of `esp/esp.ino`; change them there and reflash the board.

## Step response proof

The firmware keeps the setpoint at the plate centre, `(0, 0)`. With the logger running and the ball settled, hold it by hand about 40 mm off centre, let go, and stop the logger after the ball settles. The position chart on the Runs page shows that release: how fast it returns, how far it overshoots and how long it takes to settle. Repeat three times per axis and keep the CSVs with the screenshots and metrics.

The step table itself only fills in when the setpoint changes inside a run (for example, an older run recorded with a movable setpoint). A current run has a constant setpoint.

## Backup plan

If the camera is too slow or unreliable, swap it for a resistive touch panel read by the ESP32. Only the sensor part changes. The ESP32 then runs PID on its own timer, and `datalog.py` and the dashboard stay the same.
