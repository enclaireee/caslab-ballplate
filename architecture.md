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
- **Actuator:** 2 servos (MG996R), one for the X axis and one for Y.
- **Controller:** PID per axis, running **on the ESP32** (the laptop only measures, logs and shows).
- **Data logging:** the ESP32 prints one line per sample. `datalog.py` saves the lines to CSV and passes them on to the dashboard.
- **Dashboard:** a Next.js website. The live page shows the ball as it moves. The Runs page opens a saved run and calculates the step response numbers.

| Assignment requirement | Covered by |
|---|---|
| ESP32 + sensor + actuator + logging | ESP32, camera, servos, `esp/datalog.py` |
| Closed loop, not on/off | PID |
| Continuous variable | ball position in mm |
| Step response from logged data | change setpoint, save CSV, open it on the Runs page |

## Folders

```
vision/              find the ball (Python + OpenCV)
  vision.py          picture -> ball x, y in mm; also imported by datalog.py
  settings.json      plate box + threshold, written when you press q
esp/                 everything that talks to the ESP32
  esp.ino            ESP32 code: setup(), loop(), settings at the top, serial commands
  pid.ino            PID math for one axis
  plate.ino          tilt angle -> servo pulse
  pid.h              the Pid type the two files share
  datalog.py         laptop: camera -> pos -> ESP32, save CSV, serve the dashboard
  esp_usb.py         real ESP32 over USB: sendLine() + readLine()
  mock.py            fake ESP32 (simulated ball), same two functions, no hardware
data_logging/        logged data and the website
  runs/              saved CSV files, one per run (made by datalog.py)
  dashboard/         Next.js dashboard: Live page (/) + Runs page (/runs) + Setup
docs/                results for submission (CSVs, screenshots, metrics table)
```

## Vision (how the ball is found)

1. Cut the picture to the plate area (ignore everything outside).
2. Grayscale, light blur, then threshold: bright pixels become white, the rest black.
3. Biggest white blob = ball. Too small = noise, so "no ball".
4. Blob centre in pixels → mm. (0,0) is the plate centre, x goes right, y goes up.

## ESP32 loop

The camera decides the pace. Every time a `pos` line arrives from the laptop (one per camera frame, ~30 per second), the ESP32 does **one control step**:

1. `dt` = time since the last `pos` line (from `millis()`). The first line uses 20 ms.
2. `error = setpoint - position`, for each axis.
3. `u = kp*error + ki*integral - kd*speed`, limited to ±15°.
   - `speed` is the change in position divided by `dt` (not the change in error), so a setpoint jump doesn't kick the plate.
   - The integral stops growing while `u` is at the limit (anti-windup).
4. Convert tilt to servo angle: `center + direction * ratio * u`, limited to a safe range, then send it as a pulse in microseconds (about 0.1 servo degree per step, not whole degrees).
5. Print one data line.

Running PID only when a new position arrives (instead of on a fixed 100 Hz timer) means the derivative never sees the same position twice, so it doesn't spike.

Safety: if the laptop says `pos none`, or no `pos` line came for 200 ms, put the plate flat and reset the integral. The ESP32 then prints a `#` message instead of a data line, so `datalog.py` is never left waiting.

## Serial format (115200 baud, plain text)

Laptop to ESP32:

```
pos 12.5 -3.0    ball position in mm (every camera frame)
pos none         ball not found
sp 50 0          set setpoint to x=50 mm, y=0 mm
pid 0.4 0 0.15   set kp ki kd (both axes)
```

ESP32 to laptop, one CSV line per sample:

```
t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg
12340,12.5,-3.0,0.0,0.0,-1.2,0.4
```

Lines starting with `#` are messages (boot, no ball, timeout). The laptop prints them but does not save them.

## datalog.py (the backend)

Only one program can open the ESP32's USB port, so `datalog.py` is the only program that talks to it. Each loop:

1. take one camera frame, find the ball in mm,
2. send `pos x y` (or `pos none`) through `Esp().sendLine()`,
3. read the reply with `Esp().readLine()`,
4. print it, and if it is a data line: save it to `data_logging/runs/<name>.csv` and hand it to the web server.

A line you type in the logger's terminal is passed to the ESP32 unchanged, which is how you send `sp` and `pid` during a run.

The ESP32 and the camera are picked by one flag, so the same code runs with or without hardware:

```bash
.venv/bin/python esp/datalog.py run1           # real ESP32 + camera
.venv/bin/python esp/datalog.py run1 --mock    # fake ESP32, no camera
```

`esp_usb.py` and `mock.py` both have exactly `sendLine(text)` and `readLine()`, so step 3 and 4 do not know which one is in use.

Web server (Python built-in `http.server`, only reachable from this laptop):

| Address | Gives |
|---|---|
| `http://127.0.0.1:8000/stream` | live data (Server-Sent Events), one JSON sample per message: `{"t_ms": 1120, "x_mm": 0.4, ...}` |
| `http://127.0.0.1:8000/runs` | list of saved CSV names: `["run1.csv", "run2.csv"]` |
| `http://127.0.0.1:8000/runs/run1.csv` | one saved CSV file |

Every answer has `Access-Control-Allow-Origin: *`, because the browser blocks a page on port 3000 from reading port 8000 otherwise.

## Dashboard (Next.js, `data_logging/dashboard/`)

- **Live page (`/`):** a client component with `new EventSource("http://127.0.0.1:8000/stream")`. It keeps the last ~10 s of samples and draws x vs. setpoint and y vs. setpoint (chart animations off, they lag at 30–50 samples per second).
- **Runs page (`/runs`):** loads `/runs`, you pick one, loads the CSV, finds where the setpoint jumps, and shows the chart and the step response numbers:

| Number | Meaning |
|---|---|
| Rise time | time from 10% to 90% of the jump |
| Overshoot | how far past the setpoint it goes, in % of the jump |
| Settling time | time until it stays within ±5% of the jump |
| Steady-state error | setpoint minus the average position over the last 1 s |

## How to run (laptop)

- `.venv/bin/python vision/vision.py`: camera only, shows where the ball is. Use it to set up the camera.
- `.venv/bin/python esp/datalog.py run1 [--mock]`: logs to `data_logging/runs/run1.csv` and starts the web server. Ctrl+C stops it.
- `npm run dev` in `data_logging/dashboard/`: the dashboard at `http://localhost:3000`.

Use the project's `.venv` Python (`.venv/bin/python ...`). Python libraries: `opencv-python`, `pyserial`. Nothing else.

## Bench calibration (values in `esp/esp.ino`, `esp/plate.ino` and `vision/settings.json`)

| Setting | How to find it |
|---|---|
| Camera number (`CAMERA` in `vision.py`) | 0 = built-in webcam, try 1 for the USB webcam |
| Plate box in the picture | run `vision.py`, press `p`, drag a box over the plate (saved to `vision/settings.json` on `q`) |
| Threshold | slider in `vision.py` until only the ball is white (saved on `q`) |
| Plate size (mm) | ruler; change `PLATE_W_MM` / `PLATE_H_MM` in `vision.py` |
| ESP32 USB port name | found automatically; pass `--port` if the wrong one is picked (Arduino IDE → Tools → Port) |
| Servo pins (`SERVO_X_PIN`, `SERVO_Y_PIN`) | from your friend's wiring |
| Servo center angles (`SERVO_CENTER_X`, `SERVO_CENTER_Y`) | adjust each until its axis is level (phone level app) |
| Servo direction (`SERVO_DIR_X`, `SERVO_DIR_Y`) | tilt +5°, the ball should roll toward +x / +y |
| Servo-to-plate ratio (`SERVO_RATIO`) | measure plate tilt for a known servo change |

## Tuning

Start with `ki = 0`. Raise `kp` until the ball responds, then raise `kd` until it stops wobbling. The camera adds ~50–150 ms of delay, so expect to need more `kd` and a gentler `kp` than in simulations. Add a little `ki` only if the ball settles off target. Tune live with `pid ...` commands and save each good run's CSV.

## Step response proof

With the ball balanced at (0,0): start the logger, type `sp 50 0` in its terminal and press Enter, let it settle, then Ctrl+C. Open the run on the Runs page. Repeat 3 times per axis and put the CSVs, screenshots and metrics table in `docs/`.

## Backup plan

If the camera is too slow or unreliable, swap it for a resistive touch panel read by the ESP32. Only the sensor part changes. The ESP32 then runs PID on its own timer, and `datalog.py` and the dashboard stay the same.
