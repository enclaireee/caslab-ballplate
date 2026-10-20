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
vision/              find the ball (Python + OpenCV)                     <- done
  vision.py          picture -> ball x, y in mm; run it alone to see it live
  settings.json      plate box + threshold, written when you press q
esp/                 everything that talks to the ESP32
  esp.ino            ESP32 code: setup(), loop(), settings at the top, serial commands   (later)
  pid.ino            PID math for one axis                                               (later)
  plate.ino          tilt angle -> servo angle                                           (later)
  datalog.py         laptop: read ESP32 lines -> print, save CSV, serve the dashboard    <- done
  mock.py            fake ESP32 (simulated ball), so everything works without hardware   <- done
  esp_usb.py         real ESP32 over USB, same readLine() as mock.py                     (later)
data_logging/        logged data and the website
  runs/              saved CSV files, one per run (made by datalog.py)
  dashboard/         Next.js dashboard: Live page (/) + Runs page (/runs)                <- done
docs/                results for submission (CSVs, screenshots, metrics table)
```

## Vision (how the ball is found)

1. Cut the picture to the plate area (ignore everything outside).
2. Grayscale, light blur, then threshold: bright pixels become white, the rest black.
3. Biggest white blob = ball. Too small = noise, so "no ball".
4. Blob centre in pixels → mm. (0,0) is the plate centre, x goes right, y goes up.

## ESP32 loop

The camera decides the pace. Every time a `pos` line arrives from the laptop (one per camera frame, ~30 per second), the ESP32 does **one control step**:

1. `dt` = time since the last `pos` line (from `millis()`).
2. `error = setpoint - position`, for each axis.
3. `u = kp*error + ki*integral + kd*derivative`, limited to ±15°.
   - The derivative uses the change in position (not error), so a setpoint jump doesn't kick the plate.
   - The integral stops growing at the limit (anti-windup).
4. Convert tilt to servo angle: `center + direction * ratio * u`, limited to a safe range.
5. Print one data line.

Running PID only when a new position arrives (instead of on a fixed 100 Hz timer) means the derivative never sees the same position twice, so it doesn't spike.

Safety: if the laptop says `pos none`, or no `pos` line came for 200 ms, put the plate flat and reset the integral.

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

Lines starting with `#` are messages (boot, errors). The laptop prints them but does not save them.

## datalog.py (the backend)

Only one program can open the ESP32's USB port, so `datalog.py` is the only program that talks to it. It:

1. reads a line from `Esp().readLine()`,
2. prints it,
3. if it is a data line: saves it to `data_logging/runs/<name>.csv` and hands it to the web server.

The data source is picked by **one import line** at the top:

```python
from mock import Esp          # fake ESP32, no hardware needed
# from esp_usb import Esp     # real ESP32 over USB (later)
```

Web server (Python built-in `http.server`, only reachable from this laptop):

| Address | Gives |
|---|---|
| `http://127.0.0.1:8000/stream` | live data (Server-Sent Events), one JSON sample per message: `{"t_ms": 1120, "x_mm": 0.4, ...}` |
| `http://127.0.0.1:8000/runs` | list of saved CSV names: `["run1.csv", "run2.csv"]` |
| `http://127.0.0.1:8000/runs/run1.csv` | one saved CSV file |

Every answer has `Access-Control-Allow-Origin: *`, because the browser blocks a page on port 3000 from reading port 8000 otherwise.

Later, for the full system, `datalog.py` also runs the camera each loop (`vision.findBall` → `toMm`) and sends `pos x y` through `esp.sendLine()` before reading the reply, since the USB port can only be opened once.

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

- `python vision/vision.py`: camera only, shows where the ball is. Use it to set up the camera.
- `python esp/datalog.py run1.csv`: logs to `data_logging/runs/run1.csv` and starts the web server. Ctrl+C stops it.
- `npm run dev` in `data_logging/dashboard/`: the dashboard at `http://localhost:3000`.

Use the project's `.venv` Python (`.venv/bin/python ...`). Python libraries: `opencv-python`, `pyserial` (later, for `esp_usb.py`). Nothing else.

## Settings to fill once hardware exists (marked `TODO` in code)

| Setting | How to find it |
|---|---|
| Camera number (`CAMERA` in `vision.py`) | 0 = built-in webcam, try 1 for the USB webcam |
| Plate box in the picture | run `vision.py`, press `p`, drag a box over the plate (saved to `vision/settings.json` on `q`) |
| Threshold | slider in `vision.py` until only the ball is white (saved on `q`) |
| Plate size (mm) | ruler |
| ESP32 USB port name | Arduino IDE → Tools → Port (e.g. `/dev/cu.usbserial-0001`) |
| Servo pins | from your friend's wiring |
| Servo center angles | adjust until the plate is level (phone level app) |
| Servo direction (+1/-1) | tilt +5°, the ball should roll toward +x / +y |
| Servo-to-plate ratio | measure plate tilt for a known servo change |

## Tuning

Start with `ki = 0`. Raise `kp` until the ball responds, then raise `kd` until it stops wobbling. The camera adds ~50–150 ms of delay, so expect to need more `kd` and a gentler `kp` than in simulations. Add a little `ki` only if the ball settles off target. Tune live with `pid ...` commands and save each good run's CSV.

## Step response proof

With the ball balanced at (0,0): send `sp 50 0` and record. Open the run on the Runs page. Repeat 3 times per axis and put the CSVs, screenshots and metrics table in `docs/`.

## Backup plan

If the camera is too slow or unreliable, swap it for a resistive touch panel read by the ESP32. Only the sensor part changes. The ESP32 then runs PID on its own timer, and `datalog.py` and the dashboard stay the same.
