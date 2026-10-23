# Whole-Project Software & Hardware Interface Diagnosis: Servo Non-Movement and 3–4 s Lag

**Date:** 2026-10-22  
**Scope:** Read-only whole-project diagnostic across `esp/`, `vision/`, `data_logging/runs/`, `data_logging/dashboard/`, and documentation (`CLAUDE.md`, `architecture.md`, `README.md`). No source, data, or configuration files were modified.

---

## 1. Executive Summary

### Top 3 Likely Causes of S1 (Runtime: Dashboard Shows Commanded Tilt, Servo Moves Only Every 3–4 s or Not at All)

1. **[Confirmed in Code + CSV Data — Firmware / Data / Dashboard] Severe Asymmetric Tilt-Limit Saturation (`+2.50°` / `1150 µs`) Combined with High `PULSE_PER_DEG = 100.0` (`esp/plate.ino:4-11,21-26`, `esp/esp.ino:16-18`)**
   - Because `PULSE_CENTER_X/Y = 1400 µs` sits only `250 µs` above `PULSE_MIN = 1150 µs` and `PULSE_PER_DEG = 100.0 µs/deg`, `setTiltLimits()` (`esp/plate.ino:21-26`) clamps positive tilt at **`+2.50°`** (`1150 µs`) and negative tilt at **`-5.50°`** (`1950 µs`).
   - With current gains `KP = 0.03, KD = 0.02` (`esp/esp.ino:16-18`), whenever the ball is more than `83.3 mm` on the negative side of center (`x_mm < -83.3 mm` at zero speed, or closer when moving toward the edge), `u_x_deg` pins at `+2.50°` (`1150 µs`). In `data_logging/runs/run_20261022_142409.csv`, the X servo is pinned motionless at `1150 µs` for **35.3% of all samples**, producing continuous motionless holds of **2.50 s, 3.38 s, 3.92 s, 4.58 s, and 19.04 s**.
   - In earlier runs (`run_20261022_124251.csv` through `run_20261022_134858.csv`), before `setTiltLimits()` was added, `TILT_LIMIT` was `±15.0°` in `pid.ino` while `tiltToPulse()` (`plate.ino:10`) clamped at `[1150, 1950] µs`. As a result, the dashboard showed `u_x_deg` and `u_y_deg` moving freely between `±2.5°` and `±15.0°`, while `writeMicroseconds()` received a constant `1150 µs` or `1950 µs` for **85% to 98.5% of the run** (motionless stretches of **3 to 33 seconds**).

2. **[Confirmed in Code + CSV Data — Laptop / Firmware / Dashboard] Vision Dropouts (`pos none`) Park the Servos at Center While Freezing the Last `u_x_deg / u_y_deg` on the Dashboard (`esp/datalog.py:185-196`, `esp/esp.ino:102-106,145-150`, `data_logging/dashboard/app/useLiveData.ts:56-123`)**
   - When `vision.findBallMm(frame)` returns `None` (lighting glare, ball near edge, HSV threshold miss, or contour circularity `< 0.5` in `vision/vision.py:135`), `datalog.py:188` sends `"pos none"`.
   - `handleCommand()` (`esp/esp.ino:102-106`) calls `hold()` (`esp/esp.ino:145-150`), which immediately moves the servos to `0°, 0°` (`1400 µs`) and prints `# no ball`—**not** a CSV data line.
   - Because no new CSV row is written during `"# no ball"` frames, the dashboard (`useLiveData.ts:89-93`, which re-fetches `/runs/<latest>.csv` every `500 ms` and displays `samples[samples.length - 1]`) **continues displaying the last valid `u_x_deg` and `u_y_deg`** across the entire dropout. In `run_20261022_142409.csv` there are **32 gaps > 200 ms** (including **0.67 s, 0.75 s, 1.34 s, 2.55 s, 14.79 s, and 40.67 s**), and in `run_20261022_145858.csv` (40 s run) there are **4 gaps > 200 ms** (**0.62 s, 1.34 s, 2.83 s, and 12.61 s**).

3. **[Confirmed in Code / Likely on Bench — Firmware / Library] `setTimerWidth(16)` Called *After* `attach()` Causes 10-Bit LEDC Quantisation (`19.53 µs` Steps) or Core 3.x Re-Attachment Failure (`esp/esp.ino:50-54`, `esp/esptest/esptest.ino:52-56`)**
   - In `ESP32Servo`, `DEFAULT_TIMER_WIDTH` is **10 bits** (`1024` ticks per `20,000 µs` = **`19.53 µs` per tick**, which equals **`0.195°` of plate tilt** at `100 µs/deg`).
   - Calling `servo.attach(pin, 500, 2400)` first configures LEDC at 10-bit resolution and converts the initial `DEFAULT_PULSE_WIDTH_TICKS` (`4825` ticks—a stale constant from 16-bit mode!) or `writeMicroseconds` in 10-bit ticks. Calling `setTimerWidth(16)` *after* `attach()` detaches and re-attaches the pin inside `ESP32Servo::setTimerWidth()`, and on ESP32 variants / `ESP32Servo` versions where `MAXIMUM_TIMER_WIDTH` is capped or where Arduino-ESP32 Core 3.x's new `ledcAttachChannel()` rejects re-attaching an already-claimed pin/channel without `ledcDetach()`, PWM either remains quantised to 10 bits (`19.53 µs` steps) or fails to reconfigure cleanly.
   - Furthermore, when the ball rests slowly or moves slightly (e.g., `run_20261022_145858.csv`), `tiltToPulse()` rounds to integer microseconds (`int(round(...))`, `plate.ino:9`), and any sub-deadband change (`< 5 µs` for MG90S, or `< 19.5 µs` at 10-bit timer width) produces zero physical servo movement for **3.0 to 12.6 seconds** at a time.

---

### Top 3 Likely Causes of S2 (`espreset.ino` Does Not Move the Servo at All, or Moves to the Wrong Position Instead of ~1400 / 1400 µs)

1. **[Confirmed in Library Source — Firmware / Library] `Servo::attach()` in `ESP32Servo` Initializes the Servo at `DEFAULT_PULSE_WIDTH_TICKS = 4825` at `DEFAULT_TIMER_WIDTH = 10` (100% Duty Cycle Glitch) Unless `setTimerWidth()` or `writeMicroseconds()` Precedes `attach()`, and `espreset.ino` Omits `setTimerWidth(16)` Entirely (`esp/espreset/espreset.ino:22-27`)**
   - In `esp/espreset/espreset.ino`, `servoX.setTimerWidth(16)` and `servoY.setTimerWidth(16)` are **completely missing** (unlike `esp.ino:53-54` and `esptest.ino:55-56`).
   - Therefore `espreset.ino` runs at `ESP32Servo`'s `DEFAULT_TIMER_WIDTH = 10` (`1024` ticks per `20,000 µs` period = **`19.53125 µs` per tick**).
   - Inside `ESP32Servo`'s `usToTicks(1400)`:
     $$\text{ticks} = \left\lfloor \frac{1400 \times 1024}{20000} \right\rfloor = \lfloor 71.68 \rfloor = 71\text{ ticks} \implies \frac{71 \times 20000}{1024} = 1386.7\text{ µs}$$
     Wait—even worse: in `ESP32Servo`, the constructor sets `this->ticks = DEFAULT_PULSE_WIDTH_TICKS` (`4825`) and `this->timer_width = 10` (`1024` max ticks). Inside `attach()`, if `writeMicroseconds()` was not called before `attach()`, `attach()` writes `this->ticks` (`4825` > `1024`, i.e. constant HIGH) for the moment between `attach()` and `writeMicroseconds(1400)`. And if compiled against an mismatched Arduino-ESP32 Core 3.x / older `ESP32Servo` version, `ledcSetup` / `ledcAttachChannel` silently fails or outputs 0 Hz.

2. **[Likely / Needs Bench — Hardware / Firmware] Mechanical / Electrical State at Boot: Servo Already Near `1400 µs`, GPIO 2 Strapping / Onboard LED Load, or 5 V Power Rail / Common-Ground / Inrush Brownout (`esp/espreset/espreset.ino:11-12,26-27`)**
   - **If the servo is already at ~1400 µs:** `espreset.ino` writes `1400 µs` once in `setup()` (`lines 26-27`) and does nothing in `loop()` (`lines 30-31`). If the rig was previously left in `hold()` (`1400 µs`) or at rest near `1400 µs`, flashing or running `espreset.ino` commands the exact same pulse (`1400 µs`), producing **zero visible motion**.
   - **If both servos start simultaneously from a distant angle on USB 5 V:** Both `servoX.writeMicroseconds(1400)` and `servoY.writeMicroseconds(1400)` execute within microseconds of each other (`lines 26-27`). Two MG90S servos starting simultaneously draw `2 × 550–800 mA = 1.1–1.6 A` peak inrush current. If powered from a 500 mA USB port or weak 5 V rail without bulk capacitance, the rail sags, browning out the ESP32 or stalling the servo internal controller mid-move (leaving it at the wrong position).
   - **GPIO 2 (`SERVO_X_PIN = 2`) vs GPIO 4 (`SERVO_Y_PIN = 4`):** GPIO 2 is an ESP32 boot strapping pin (must be Low or floating during serial flashing) and on most ESP32 DevKit boards is wired to the onboard blue LED with a series resistor to GND, loading the 3.3 V PWM signal line.

3. **[Confirmed Calibration Discrepancy — Firmware / Docs / Hardware] `1400 µs` Is an Offset Rig-Calibration Value (`100 µs` Away from the MG90S Nominal `1500 µs` Neutral), and `espreset.ino` Bypasses `PULSE_MIN / PULSE_MAX` Clamping (`esp/espreset/espreset.ino:15-16,26-27`, `architecture.md:148-158`)**
   - A standard TowerPro MG90S has its mechanical neutral (90° mid-travel) at **`1500 µs`**, not `1400 µs`. At `1400 µs`, the servo horn is commanded **~9°–10° off its internal potentiometer center**. If a servo horn was re-mounted on the splines assuming `1500 µs` center (or tested with standard Arduino `servo.write(90)` which sends `1500 µs`!), then `1400 µs` tilts the plate noticeably off-level ("moves to the wrong position").

---

## 2. Project Inventory and End-to-End Signal Chain

### 2.1 Complete Project File Inventory

#### Files Read in Full
| Layer | File Path | Lines | Purpose |
| :--- | :--- | ---: | :--- |
| **Docs** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/CLAUDE.md` | 84 | Agent diagnostic rules, known open issues 1–8 |
| **Docs** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/architecture.md` | 188 | System architecture & servo pulse/tilt source of truth |
| **Docs** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/README.md` | 120 | User guide, setup, serial commands |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/esp.ino` | 151 | Main ESP32 control sketch (`setup`, `loop`, `handleCommand`, `controlStep`, `hold`) |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/pid.h` | 23 | `Axis` and `PID` struct definitions |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/pid.ino` | 47 | `makePID`, `resetAxis`, `resetPID`, `axisStep`, `pidStep` |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/plate.ino` | 27 | `tiltToPulse`, `moveServos`, `setTiltLimits` |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/esptest/esptest.ino` | 97 | Interactive serial servo bench-test sketch |
| **Firmware** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/espreset/espreset.ino` | 32 | One-shot setup-only servo centering sketch |
| **Laptop** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/datalog.py` | 203 | Main coordinator: camera loop, serial I/O, CSV writer, HTTP/SSE server on `:8000` |
| **Laptop** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/esp_usb.py` | 47 | `pyserial` wrapper (`findPort`, `Esp`) |
| **Laptop** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/test_datalog.py` | 20 | Unit tests for `isDataLine` and `toSample` |
| **Laptop** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/vision/vision.py` | 206 | OpenCV HSV ball tracker, plate corner perspective transform, calibration UI |
| **Laptop** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/vision/settings.json` | 7 | Saved HSV range, plate size (`250.0 mm`), and 4 pixel corner coordinates |
| **Config** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/requirements.txt` | 3 | Python dependencies (`pyserial`, `opencv-python`, `numpy` — unpinned) |
| **Config** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/.gitignore` | 6 | Git ignore patterns |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/package.json` | 29 | Next.js 16.2.3 / React 19.2.4 dependencies |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/package-lock.json` | 60 (hdr) | Lockfile header inspected for package versions |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/next.config.ts` | 7 | Next.js config (no API proxy/rewrites) |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/tsconfig.json` | 34 | TypeScript config |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/eslint.config.mjs` | 16 | ESLint config |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/next-env.d.ts` | 6 | Next.js types |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/AGENTS.md` | 15 | Note on Next.js version |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/DESIGN.md` | 158 | Dashboard visual design spec |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/README.md` | 36 | Boilerplate Next.js README |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/config.ts` | 6 | `DATALOG_URL = "http://127.0.0.1:8000"` |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/useLiveData.ts` | 124 | Polls `/runs` and `/runs/<latest>.csv` every `500 ms` |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/stepResponse.ts` | 161 | Step-response settling time / overshoot metrics |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/page.tsx` | 114 | Main live telemetry page |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/runs/page.tsx` | 190 | Saved CSV run viewer & step-response analyzer |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/how-to-run/page.tsx` | 206 | Interactive setup guide embedded in dashboard |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/layout.tsx` | 25 | Root layout |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/not-found.tsx` | 18 | 404 page |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/globals.css` | 26 | Tailwind CSS setup |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/DashboardHeader.tsx` | 73 | Connection badge (30 s stale timeout) |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/SystemParametersBar.tsx` | 64 | Displays `X Tilt` (`u_x_deg`) and `Y Tilt` (`u_y_deg`) |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/BallPlateSimulation.tsx` | 173 | 2D canvas + `X TILT` / `Y TILT` bars (hardcoded `/ 15` deg scale) |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/TelemetryCharts.tsx` | 237 | Position (`±125 mm`) and Tilt (`±15°`) time-series SVG charts |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/DataLogModal.tsx` | 145 | Modal CSV parser (expects `time_ms,ball_x,...` — mismatched schema!) |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/DashboardFooter.tsx` | 13 | Footer |
| **Dashboard** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/app/components/SidebarNav.tsx` | 53 | Navigation sidebar |
| **Data** | `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/runs/*.csv` (all 21 files) | 60,134 | `run1.csv`, `run2.csv`, and 19 `run_20261022_*.csv` files analyzed in full |

#### Files Missing or Skipped (With Reason)
- **Missing files noted:**
  - `analysis/2026-10-22-servo-software.md`: Referenced in `CLAUDE.md:23,58,65`, but the `analysis/` directory did not exist on disk or in any commit in `git log --all --stat`.
  - `platformio.ini`, `sketch.yaml`, `.arduino-cli.yaml`: None exist in the repository. No Arduino/PlatformIO lockfiles are committed, meaning the ESP32 Arduino core version and `ESP32Servo` library version are determined solely by the user's local Arduino IDE installation.
  - `esp/mock.py`: Imported by `esp/datalog.py:165` when `--mock` is passed (`from mock import Esp`), and mentioned in `README.md:56` and `CLAUDE.md:50`, but was deleted in commit `5b0ba2ad` (`v1`). Running `python esp/datalog.py --mock` will immediately crash with `ModuleNotFoundError: No module named 'mock'`.
- **Skipped directories (per `CLAUDE.md:25` rules):**
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/.venv/` (skipped per rule; macOS virtual environment)
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/.next/` (skipped per rule; Next.js build output)
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/node_modules/` (skipped per rule; npm packages)
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/esp/__pycache__/` and `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/vision/__pycache__/` (skipped per rule; Python bytecode cache)
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/.playwright-mcp/` (skipped per rule; Playwright browser automation logs/screenshots)
  - `/Users/taufan.zamzami/Development/Coding/caslab-ballplate/data_logging/dashboard/public/*.svg` (static template icons)

---

### 2.2 End-to-End Signal Chain (Camera $\rightarrow$ Servo $\rightarrow$ CSV $\rightarrow$ Dashboard)

```
[1. Camera Capture]        vision/vision.py:42-48 (openCamera), esp/datalog.py:185 (camera.read)
       │
       ▼
[2. Ball Detection]        vision/vision.py:114-142 (findBallMm), esp/datalog.py:186
       │
       ▼
[3. Serial Command TX]     esp/datalog.py:187-190 -> esp/esp_usb.py:37-39 (Esp.sendLine)
       │                   Sends "pos <x> <y>\n" or "pos none\n" at 115200 baud
       ▼
[4. ESP32 Serial RX]       esp/esp.ino:64-67 (loop: Serial.readStringUntil('\n'))
       │
       ▼
[5. Command Parser]        esp/esp.ino:93-124 (handleCommand)
       │                   "pos none" -> hold() (esp.ino:145-150) -> moveServos(0, 0) + "# no ball"
       │                   "pos x y"  -> controlStep(x, y) (esp.ino:128-142)
       ▼
[6. Control Step & dt]     esp/esp.ino:128-133 (controlStep computes dt from millis() - lastControlMs)
       │
       ▼
[7. PID Computation]       esp/pid.ino:42-46 (pidStep) -> esp/pid.ino:24-40 (axisStep)
       │                   Computes u = constrain(kp*err + ki*integral - kd*speed, tiltMin, tiltMax)
       ▼
[8. Tilt-to-Pulse Map]     esp/plate.ino:16-19 (moveServos) -> esp/plate.ino:8-14 (tiltToPulse)
       │                   pulse = constrain(int(round(1400 + (-1)*tilt*100.0)), 1150, 1950)
       ▼
[9. PWM Hardware Write]    esp/plate.ino:17-18 (servoX.writeMicroseconds, servoY.writeMicroseconds)
       │                   ESP32Servo usToTicks() -> LEDC GPIO 2 (X) & GPIO 4 (Y) -> MG90S Servos
       ▼
[10. Telemetry Serial TX]  esp/esp.ino:136-141 (Serial.print 7 CSV fields + '\n')
       │
       ▼
[11. Laptop Serial RX]     esp/datalog.py:193 -> esp/datalog.py:53-62 (readReply) -> esp/esp_usb.py:41-43 (readLine)
       │
       ▼
[12. CSV Filter & Write]   esp/datalog.py:43-45 (isDataLine), esp/datalog.py:194-197 (csv_file.write + flush)
       │
       ▼
[13. HTTP / Dashboard]     esp/datalog.py:69-82 (Website.do_GET "/runs/<name>")
                           data_logging/dashboard/app/useLiveData.ts:56-98 (polls /runs & /runs/<last> every 500 ms)
                           data_logging/dashboard/app/components/SystemParametersBar.tsx:31-36 (displays u_x_deg, u_y_deg)
```

#### Hop-by-Hop Failure, Delay, and Drop Analysis

| Hop | File & Lines | What Can Silently Drop, Delay, or Block Data |
| :--- | :--- | :--- |
| **1. Camera Capture** | `vision/vision.py:42-48`<br>`esp/datalog.py:185` | `cv2.VideoCapture(CAMERA)` (`CAMERA = 0`) uses default OS backend with a multi-frame internal buffer and auto-exposure. If exposure drops in dim light, frame rate falls from 30–50 Hz to 10–15 Hz. If `camera.read()` fails (`ok == False`), `ball` becomes `None` and looks identical to a lost ball. |
| **2. Ball Detection** | `vision/vision.py:114-142`<br>`esp/datalog.py:186` | `findBallMm()` returns `None` if `corners` is unset (`line 115`), no HSV contour has `area >= 100` (`line 125`), or the largest contour has `circularity < 0.5` (`line 135`, e.g. motion blur or partial occlusion at plate edge). Also, `cv2.getPerspectiveTransform(pts, dst)` is recomputed from scratch on **every single frame** (`lines 138-139`). |
| **3. Serial Command TX** | `esp/datalog.py:179-190`<br>`esp/esp_usb.py:37-39` | If the user types a command into `stdin` (`datalog.py:179-182`, e.g., `pid ...`), `datalog.py` sends **both** the `stdin` command **and** a `pos ...` command in the same loop iteration, but only calls `readReply(esp)` **once** (`line 193`). If the `stdin` command were anything that returned a matching reply or took time, the loop would desynchronize by one frame. |
| **4. ESP32 Serial RX** | `esp/esp.ino:64-67` | `Serial.readStringUntil('\n')` blocks up to `Serial.setTimeout()` (default **`1000 ms`**) if a line arrives without a terminating `\n`. Also, the ESP32 hardware UART RX buffer is default `256 bytes`; if the laptop ever sends faster than the ESP32 reads, characters drop silently. |
| **5. Command Parser** | `esp/esp.ino:93-124` | `pos none` (`lines 102-106`) calls `hold()`, which resets servos to `0°, 0°` (`1400 µs`) and prints `# no ball`, **without** updating `lastControlMs` or resetting `pid.x.prevPos`, `pid.y.prevPos`, or `integral`. Unrecognized commands (`sp ...`, `zero`) print `# unknown command: ...` and do nothing. |
| **6. Control Step & `dt`** | `esp/esp.ino:128-133` | `dt = (now - lastControlMs) / 1000.0f`. Because `pos none` does **not** update `lastControlMs`, if the ball is lost for `< 500 ms` (so the `500 ms` serial silence timeout in `esp.ino:72-86` never triggers, because `pos none` is itself a serial command that resets `lastSerialMs`!), `lastControlMs` can be **many seconds old**! When the ball reappears, `dt` is huge (e.g., `14.8 s` or `40.7 s`), corrupting `speed = (pos - prevPos) / dt` and `integral += err * dt`. |
| **7. PID Computation** | `esp/pid.ino:24-40` | `axisStep()` clamps output `u` to `[tiltMin, tiltMax]` (`[-5.50°, +2.50°]`). When `ki > 0`, `integral` continues accumulating up to `±500` (`line 36`) even when the actuator is saturated at `tiltMin`/`tiltMax` (no conditional anti-windup). |
| **8. Tilt-to-Pulse Map** | `esp/plate.ino:8-14` | `tiltToPulse()` rounds to integer microseconds (`int(round(...))`) and clamps to `[1150, 1950]`. Any `u > +2.50°` (in older firmware where `TILT_LIMIT` was `15°`) was silently crushed to `1150 µs`. Small changes `< 0.005°` map to the same integer microsecond. |
| **9. PWM Hardware Write** | `esp/plate.ino:17-18`<br>`esp/esp.ino:46-54` | `servoX.writeMicroseconds()` converts `us` to timer ticks via `usToTicks()`. Because `setTimerWidth(16)` was called *after* `attach()`, tick resolution and LEDC channel state depend on `ESP32Servo` / Core version. Also, `writeMicroseconds()` is called unconditionally on every `controlStep`, even when the integer pulse did not change. |
| **10. Telemetry Serial TX** | `esp/esp.ino:136-141` | Prints 7 comma-separated floats (~35–45 bytes) at `115200` baud (~3.5 ms wire time). Only called inside `controlStep()`, **never** during `hold()` (`pos none`) or the `500 ms` timeout (`esp.ino:72-86`). |
| **11. Laptop Serial RX** | `esp/datalog.py:53-62`<br>`esp/esp_usb.py:41-43` | `readReply(esp)` loops until it gets `isDataLine(line)`, `"# no ball"`, or `""` (2-second serial timeout in `Esp.__init__`, `esp_usb.py:30`). Because `datalog.py` runs camera capture and serial I/O synchronously in a single thread, a 2-second serial timeout freezes camera capture for 2 full seconds. |
| **12. CSV Filter & Write** | `esp/datalog.py:43-45,194-197` | `isDataLine(line)` **only checks `len(line.split(",")) == 7`** and does **not** verify `float(part)`! As a result, 27 KB bursts of NUL/replacement bytes (`\x00\ufffd\x00`) prefixed to the first data line pass `isDataLine()` and corrupt line 2 of 5 CSV files (`run1.csv`, `134210`, `134610`, `134737`, `142409`) and line 340 of `134858`. |
| **13. HTTP / Dashboard** | `esp/datalog.py:76-80`<br>`useLiveData.ts:56-98`<br>`SystemParametersBar.tsx:31-36` | The dashboard **does not use `/stream` (SSE)**! Instead, `useLiveData.ts` polls `/runs` and downloads the **entire** latest CSV file every `500 ms`, parsing it line by line (`parseCsv`). During `"# no ball"` (`pos none`), no new CSV rows are written, so `samples[samples.length - 1]` stays frozen on the last valid `u_x_deg / u_y_deg` while the physical servos are parked at `1400 µs`. |

---

## 3. Known Open Issues Check (`CLAUDE.md` Issues 1–8)

> **Note on `analysis/2026-10-22-servo-software.md`:** `CLAUDE.md:23,58,65` references `analysis/2026-10-22-servo-software.md` as the previous analysis report where Known Open Issues 1–8 were catalogued. That file does not exist in the working tree or anywhere in `git log --all`. Below we verify each of the 8 issues from `CLAUDE.md:58-67` directly against the current codebase and evaluate whether it can explain **S1** (runtime 3–4 s movement) or **S2** (`espreset` behavior).

| # | Known Issue from `CLAUDE.md:60-67` | Still in Code? | File & Line Numbers | Can It Explain S1 (3–4 s Lag) or S2 (`espreset`)? |
| :-: | :--- | :---: | :--- | :--- |
| **1** | **`PULSE_CENTER = 1400` in `[1150, 1950]` gives only `2.5°` of travel on the `1150` side** | **YES** | `esp/esp.ino:32-35`<br>`esp/plate.ino:21-26`<br>`esp/esptest/esptest.ino:34-37`<br>`esp/espreset/espreset.ino:15-18` | **YES — Primary cause of S1 (Confirmed).** `1400 - 1150 = 250 µs`, which at `PULSE_PER_DEG = 100.0` is only `2.50°` (`tiltMax = +2.50°` since `SERVO_DIR = -1`). Whenever `u_x_deg` or `u_y_deg` reaches `+2.50°`, the servo hits the `1150 µs` clamp and stops moving entirely (35.3% of `run_20261022_142409.csv`, with holds of 2.5–19.0 s). Also contributes to **S2** if the user expects `1400 µs` to be mechanical center when the MG90S nominal center is `1500 µs` (`1550 µs` is the midpoint of `[1150, 1950]`). |
| **2** | **`PULSE_PER_DEG` is `100` in code and `10` in `architecture.md`** | **PARTIALLY** (Fixed in `architecture.md:155`, still stale in `architecture.md:72`) | `esp/esp.ino:37` (`100.0f`)<br>`esp/esptest/esptest.ino:39` (`100.0f`)<br>`architecture.md:155` (`100.0`)<br>`architecture.md:72` (`"10 µs per degree"`) | **YES — Major contributor to S1 (Confirmed).** In `architecture.md`, the table at line 155 was updated to `100.0`, but the prose at `architecture.md:72` still says *"1° of plate tilt needs about 10 µs of servo pulse (`PULSE_PER_DEG`), so ±15° is ±150 µs around the middle."* Setting `PULSE_PER_DEG = 100.0` (10× larger) shrank the available plate tilt range from `[-55°, +25°]` to `[-5.5°, +2.5°]`, causing the controller to saturate constantly during normal runs. |
| **3** | **`TILT_LIMIT = 15°` in `pid.ino` is wider than the pulse clamp (`2.5°` / `5.5°`)** | **FIXED in uncommitted working tree** (Present in `HEAD` commit `29d51a5` and Runs 1–16) | Working tree: `esp/pid.h:15,20`, `esp/pid.ino:6,17-22,38`, `esp/plate.ino:21-26`, `esp/esp.ino:55`<br>Git `HEAD`: `esp/pid.ino:2` (`TILT_LIMIT = 15.0f`) | **YES — Explains S1 in Runs 1–16 (Confirmed).** In `HEAD` (`29d51a5`) and all CSV runs up to `13:48`, `pid.ino` clamped `u` to `±15.0°` while `tiltToPulse()` clamped pulses to `[1150, 1950]` (`[-5.5°, +2.5°]`). Thus `u_x_deg` / `u_y_deg` varied between `±2.5°` and `±15°` on the dashboard while the servo was 100% frozen at `1150` or `1950 µs` for 3–33 seconds at a stretch. In the uncommitted working tree, `setTiltLimits()` (`plate.ino:21-26`) sets `tiltMin = -5.5°`, `tiltMax = +2.5°`, so the CSV now records the clipped `u`, though the dashboard charts (`TelemetryCharts.tsx:53`, `BallPlateSimulation.tsx:148,162`) still hardcode `±15°`. |
| **4** | **`espreset.ino` does not clamp to `PULSE_MIN` / `PULSE_MAX`** | **YES** | `esp/espreset/espreset.ino:15-18,26-27` | **NO for current `1400 µs` value (Confirmed), YES if constants are edited.** `espreset.ino:17-18` defines `PULSE_MIN = 1150` and `PULSE_MAX = 1950` (unused dead constants) and `lines 26-27` call `writeMicroseconds(PULSE_CENTER_X)` (`1400`) directly without `constrain()`. Since `1400` is already inside `[1150, 1950]`, adding `constrain(1400, 1150, 1950)` still yields `1400`. |
| **5** | **`sp x y` is in `README.md`, `architecture.md`, `datalog.py` and the CSV header, but removed from `esp.ino`** | **YES** | Removed in commit `29d51a5`<br>Still referenced in:<br>`README.md:94,104`<br>`architecture.md:39,65,86,101-106`<br>`esp/datalog.py:21,150,178`<br>`esp/esp.ino:9-10,138-139`<br>`how-to-run/page.tsx:161` | **NO for S1/S2 directly**, unless the user tried to test servo movement during a run by typing `sp 50 0` into `datalog.py`: `esp.ino:123` rejects `sp 50 0` with `# unknown command: sp 50 0` (`readReply()` prints it to terminal and ignores it), leaving `spX = 0, spY = 0` and the servos unmoved! |
| **6** | **`run_20261022_142409.csv` has NUL bytes on line 2** | **YES — and also in 5 other CSV files!** | `data_logging/runs/run1.csv:2`<br>`run_20261022_134210.csv:2`<br>`run_20261022_134610.csv:2`<br>`run_20261022_134737.csv:2`<br>`run_20261022_134858.csv:340`<br>`run_20261022_142409.csv:2`<br>`esp/datalog.py:43-45` | **Indirectly related to S1 (Confirmed serial/logger bug).** Five runs have ~27.3 KB of `\x00\xef\xbf\xbd\x00` on line 2, and `run_20261022_134858.csv` has 32 NULs injected mid-line at line 340 right before a 13.58 s freeze. They get into the CSV because `isDataLine()` (`datalog.py:43-45`) only checks `len(line.split(",")) == 7` without checking `float(part)`. |
| **7** | **`datalog.py` skips `reset_input_buffer` if the first messages are missed** | **YES** | `esp/esp_usb.py:30-35`<br>`esp/datalog.py:170` | **YES — Explains line-2 NUL corruption and initial lag (Confirmed).** `Esp.__init__()` (`esp_usb.py:30-35`) opens the serial port, sleeps `1.5 s`, and calls `self.port.reset_input_buffer()` **before** `datalog.py` starts the HTTP server or enters the `while True` loop. Any serial bytes or UART break/noise arriving after `reset_input_buffer()` (or when the ESP32 does not reset on port open, as seen in the 5 runs starting at `t_ms = 7.5–59.1 s`) remain in the OS serial buffer and are read on the first `readReply()`. |
| **8** | **`setTimerWidth(16)` is called after `attach()` (`ESP32Servo` says to call it before)** | **YES** (and omitted completely in `espreset.ino`) | `esp/esp.ino:50-54`<br>`esp/esptest/esptest.ino:52-56`<br>`esp/espreset/espreset.ino:22-27` | **YES — Can contribute to both S1 and S2 (Confirmed in `ESP32Servo` source).** Detailed in Section 4 and Section 6.2 below. |

---

## 4. Phase 2: `espreset.ino` (S2) and the "Works on Arduino" Ambiguity (S3)

### 4.1 Line-by-Line Comparison Across the Three Firmware Sketches

| Feature / Step | `esp/esp.ino` + `esp/plate.ino` | `esp/esptest/esptest.ino` | `esp/espreset/espreset.ino` |
| :--- | :--- | :--- | :--- |
| **Library Include** | `#include <ESP32Servo.h>` (`esp.ino:12`) | `#include <ESP32Servo.h>` (`esptest.ino:16`) | `#include <ESP32Servo.h>` (`espreset.ino:8`) |
| **GPIO Pins** | `SERVO_X_PIN = 2`, `SERVO_Y_PIN = 4` (`esp.ino:21-22`) | `SERVO_X_PIN = 2`, `SERVO_Y_PIN = 4` (`esptest.ino:22-23`) | `SERVO_X_PIN = 2`, `SERVO_Y_PIN = 4` (`espreset.ino:11-12`) |
| **`SERVO_US_MIN / MAX`** | `500` / `2400` (`esp.ino:29-30`) | `500` / `2400` (`esptest.ino:30-31`) | `500` / `2400` (`espreset.ino:13-14`) |
| **`PULSE_CENTER_X / Y`** | `1400` / `1400` (`esp.ino:32-33`) | `1400` / `1400` (`esptest.ino:34-35`) | `1400` / `1400` (`espreset.ino:15-16`) |
| **`PULSE_MIN / MAX`** | `1150` / `1950` (`esp.ino:34-35`) | `1150` / `1950` (`esptest.ino:36-37`) | `1150` / `1950` (`espreset.ino:17-18`, **unused!**) |
| **`PULSE_PER_DEG`** | `100.0f` (`esp.ino:37`) | `100.0f` (`esptest.ino:39`) | *Not defined* |
| **`SERVO_DIR_X / Y`** | `-1.0f` / `-1.0f` (`esp.ino:38-39`) | `-1.0f` / `-1.0f` (`esptest.ino:40-41`) | *Not defined* |
| **`Serial.begin`** | `Serial.begin(115200)` (`esp.ino:44`) | `Serial.begin(115200)` (`esptest.ino:48`) | **None** (no serial output at all) |
| **Timer Allocation** | `allocateTimer(0)`, `allocateTimer(1)` (`esp.ino:46-47`) | `allocateTimer(0)`, `allocateTimer(1)` (`esptest.ino:50-51`) | `allocateTimer(0)`, `allocateTimer(1)` (`espreset.ino:20-21`) |
| **`setPeriodHertz`** | `setPeriodHertz(50)` (`esp.ino:48-49`) | `setPeriodHertz(50)` (`esptest.ino:52-53`) | `setPeriodHertz(50)` (`espreset.ino:22-23`) |
| **`attach()` Call** | `attach(pin, 500, 2400)` (`esp.ino:50-51`) | `attach(pin, 500, 2400)` (`esptest.ino:52-53`) | `attach(pin, 500, 2400)` (`espreset.ino:24-25`) |
| **`setTimerWidth(16)`** | Called **after** `attach()` (`esp.ino:53-54`) | Called **after** `attach()` (`esptest.ino:55-56`) | **MISSING** (stays at default 10-bit width) |
| **Pulse Write Method** | `moveServos(0, 0)` $\rightarrow$ `tiltToPulse()` with `constrain(..., 1150, 1950)` $\rightarrow$ `writeMicroseconds()` (`esp.ino:57`, `plate.ino:8-19`) | `moveTo(0, 0)` $\rightarrow$ `tiltToPulse()` with `constrain(..., 1150, 1950)` $\rightarrow$ `writeMicroseconds()` (`esptest.ino:18-28,58`) | Direct `servoX.writeMicroseconds(PULSE_CENTER_X)` and `servoY.writeMicroseconds(PULSE_CENTER_Y)` (`espreset.ino:26-27`) |
| **Delays / Loop** | `loop()` runs serial + 500 ms timeout (`esp.ino:63-88`) | `loop()` runs interactive commands (`esptest.ino:64-96`) | No `delay()`, `loop() {}` is empty (`espreset.ino:30-31`); never detaches |

---

### 4.2 Answers to Phase 2 Questions (a–f)

#### (a) What pulse is really written to each servo in `espreset.ino`?
- **Nominal argument passed to `writeMicroseconds()`:**
  - `servoX.writeMicroseconds(PULSE_CENTER_X)` passes **`1400`** (`esp/espreset/espreset.ino:15,26`).
  - `servoY.writeMicroseconds(PULSE_CENTER_Y)` passes **`1400`** (`esp/espreset/espreset.ino:16,27`).
  - Neither `PULSE_MIN`/`PULSE_MAX` (`1150`/`1950`) nor `SERVO_DIR_X`/`Y` is used in `espreset.ino` (though in `esp.ino:57` and `esptest.ino:58`, `tiltToPulse(0, 1400, -1.0)` also evaluates to `constrain(int(round(1400 + (-1.0)*0*100.0)), 1150, 1950) = 1400`).
- **What `ESP32Servo` actually writes to the hardware LEDC timer:**
  1. Inside `Servo::writeMicroseconds(1400)` (`ESP32Servo.cpp`), `value = 1400` is compared against `this->min` (`500`) and `this->max` (`2400` from `attach(pin, 500, 2400)`). Since `500 <= 1400 <= 2400`, it is not clamped by `ESP32Servo`.
  2. Next, `writeMicroseconds(1400)` converts `1400 µs` to timer ticks using `usToTicks(1400)`:
     $$\text{ticks} = \left\lfloor \frac{\text{us} \times 2^{\text{timer\_width}}}{\frac{1000000}{\text{REFRESH\_CPS}}} \right\rfloor$$
  3. Because `espreset.ino` **omits `setTimerWidth(16)`**, `this->timer_width` is `DEFAULT_TIMER_WIDTH = 10` (`2^{10} = 1024` ticks per `20,000 µs` period, i.e. **`19.53125 µs` per tick**):
     $$\text{ticks} = \left\lfloor \frac{1400 \times 1024}{20000} \right\rfloor = \lfloor 71.68 \rfloor = 71\text{ ticks}$$
  4. Therefore, the actual hardware PWM high-time generated by the ESP32 LEDC peripheral in `espreset.ino` is:
     $$\text{Actual Pulse Width} = \frac{71}{1024} \times 20000\text{ µs} = \mathbf{1386.72\text{ µs}}$$
     That is **`13.3 µs` lower** than `1400 µs` due to 10-bit integer truncation in `usToTicks()`.
  5. **Initial glitch during `attach()` (`espreset.ino:24-25`):** In `ESP32Servo`, `Servo::Servo()` initializes `this->ticks = DEFAULT_PULSE_WIDTH_TICKS` (`4825`, a constant left over from when `DEFAULT_TIMER_WIDTH` was 16!) and `this->timer_width = 10` (`1024` ticks full-scale). When `servoX.attach(2, 500, 2400)` is called *before* `writeMicroseconds(1400)`, `attach()` calls `pwm.write(this->ticks)` (`4825` on a 10-bit `1024`-tick timer = 100% duty cycle) for the few microseconds until `writeMicroseconds(1400)` overwrites the duty register on lines 26–27.

#### (b) Does `1400 / 1400` match `PULSE_CENTER_X/Y` in the code and in `architecture.md`? Where does `1400` come from?
- **Yes, it matches both code and docs:** `PULSE_CENTER_X = 1400` and `PULSE_CENTER_Y = 1400` appear in `esp/esp.ino:32-33`, `esp/esptest/esptest.ino:34-35`, `esp/espreset/espreset.ino:15-16`, and `architecture.md:152`.
- **Where `1400` comes from (git history provenance):**
  - In commit `5b0ba2ad` (`2026-10-21 13:41`, *"v1"*), the constants were `SERVO_CENTER_DEG = 90.0f` (`1500 µs` nominal) with `servo.write(deg)`.
  - In commit `5794a36` (`2026-10-21 15:01`, *"feat: update servo control to use microsecond pulse widths"*), it was changed to `PULSE_CENTER_X = 1500`, `PULSE_CENTER_Y = 1500`, `PULSE_MIN = 1000`, `PULSE_MAX = 2000`, `PULSE_PER_DEG = 10.0f`.
  - In commit `33f9401` (`2026-10-22 10:19`, *"feat(esp): update servo pulse range to 1150-1950 us"*), the limits were changed to `PULSE_MIN = 1150`, `PULSE_MAX = 1950` (whose midpoint is **`1550 µs`**, not `1400 µs`!), while `PULSE_CENTER_X/Y` was still `1500`.
  - In commit `29d51a5` (`2026-10-22 13:01`, *"Update PID constants and servo configuration"*), `PULSE_CENTER_X` and `PULSE_CENTER_Y` were changed from `1500` to **`1400`**, with the comment `// flat plate on this rig; re-measure if horns move` (`esp/esp.ino:32`).
- **Measured value vs. guess:** `1400 µs` is a rig-specific empirical offset chosen to make the physical plate level given how the servo horns were mounted on the splines (or to compensate for linkage geometry), **not** the servo's internal center (`1500 µs`). Because `PULSE_MIN = 1150` and `PULSE_MAX = 1950` were not shifted when `PULSE_CENTER` was moved from `1500` to `1400`, the travel became heavily lopsided (`250 µs` toward `1150` vs `550 µs` toward `1950`). Furthermore, if a servo horn was removed and re-mounted at the servo's natural `1500 µs` center (e.g., after testing `servo.write(90)` in Arduino IDE!), `1400 µs` will drive the plate `100 µs` (~`9°–10°` of servo shaft rotation) away from level.

#### (c) Could the clamp, a wrong constant, or a call order produce no move or a wrong move in `espreset.ino`?
- **`PULSE_MIN` / `PULSE_MAX` clamp:** No—`1400` is well inside `[1150, 1950]` and inside `attach(pin, 500, 2400)`.
- **Call order & missing `setTimerWidth(16)`:**
  - In `espreset.ino:20-27`, the call order is `allocateTimer(0/1)` $\rightarrow$ `setPeriodHertz(50)` $\rightarrow$ `attach(pin, 500, 2400)` $\rightarrow$ `writeMicroseconds(1400)`.
  - As shown in (a), omitting `setTimerWidth(16)` causes `1386.7 µs` to be written instead of `1400 µs` (`13.3 µs` error, ~`1.3°` of servo shaft angle), which is small.
  - However, in `esp.ino:50-54` and `esptest.ino:52-56`, `setTimerWidth(16)` is called **after** `attach()`. Inside `ESP32Servo::setTimerWidth(16)` (`ESP32Servo.cpp`), if the pin is already attached (`this->pinNumber >= 0`), it calls `pwm.detachPin(this->pinNumber)` and then `pwm.attachPin(this->pinNumber, this->REFRESH_CPS, this->timer_width)`. On Arduino-ESP32 Core 3.x, `ESP32PWM::detachPin()` only zeroes its internal array without calling `ledcDetach(pin)` (which is only in `~ESP32PWM()`!), so the subsequent `ledcAttachChannel(pin, 50, 16, channel)` call on an already-attached pin can fail or leave the channel in its old/broken state depending on the exact Core 3.x point release!
- **Why `espreset.ino` produces "no move" in software even when PWM is working:**
  - `espreset.ino` only ever commands a single pulse value: **`1400 µs`**.
  - Whenever `esp.ino` is running and the ball is removed from the plate (or `datalog.py` is stopped for `> 500 ms`), `esp.ino:72-86` or `esp.ino:102-106` calls `hold()` (`esp.ino:145-150`), which calls `moveServos(0, 0)` $\rightarrow$ **`1400 µs`**.
  - Therefore, if the servos were already at `1400 µs` when `espreset.ino` was flashed or reset, **commanding `1400 µs` produces zero physical movement (`0 µs` change)**!

#### (d) Does `espreset.ino` finish and stop sending pulses too early?
- **No (Confirmed in `ESP32Servo` and ESP32 LEDC hardware architecture).**
- In `esp/espreset/espreset.ino:20-31`:
  - `setup()` attaches `servoX` and `servoY` to ESP32 hardware LEDC timers 0 and 1 and calls `writeMicroseconds(1400)`.
  - `setup()` never calls `servoX.detach()` or `servoY.detach()`.
  - `loop()` (`lines 30-31`) is an empty infinite loop `void loop() {}` (in Arduino-ESP32, `loopTask` calls `loop()` repeatedly forever).
  - Because the ESP32 LEDC peripheral is an independent hardware PWM generator driven by the APB clock, once `ledcWrite()` sets the duty cycle in `writeMicroseconds()`, the hardware continues outputting the 50 Hz (`20 ms` period) pulse train on GPIO 2 and GPIO 4 indefinitely with zero CPU intervention—unless the ESP32 is held in reset (`EN` low), enters deep sleep, or browns out.

#### (e) GPIO 2 (`SERVO_X_PIN`) vs. GPIO 4 (`SERVO_Y_PIN`): ESP32 Strapping Pin & Onboard LED Effects
- **Official Espressif Strapping Pin Rules ([ESP32 Boot Mode Selection](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html#gpio2)):**
  - **GPIO 2** is a boot strapping pin with a weak internal pull-down resistor (`~45 kΩ`).
  - During **serial bootloader entry (flashing)** (`GPIO0 = Low`), **GPIO 2 must be Low or floating**. If an external circuit (such as a powered servo signal input with an internal pull-up to 5 V) pulls GPIO 2 High while `esptool` resets the chip to flash firmware, the ESP32 fails to enter `DOWNLOAD_BOOT` (or enters `HSPI_FLASH_BOOT` / test mode) and flashing fails.
  - During **normal execution boot** (`GPIO0 = High`), GPIO 2's strapping value is ignored for UART download, though before `setup()` runs, GPIO 2 is in high-impedance input with weak pull-down.
  - **Onboard LED load on GPIO 2:** On standard 30-pin and 38-pin ESP32 DevKitC / NodeMCU-32S boards, **GPIO 2 is hardwired to the onboard blue LED** (in series with a `470 Ω–1 kΩ` resistor to GND). That LED+resistor loads GPIO 2 with `~1.5–3 mA` to GND whenever the PWM pulse is high, slightly lowering the high-level voltage ($V_{OH}$) seen by Servo X compared to Servo Y, and visibly glowing at ~7% duty cycle (`1400 µs / 20000 µs = 7.0%`) when 50 Hz PWM is active!
- **Comparison with GPIO 4 (`SERVO_Y_PIN`):**
  - **GPIO 4** is **not** a boot mode strapping pin and has **no onboard LED** on standard ESP32 DevKit boards.
- **Why X vs. Y behavior matters diagnostically:**
  - If **Servo Y (GPIO 4) works** while **Servo X (GPIO 2) does not move or twitches**, the problem is specific to GPIO 2 (onboard LED loading the 3.3 V signal below the servo's $V_{IH}$ threshold, a bad wire, or a damaged Servo X).
  - If **neither Servo X nor Servo Y moves**, GPIO 2's strapping/LED circuit is **not** the primary cause; the fault lies in a shared element (5 V servo power / missing common GND, servos already at `1400 µs`, or `ESP32Servo` / Arduino Core version).
  - Bonus observation: Because GPIO 2 drives the onboard blue LED on most ESP32 boards, **the onboard blue LED acts as a built-in hardware PWM indicator**! At `1400 µs` (`7%` duty cycle), the GPIO 2 LED should glow dimly; if `attach()` stuck at `4825/1024` ticks (`100%` duty cycle), it glows at full brightness; if no PWM is output, it is completely off.

#### (f) Unpacking S3 ("The `espreset` Sketch Works Fine 'on Arduino'"): Ambiguity Analysis
The user's statement that `espreset` works fine *"on Arduino"* is ambiguous. Below are the four plausible readings considered, the evidence for each, and what the user must confirm:

| Reading | Meaning | Evidence in Repo & Software Stack | Plausibility |
| :--- | :--- | :--- | :---: |
| **Reading A: Different Hardware Board (Arduino Uno / Nano / Mega with standard `<Servo.h>`)** | The user tested the servos on a 5 V AVR Arduino board (e.g., Arduino Uno) using the standard Arduino `Servo.h` library, where the servos moved cleanly. | 1. Standard AVR Arduino outputs **5.0 V logic** on PWM pins (vs. ESP32's **3.3 V logic**), which drives all genuine and clone MG90S servos with wide noise margin.<br>2. Standard Arduino `Servo.h` defaults to **`1500 µs` center** (`servo.write(90)`) and uses a 16-bit hardware timer (`0.5 µs` resolution) without `ESP32Servo`'s `setTimerWidth` / LEDC Core 3.x issues.<br>3. If the servo horns were centered on an Arduino Uno using `servo.write(90)` (`1500 µs`), then running `espreset.ino` (`1400 µs`) on the ESP32 will move the servos to an unexpected offset (`-100 µs` from `1500 µs`). | **High (Supported by hardware/library differences)** |
| **Reading B: Flashed from Arduino IDE Alone (Serial Monitor Closed, `datalog.py` Not Running)** | The user means flashing `espreset.ino` from the **Arduino IDE** works, whereas running the rig with the Python scripts (`datalog.py`) or another tool fails. | 1. When `espreset.ino` is flashed from Arduino IDE, `esptool` resets the board once and leaves the serial port closed. If `datalog.py` is later started while `espreset.ino` is on the board, opening the serial port in `Esp.__init__` toggles `DTR/RTS`, resetting the ESP32, and `datalog.py` then sends `pos ...` commands that `espreset.ino` ignores.<br>2. Alternatively, if one laptop/machine compiled with **Arduino-ESP32 Core 2.0.x** and another compiled with **Core 3.x** + an older `ESP32Servo`, PWM output differs between machines. | **High (Supported by workflow/IDE differences)** |
| **Reading C: Standard Arduino IDE Servo Example (`Sweep` or `servo.write(90)`) on the Same ESP32** | The user ran a standard Arduino IDE example sketch (`servo.write(0)`, `servo.write(90)`, `servo.write(180)`) on the ESP32 and saw the servos move, whereas `espreset.ino` did not move or went to the wrong angle. | 1. `servo.write(90)` with `attach(pin, 500, 2400)` commands the midpoint of `[500, 2400]`, which is **`1450 µs`** (or **`1500 µs`** with default `1000–2000 µs`), **not `1400 µs`**!<br>2. A sweep sketch continuously alternates between two different angles (`0°` and `180°`), so movement is always visible; `espreset.ino` only writes `1400 µs` once, so if the servo is already at `1400 µs` (from `esp.ino`'s `hold()`), `espreset.ino` produces **zero visible motion**! | **Very High (Directly explains both "does not move" and "wrong position")** |
| **Reading D: Earlier Version of `espreset.ino` in Git History** | An older commit of `espreset.ino` worked before recent edits. | Git history check (`git log -p esp/espreset/espreset.ino`):<ul><li>Commit `5b0ba2ad` (`Oct 21 13:41`): used `servo.write(90.0f)` (`1450 µs` with `500–2400`).</li><li>Commit `5794a36` (`Oct 21 15:01`): used `writeMicroseconds(1500)`.</li><li>Commit `29d51a5` (`Oct 22 13:01`): changed `PULSE_CENTER_X/Y` from `1500` to `1400`.</li></ul>If the user remembers `espreset.ino` centering properly before Oct 22 13:01, it was writing **`1500 µs`** (or `1450 µs`), not `1400 µs`! | **High (Directly proven by `git log`)** |

#### Software & Environment Differences When Flashing from Arduino IDE (for Reading B)
If S3 means *"works in one Arduino IDE setup vs. another setup"*, the exact software variables that change servo behavior are:
1. **ESP32 Arduino Core Version (`Tools -> Board -> Boards Manager -> esp32 by Espressif Systems`):**
   - **Core 2.0.x (ESP-IDF 4.4):** Uses `ledcSetup(channel, freq, bits)` + `ledcAttachPin(pin, channel)`. Calling `setTimerWidth(16)` after `attach()` re-runs `ledcSetup()` on the existing channel cleanly.
   - **Core 3.0.x / 3.1.x (ESP-IDF 5.1+):** Removed `ledcSetup` and `ledcAttachPin`, replacing them with pin-centric `ledcAttachChannel(pin, freq, bits, channel)` ([Espressif 2.x to 3.0 Migration Guide](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html#ledc)). Calling `ledcAttachChannel()` a second time on an already-attached pin (which `ESP32Servo::setTimerWidth()` does when called after `attach()`) without first calling `ledcDetach(pin)` can fail or log an error in ESP-IDF 5.x LEDC driver.
2. **`ESP32Servo` Library Version (`Sketch -> Include Library -> Manage Libraries -> ESP32Servo`):**
   - **Versions `< 1.1.0`:** Did not support Core 3.x at all; `DEFAULT_TIMER_WIDTH` was `16` in very old versions (`0.9.x`) and changed to `10` in `0.11.0+`, while `DEFAULT_PULSE_WIDTH_TICKS` remained hardcoded at `4825`.
   - **Versions `3.0.0–3.2.1`:** Added Core 3.x `#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)` conditionals in `ESP32PWM.cpp` (`https://raw.githubusercontent.com/madhephaestus/ESP32Servo/master/src/ESP32PWM.cpp`).
3. **Board Target Selection (`Tools -> Board`):**
   - Selecting `ESP32 Dev Module` vs. an `ESP32-S3` or `ESP32-C3` board changes `MAXIMUM_TIMER_WIDTH` (`14` vs `20`) and whether `ESP32PWM` uses MCPWM or LEDC (`ESP32PWM.cpp:26-28,60-67`).
4. **Serial Monitor State & Power Source:**
   - Opening or closing the Arduino IDE Serial Monitor toggles `DTR/RTS` and reboots the ESP32.
   - Powering servos from USB 5 V vs. an external 5 V supply with common GND determines whether simultaneous X+Y startup inrush current (`1.1–1.6 A`) browns out the board.

---

## 5. Phase 3: Runtime 3–4 s Lag (S1) — Hypotheses H1–H8 Tested Against All 21 CSV Runs

### 5.1 Summary of All 21 CSV Runs in `data_logging/runs/`

All 21 CSV files share the 7-column header `t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg`. None of the 21 files contain `t_ms` jumping backwards (`dt <= 0` count is `0` in every file), meaning the ESP32 never rebooted mid-run *after* logging started. However, **6 files contain NUL (`\x00`) / non-ASCII bytes**, and the 21 runs span **6 distinct firmware eras** on 2026-10-22:

| # | CSV File (Chronological by mtime) | Rows | Duration (s) | Median `dt` / Rate | Gaps `>200ms` (Max Gap) | Fitted Gains `(KP, KI, KD)` | Active `u_x` Clamp `[min, max]` | % Samples Clamped at `1150 / 1950 µs` (X / Y) | `pulse_x` Changes/s (Max Hold) | Corrupted Bytes? |
| :-: | :--- | ---: | ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | `run1.csv` | 4,268 | 97.6 s | `22 ms` (45.5 Hz) | 1 (`0.81 s`) | `(0.074, 0, 0.025)` | `[-15°, +15°]` | 16.0% / 14.3% | `16.2/s` (`0.83 s`) | **Line 2:** 10,880 NUL + 16,320 non-ASCII (`t0=59.1s`) |
| 2 | `run2.csv` | 3,165 | 72.1 s | `22 ms` (45.5 Hz) | 0 (`0.13 s`) | `(0.074, 0, 0.025)` | `[-15°, +15°]` | 10.6% / 8.8% | `18.3/s` (`0.40 s`) | Clean (`t0=2.6s`) |
| 3 | `run_20261022_121704.csv` | 5,440 | 256.8 s | `21 ms` (47.6 Hz) | 18 (`64.68 s`) | `(0.074, 0, 0.025)` | `[-15°, +15°]` | 16.5% / 18.7% | `8.0/s` (`64.68 s`) | Clean (`t0=2.5s`) |
| 4 | `run_20261022_122241.csv` | 3,746 | 177.2 s | `21 ms` (47.6 Hz) | 14 (`42.84 s`) | `(0.074, 0, 0.025)` | `[-15°, +15°]` | 27.6% / 23.0% | `5.9/s` (`42.84 s`) | Clean (`t0=3.2s`) |
| 5 | `run_20261022_122846.csv` | 17,808 | 740.3 s | `21 ms` (47.6 Hz) | 38 (`52.66 s`) | Live tuning (`sp` varied `0..100`) | `[-15°, +15°]` | 55.6% / 59.3% | `5.6/s` (`52.66 s`) | Clean (`t0=2.8s`) |
| 6 | `run_20261022_124251.csv` | 3,760 | 140.4 s | `21 ms` (47.6 Hz) | 19 (`33.32 s`) | `(~0.15, ~0.02, ~0.05)` | `[-15°, +15°]` | **92.8% / 87.9%** | **`1.47/s`** (`36.99 s`) | Clean (`t0=2.5s`) |
| 7 | `run_20261022_124558.csv` | 1,033 | 49.0 s | `21 ms` (47.6 Hz) | 20 (`9.08 s`) | `(~0.18, ~0.03, ~0.06)` | `[-15°, +15°]` | **85.9% / 85.4%** | **`1.86/s`** (`11.27 s`) | Clean (`t0=2.6s`) |
| 8 | `run_20261022_124713.csv` | 3,523 | 127.1 s | `21 ms` (47.6 Hz) | 26 (`25.84 s`) | `(~0.15, ~0.01, ~0.05)` | `[-15°, +15°]` | **88.9% / 88.2%** | **`1.61/s`** (`25.88 s`) | Clean (`t0=2.3s`) |
| 9 | `run_20261022_133746.csv` | 1,397 | 49.0 s | `21 ms` (47.6 Hz) | 7 (`9.43 s`) | `(0.15, 0.05, 0.06)` | `[-15°, +15°]` | **91.8% / 64.9%** | **`1.59/s`** (`12.22 s`) | Clean (`t0=2.3s`) |
| 10 | `run_20261022_133930.csv` | 2,555 | 75.5 s | `21 ms` (47.6 Hz) | 9 (`6.53 s`) | `(0.15, 0.05, 0.06)` | `[-15°, +15°]` | **87.2% / 77.7%** | **`2.61/s`** (`15.65 s`) | Clean (`t0=1.9s`) |
| 11 | `run_20261022_134210.csv` | 2,523 | 112.9 s | `21 ms` (47.6 Hz) | 22 (`14.96 s`) | `(0.15, 0.05, 0.06)` | `[-15°, +15°]` | **86.8% / 90.8%** | **`1.69/s`** (`22.66 s`) | **Line 2:** 10,910 NUL + 16,365 non-ASCII (`t0=13.7s`) |
| 12 | `run_20261022_134453.csv` | 605 | 31.1 s | `21 ms` (47.6 Hz) | 10 (`9.41 s`) | `(1.00, 0, 0)` | `[-15°, +15°]` | **95.9% / 96.7%** | **`0.77/s`** (`16.71 s`) | Clean (`t0=1.8s`) |
| 13 | `run_20261022_134610.csv` | 1,025 | 32.0 s | `21 ms` (47.6 Hz) | 7 (`4.30 s`) | `(1.00, 0, 0)` | `[-15°, +15°]` | **93.3% / 97.6%** | **`1.44/s`** (`7.13 s`) | **Line 2:** 10,918 NUL + 16,377 non-ASCII (`t0=7.7s`) |
| 14 | `run_20261022_134737.csv` | 404 | 19.9 s | `21 ms` (47.6 Hz) | 2 (`5.35 s`) | `(1.00, 0, 0)` | `[-15°, +15°]` | **98.5% / 96.5%** | **`0.35/s`** (`10.27 s`) | **Line 2:** 10,910 NUL + 16,365 non-ASCII (`t0=7.5s`) |
| 15 | `run_20261022_134858.csv` | 4,074 | 145.6 s | `21 ms` (47.6 Hz) | 16 (`13.58 s`) | `(1.00, 0, 0)` | `[-15°, +15°]` | **92.0% / 92.6%** | **`1.48/s`** (`33.36 s`) | **Line 340:** 32 NULs mid-line before `13.58 s` gap |
| 16 | `run_20261022_135324.csv` | 0 | — | — | — | *(Header only)* | — | — | — | Empty (header only) |
| 17 | `run_20261022_135359.csv` | 758 | 28.4 s | `21 ms` (47.6 Hz) | 3 (`5.34 s`) | `(0.03, 0, 0.012)` | `[-2.5°, +2.5°]` | 15.8% / 28.4% | `15.7/s` (`5.34 s`) | Clean (`t0=2.1s`) |
| 18 | `run_20261022_135451.csv` | 1,693 | 52.8 s | `21 ms` (47.6 Hz) | 15 (`3.91 s`) | `(1.20, 0, 0.012)` | `[-2.5°, +2.5°]` | **55.6% / 64.9%** (and 43.4% at `-2.5°`) | **`0.91/s`** (`14.13 s`) | Clean (`t0=1.8s`) |
| 19 | `run_20261022_135900.csv` | 1,903 | 184.2 s | `21 ms` (47.6 Hz) | 9 (`74.08 s`) | `(0.03, 0, 0.020)` | `[-2.5°, +2.5°]` | 15.6% / 22.9% | `4.6/s` (`74.08 s`) | Clean (`t0=2.5s`) |
| 20 | `run_20261022_142409.csv` | 5,046 | 194.2 s | `22 ms` (45.5 Hz) | 32 (`40.67 s`) | `(0.03, 0, 0.020)` | `[-5.5°, +2.5°]` | **35.3% / 22.7%** | `9.8/s` (`40.67 s`) | **Line 2:** 10,906 NUL + 16,359 non-ASCII (`t0=17.8s`) |
| 21 | `run_20261022_145858.csv` | 558 | 39.8 s | `40 ms` (25.0 Hz) | 4 (`12.61 s`) | `(0.03, 0, 0.020)` | `[-5.5°, +2.5°]` | 0.9% / 0.2% | **`2.4/s`** (`12.61 s`) | Clean (`t0=2.5s`) |

---

### 5.2 Hypothesis-by-Hypothesis Evaluation (H1–H8)

#### H1. Output-Side Throttling, Rounding, `PULSE_PER_DEG` Scaling, and Tilt-Limit Clamping
- **Does the firmware skip `writeMicroseconds()` when the integer pulse is unchanged?**
  - **No (Confirmed in `esp/plate.ino:16-19`):** `moveServos(ux, uy)` unconditionally calls `servoX.writeMicroseconds(...)` and `servoY.writeMicroseconds(...)` on every `controlStep()`.
- **Does `tiltToPulse` clamping / `setTiltLimits` cause multi-second holds where `u` is non-zero or varying while the pulse never changes?**
  - **YES — Confirmed with overwhelming CSV evidence (Primary software cause of S1):**
    1. **Runs 6–15 (`124251` to `134858`, matching git `HEAD` commit `29d51a5`):** `TILT_LIMIT` in `pid.ino` was `15.0°`, while `PULSE_PER_DEG = 100.0` meant `tiltToPulse()` saturated at `PULSE_MIN = 1150 µs` (`+2.50°`) and `PULSE_MAX = 1950 µs` (`-5.50°`). On the dashboard, `u_x_deg` and `u_y_deg` moved dynamically between `2.5°` and `15.0°`, while `tiltToPulse()` output a rock-solid `1150 µs` or `1950 µs` for **85.9% to 98.5% of the entire run**! In those runs, the reconstructed pulse changes only **`0.35 to 2.61` times per second**, with continuous constant-pulse holds of **3.1 s, 3.3 s, 3.6 s, 3.9 s, 4.3 s, 5.2 s, 6.4 s, 10.3 s, 22.7 s, and 33.4 s**.
    2. **Run 18 (`135451`, `KP = 1.20` with `±2.5°` clamp):** 99.0% of all samples are pinned at either `+2.50°` (`1150 µs`) or `-2.50°` (`1650 µs`), so the servo only flips between its two limits **`0.91` times per second** (every 1 to 14 seconds).
    3. **Run 20 (`142409`, current working tree `KP = 0.03, KD = 0.02`, `tiltMin = -5.50°, tiltMax = +2.50°`):** Because `tiltMax` is only `+2.50°` (`250 µs` headroom on the `1150 µs` side), whenever `x_mm < -83.3 mm`, `u_x_deg` saturates at `+2.50°` (`1150 µs`). This happens for **35.3% of all samples in `run_20261022_142409.csv`**, holding `servoX` motionless at `1150 µs` for stretches of **2.50 s (`t=107.6..110.1s`), 3.38 s (`t=110.1..113.5s`), 3.92 s (`t=199.3..203.2s`), 4.58 s (`t=118.4..123.0s`), and 19.04 s (`t=180.2..199.3s`)**.
    4. **Run 21 (`145858`, latest run):** The ball sits nearly stationary at `x = -37.4 mm` (`u_x = +1.12°`, `1288 µs`) and `x = -32.7 mm` (`u_x = +0.98°`, `1302 µs`). Because `x_mm` is quantized to `0.1 mm` (`datalog.py:190`) and `KP = 0.03`, a `0.1 mm` position change when stationary produces $\Delta u = 0.003^\circ \implies 0.3\text{ µs}$, which rounds to the **exact same integer microsecond** (`1298 µs` is held for **3.04 s** straight at `t=32.5..35.6s`, and `1288 µs` is held across a **12.61 s** gap).
- **Test to confirm/rule out:** Widen `PULSE_CENTER_X/Y` to the midpoint of `[1150, 1950]` (`1550 µs`, or re-level horns at `1500 µs` with symmetric limits) and verify on the bench whether `PULSE_PER_DEG` is truly `100 µs/deg` or `~10–30 µs/deg`.

#### H2. Control Loop Blocked (`readStringUntil`, `parseFloat`, `delay`, or Long Prints)
- **Confidence:** **Ruled out during normal `pos` streaming; Confirmed possible only if an unterminated serial line is sent.**
- **Evidence & Worst-Case Loop Period Calculation (`esp/esp.ino:63-88`):**
  - `esp.ino` does **not** use `Serial.parseFloat()` or `Serial.parseInt()`; it uses `Serial.readStringUntil('\n')` (`line 65`) followed by in-memory `sscanf(line.c_str(), "%f %f", &x, &y)` (`line 108`).
  - When `datalog.py:38` (`self.port.write((text + "\n").encode())`) sends a newline-terminated command, `readStringUntil('\n')` returns as soon as `\n` arrives (~`1.5 ms` at `115200` baud).
  - `controlStep()` (`esp.ino:128-142`) executes floating-point PID math (`< 50 µs`), two `writeMicroseconds()` calls (`< 20 µs`), and `Serial.print()` of ~40 bytes (`~3.5 ms` TX time if buffer were full, `< 100 µs` into UART TX FIFO).
  - In the CSVs, the median sample period across Runs 1–20 is **`21–22 ms` (`45.5–47.6 Hz`)**, proving the ESP32 loop takes `< 2 ms` and is paced entirely by the laptop camera (`vision.py`).
  - **Only blocking case:** If raw bytes without `\n` are sent to the ESP32, `Serial.readStringUntil('\n')` blocks for the default Arduino stream timeout of **`1000 ms` (`1.0 s`)**.

#### H3. Input Starvation (`pos none`, Camera Frame Drops, Stale `dt`, Timeout Path, Serial Buffer Lag)
- **Confidence:** **Confirmed in Code + CSV Data (Major contributor to S1).**
- **Evidence:**
  1. **Frequent multi-second gaps in CSVs caused by `"pos none"`:** Whenever `vision.findBallMm(frame)` returns `None`, `datalog.py:188` sends `"pos none"`. The ESP32 responds with `"# no ball"` (`esp.ino:149`), which `readReply()` (`datalog.py:59`) returns to `main()`, where `isDataLine("# no ball")` is `False` (`datalog.py:194`). Thus **no CSV row is written while the ball is lost**, creating the multi-second timestamp jumps in `t_ms` seen in almost every run (e.g., **32 gaps > 200 ms** in `run_20261022_142409.csv`, including `1.34 s, 2.55 s, 3.38 s, 14.79 s, 40.67 s`; and **4 gaps > 200 ms** in `run_20261022_145858.csv`: `0.62 s, 1.34 s, 2.83 s, 12.61 s`).
  2. **Why `"pos none"` bypasses the `500 ms` timeout reset in `esp.ino:72-86`:**
     - Look at `esp/esp.ino:64-86`:
       ```cpp
       if (Serial.available()) {
         String line = Serial.readStringUntil('\n');
         ...
         handleCommand(line);
         lastSerialMs = millis();
       }
       if (hasSeenBall && millis() - lastSerialMs > TIMEOUT_MS) {
         hold();
         pid.x.prevPos = NAN;
         ...
       }
       ```
     - Because `datalog.py` sends `"pos none"` at ~45 Hz whenever the camera does not see the ball, `Serial.available()` is true every `22 ms` and **`lastSerialMs = millis()` is updated every `22 ms`!**
     - Consequently, `millis() - lastSerialMs > TIMEOUT_MS` (`500 ms`) **NEVER FIRES** during camera dropouts!
     - Instead, `handleCommand("pos none")` (`esp.ino:102-106`) calls `hold()`, which moves the servos to `0°, 0°` (`1400 µs`) **without** resetting `pid.x.prevPos`, `pid.y.prevPos`, `pid.x.integral`, `pid.y.integral`, or `lastControlMs`!
     - When the ball is finally detected again after a 3–40 second dropout, `controlStep()` (`esp.ino:128-131`) computes `dt = (now - lastControlMs) / 1000.0f` over the **entire multi-second dropout**, and `axisStep()` (`pid.ino:29-36`) computes `speed = (pos - stale_prevPos) / huge_dt` and `integral += err * huge_dt`!
     - We can see this directly in `run_20261022_142409.csv` (`analyze_details.py` output): the PD fit has `median_err = 0.0026°`, but `max_err = 2.9060°` right on the samples after multi-second gaps!

#### H4. Laptop-Side Serial Reset (`DTR` / `RTS`) and Mid-Run Reboots
- **Confidence:** **Ruled out for mid-run reboots (Confirmed `0` mid-run resets in all 21 CSVs); Confirmed at startup (`Esp.__init__`).**
- **Evidence:**
  - `esp/esp_usb.py:30` opens the serial port with `self.port = serial.Serial(port, BAUD, timeout=2)` and never reopens it during a run (there is no retry or reconnect loop in `esp_usb.py` or `datalog.py`).
  - Across all 21 CSV files (60,134 rows), `t_ms` is strictly monotonically increasing (`Resets (dt<=0): 0` in every file). Thus the ESP32 **never** rebooted mid-run while `datalog.py` was logging.
  - However, at startup (`Esp.__init__`), `serial.Serial(port, BAUD, timeout=2)` asserts `DTR` and `RTS`, triggering the ESP32 DevKit two-transistor auto-reset circuit (`t_ms` starts around `1800–3200 ms` in 15 of the 20 non-empty runs). In the 5 runs where `t_ms` starts at `7,515–59,125 ms`, the board did not reset cleanly on open and dumped ~27.3 KB of `\x00\ufffd\x00` into line 2 of the CSV.

#### H5. Servo Library or Timer Issues (`attach` Before `allocateTimer`, `setTimerWidth(16)` After `attach()`, LEDC Quantisation)
- **Confidence:** **Confirmed in Code & `ESP32Servo` Source (Contributes to S1 and S2).**
- **Exact LEDC Resolution vs. `1 µs` Calculation:**
  - At `REFRESH_CPS = 50 Hz`, one PWM period is $T = \frac{10^6\text{ µs}}{50} = 20,000\text{ µs}$.
  - `ESP32Servo` converts microseconds to LEDC duty ticks via integer floor division:
    $$\text{ticks} = \left\lfloor \frac{\text{us} \times 2^{\text{timer\_width}}}{20000} \right\rfloor, \quad \Delta\text{us}_{\text{step}} = \frac{20000}{2^{\text{timer\_width}}}$$
  - **At `DEFAULT_TIMER_WIDTH = 10` bits (`1024` ticks, used by `espreset.ino` and initially by `attach()` in `esp.ino` / `esptest.ino`):**
    $$\Delta\text{us}_{10\text{-bit}} = \frac{20000\text{ µs}}{1024} = \mathbf{19.53125\text{ µs/tick}}$$
    At `PULSE_PER_DEG = 100.0 µs/deg`, one 10-bit LEDC tick equals **`0.1953°` of plate tilt** (nearly **20× coarser** than `1 µs`). Any commanded tilt change smaller than `0.195°` (`~6.5 mm` of ball motion at `KP = 0.03`) produces **zero change in the hardware PWM duty register**!
  - **At `timer_width = 14` bits (`16,384` ticks, the `MAXIMUM_TIMER_WIDTH` cap in some `ESP32Servo` builds/targets):**
    $$\Delta\text{us}_{14\text{-bit}} = \frac{20000\text{ µs}}{16384} = \mathbf{1.2207\text{ µs/tick}}$$
  - **At `timer_width = 16` bits (`65,536` ticks):**
    $$\Delta\text{us}_{16\text{-bit}} = \frac{20000\text{ µs}}{65536} = \mathbf{0.3052\text{ µs/tick}}$$
  - Because `esp.ino:50-54` and `esptest.ino:52-56` call `setTimerWidth(16)` **after** `attach()`, `attach()` first initializes the LEDC channel at 10-bit resolution (`19.53 µs/tick`) and writes the initial pulse before `setTimerWidth(16)` attempts to detach and re-attach the pin.

#### H6. Servo Deadband (MG90S Internal Deadband vs. Commanded Tilt)
- **Confidence:** **Confirmed contributor for small ball motions.**
- **Calculation:**
  - The MG90S datasheet specifies a deadband width of **`~5 µs`** (up to `5–10 µs` on clone analog/digital variants).
  - At the current `PULSE_PER_DEG = 100.0 µs/deg`:
    $$\Delta u_{\text{deadband}} = \frac{5\text{ µs}}{100\text{ µs/deg}} = 0.05^\circ$$
    With `KP = 0.03 deg/mm`, `0.05°` corresponds to $\frac{0.05}{0.03} = 1.67\text{ mm}$ of ball position change.
  - Note: If `PULSE_PER_DEG` were `10.0 µs/deg` (as in `architecture.md:72` and Runs 1–5), a `5 µs` deadband corresponds to `0.5°` of commanded tilt (`6.8 mm` of ball motion at `KP = 0.074`).
  - Therefore, at `PULSE_PER_DEG = 100.0`, the `5 µs` servo deadband alone only masks changes smaller than `0.05°` (`1.67 mm`); it cannot by itself explain a 3–4 second freeze when `u` changes by several degrees, which is instead explained by **H1** (saturation at `+2.5°` / `1150 µs`), **H3/H8** (`pos none` freezing the dashboard while parking the servos), or **H5/H7** (PWM/hardware).

#### H7. Power Brownout or Stall Reset
- **Confidence:** **Mid-run ESP32 CPU brownout reset is ruled out by CSV `t_ms` continuity; Servo-rail voltage droop / thermal stall under load Needs Bench.**
- **Software Signs Checked in CSVs:**
  - Across all 21 CSV runs, `t_ms` never resets to 0 mid-run (`dt <= 0` count is `0`), and `# ball-plate ready` never re-appears mid-run. This proves the **ESP32 3.3 V rail did not brown out and reset the MCU** during active logging.
  - However, in `run_20261022_134858.csv` at line 340 (`t_ms = 27848`), 32 NUL bytes (`\x00`) are injected right in the middle of the UART transmission `27848,-39.8,109.9,0.0,0.0,15.0\x00...\x0015.00`, immediately followed by a **13.58-second gap** (`t_ms` jumps from `27848` to `41432`). That is a classic signature of a transient USB/ground glitch when both servos were stalled hard against the `15.0°` (`1150 µs`) limit.
  - Furthermore, if the servos are powered from a separate 5 V supply (or a current-limited 5 V rail) that droops below `~4.0 V` when the servos stall at `1150 µs` or `1950 µs`, the **servos** will lose torque or reset their internal potentiometer amplifier while the USB-powered ESP32 keeps running and logging `t_ms` normally!

#### H8. Dashboard or CSV Mismatch (Dashboard Shows `u` Values That Do Not Match Physical Servo State)
- **Confidence:** **Confirmed in Code (3 distinct mechanisms).**
  1. **During `"pos none"` (ball lost), the dashboard displays a stale `u_x_deg / u_y_deg` while the servos are actually parked at `0°` (`1400 µs`):**
     - When `datalog.py` sends `"pos none"`, `esp.ino:104` calls `hold()` (`moveServos(0, 0)` $\rightarrow$ `1400 µs`) and prints `"# no ball"`.
     - Because `"# no ball"` is not written to the CSV file, `useLiveData.ts:89-93` keeps reading the last CSV row and displaying its non-zero `u_x_deg` and `u_y_deg` in `SystemParametersBar.tsx:31-36` (`X Tilt`, `Y Tilt`) and `BallPlateSimulation.tsx:138-167` for the entire duration of the dropout (up to `12.6 s` in `run_20261022_145858.csv` and `40.7 s` in `run_20261022_142409.csv`)!
     - Even worse, `DashboardHeader.tsx:26` sets `STALE_MS = 30000` (`30 seconds`!), so the green `"ESP32 Connected"` badge stays green for 30 seconds after data stops arriving!
  2. **In Runs 1–15 (before `setTiltLimits` was added), `u_x_deg / u_y_deg` in the CSV was clamped at `±15°` while `tiltToPulse` clamped at `[-5.5°, +2.5°]`:**
     - Any `u` between `+2.5°` and `+15.0°` in the CSV/dashboard was clipped to `1150 µs` before reaching `writeMicroseconds()`.
  3. **If `pid 0 0 0` is sent or after the `500 ms` serial timeout (`esp.ino:72-86`):**
     - If `datalog.py` stops sending for `> 500 ms`, `esp.ino:73` calls `hold()` (`1400 µs`) without printing a CSV line, leaving the dashboard frozen on the last `u_x_deg / u_y_deg`.

---

## 6. Phase 4: Servo and Library Research (With Cited Sources)

### 6.1 MG90S Servo Specifications: Genuine TowerPro vs. Clones, `1400 µs` vs. `1500 µs`, and Safe Bench Range
- **Operating Specifications (TowerPro MG90S Datasheet & Standard Reference Data):**
  - **PWM Period / Frequency:** `20 ms` (`50 Hz`).
  - **Pulse Width Range:** Manufacturer spec is `~500 µs` to `2400 µs` for full `~180°` mechanical travel (`1000 µs` to `2000 µs` for standard `~90°–120°` RC travel).
  - **Neutral (Center) Pulse:** **`1500 µs`** (`90°` mechanical midpoint).
  - **Deadband Width:** **`~5 µs`** (`1–5 µs` on digital revisions, up to `5–10 µs` on cheap analog clones).
  - **Operating Voltage:** **`4.8 V to 6.0 V DC`**.
  - **No-Load Speed:** `0.10 s / 60°` at `4.8 V`; `0.08 s / 60°` at `6.0 V`.
  - **Stall Torque:** `1.8 kg·cm` at `4.8 V`; `2.2 kg·cm` at `6.0 V`.
  - **Current Draw:** Idle `~10 mA`; no-load running `~120–250 mA`; **stall / peak startup current `~550 mA to 800 mA` per servo** (two servos starting simultaneously draw **`1.1 A to 1.6 A`**).
  - *Citations:*
    - TowerPro / ServoDatabase MG90S specifications: https://servodatabase.com/servo/towerpro/mg90s
    - ElectronicosCaldas TowerPro MG90S Datasheet PDF: https://www.electronicoscaldas.com/datasheet/MG90S_Tower-Pro.pdf
    - Adafruit Micro Servo reference (`1000–2000 µs` vs extended range): https://learn.adafruit.com/arduino-lesson-14-servo-motors/servo-motors
- **Genuine TowerPro vs. Clone MG90S Parts (Lower-confidence vendor/community reports noted):**
  - Genuine TowerPro MG90S servos use a digital controller IC and metal gear train with smooth response across `~600–2300 µs`.
  - Inexpensive clone "MG90S" servos frequently use analog controller ICs (such as KC5188 / AA51880) with varying potentiometer scaling: some clones sweep only `90°` over `1000–2000 µs` and require `500–2400 µs` for `180°`, while other clones hit their internal mechanical gear end-stop at `< 700 µs` or `> 2100 µs`, stalling the motor, drawing `700+ mA` continuously, overheating, or stripping the first reduction gear.
- **Is `1400 µs` vs. `1500 µs` Plausible as Center, and What Is the Safe Bench Range?**
  - **Servo internal center is always `~1500 µs` (`±20 µs`).** A value of `1400 µs` is **not** the servo's internal center; it is a **`-100 µs` (`~9°–10°` shaft angle) mechanical mounting offset** caused by the coarse spline teeth (`~15°` per tooth on 21-tooth micro servo splines) when pressing the horn onto the shaft.
  - **Safe bench-test range:** Start at **`1500 µs`** and test within **`[1200 µs, 1800 µs]`** first with the linkage disconnected, then within the rig's **`[1150 µs, 1950 µs]`** limits in `50 µs` steps while watching for mechanical binding.

### 6.2 `ESP32Servo` Library Internals (`attach`, `writeMicroseconds`, `setPeriodHertz`, `allocateTimer`, `setTimerWidth`)
- **Direct Source Inspection (`madhephaestus/ESP32Servo`, latest `v3.2.1`):**
  - Repository & headers:
    - `library.properties` (`v3.2.1`): https://raw.githubusercontent.com/madhephaestus/ESP32Servo/master/library.properties
    - `ESP32Servo.h`: https://raw.githubusercontent.com/madhephaestus/ESP32Servo/master/src/ESP32Servo.h
    - `ESP32Servo.cpp`: https://raw.githubusercontent.com/madhephaestus/ESP32Servo/master/src/ESP32Servo.cpp
    - `ESP32PWM.cpp`: https://raw.githubusercontent.com/madhephaestus/ESP32Servo/master/src/ESP32PWM.cpp
  - **Key constants in `ESP32Servo.h`:**
    - `DEFAULT_uS_LOW = 544`, `DEFAULT_uS_HIGH = 2400`
    - `MINIMUM_PULSE_WIDTH = 500`, `MAXIMUM_PULSE_WIDTH = 2500`
    - `DEFAULT_TIMER_WIDTH = 10` (`1024` ticks)
    - `DEFAULT_PULSE_WIDTH = 1500`
    - `DEFAULT_PULSE_WIDTH_TICKS = 4825` *(Bug in library header: `4825` was calculated for 16-bit timer width where `1500 µs -> 4915` ticks, not 10-bit where `1500 µs -> 76` ticks!)*
    - `MAXIMUM_TIMER_WIDTH`: `14` on `ARDUINO_ESP32C3_DEV`, `20` on classic ESP32 (`16` effective in `usToTicks` if set to `16`).
  - **`attach(pin, min, max)` behavior (`ESP32Servo.cpp`):**
    - Enforces `min >= 500` and `max <= 2500`. Here `attach(pin, 500, 2400)` sets `this->min = 500`, `this->max = 2400`.
    - **Crucial bug when `attach()` is called before `setTimerWidth()`:** Inside `Servo::attach(int pin, int min, int max)`:
      ```cpp
      if (this->pinNumber < 0) // we are attaching to a new or previously detached pin; we need to initialize/reinitialize
      {
          this->ticks = DEFAULT_PULSE_WIDTH_TICKS;
          this->timer_width = DEFAULT_TIMER_WIDTH;
          this->timer_width_ticks = pow(2,this->timer_width);
      }
      ```
      Because `attach()` unconditionally resets `this->timer_width = DEFAULT_TIMER_WIDTH` (`10`) when `this->pinNumber < 0`, **calling `setTimerWidth(16)` BEFORE `attach()` is actually wiped out by `attach()`**, while **calling `setTimerWidth(16)` AFTER `attach()`** triggers `pwm.detachPin(this->pinNumber)` followed by `pwm.attachPin(this->pinNumber, this->REFRESH_CPS, this->timer_width)`!
  - **What `setTimerWidth(16)` does when called after `attach()` (`ESP32Servo.cpp` & `ESP32PWM.cpp`):**
    ```cpp
    int ticks = this-> ticks;
    int microseconds = this->ticksToUs(ticks);
    this->timer_width = value;
    this->timer_width_ticks = pow(2,this->timer_width);
    this->ticks = this->usToTicks(microseconds);
    if (this->pinNumber >= 0) {
        pwm.detachPin(this->pinNumber);
        pwm.attachPin(this->pinNumber, this->REFRESH_CPS, this->timer_width);
    }
    ```
    Look at what happens on lines 50–54 of `esp.ino` (`attach` followed immediately by `setTimerWidth(16)` *before* `moveServos(0,0)`):
    1. `attach()` sets `this->ticks = 4825`, `this->timer_width = 10` (`1024`), and calls `pwm.attachPin(pin, 50, 10)`.
    2. `setTimerWidth(16)` converts `ticks = 4825` at 10-bit (`ticksToUs(4825) = 94,238 µs`), rescales to 16-bit (`308,800` ticks), and calls `pwm.detachPin(pin)` + `pwm.attachPin(pin, 50, 16)`.
    3. Look at `ESP32PWM::detachPin(int pin)` in `ESP32PWM.cpp`: it sets `ChannelUsed[pwmChannel] = NULL` and `pwmChannel = -1`, **but on Arduino-ESP32 Core 3.x it forgets to call `ledcDetach(pin)`** (unlike `~ESP32PWM()` at `ESP32PWM.cpp:79` which calls `ledcDetach(pin)`)!
    4. Then `pwm.attachPin(pin, 50, 16)` calls `_ledcSetupTimerFreq` $\rightarrow$ `ledcAttachChannel(pin, 50, 16, channel)` (`ESP32PWM.cpp:96`) on a `pin` that Core 3.x's Peripheral Manager (`periman`) **still considers attached at 10-bit resolution**!

### 6.3 ESP32 Arduino Core 2.x vs. 3.x LEDC API Overhaul
- **Official Documentation ([Espressif Arduino-ESP32 2.x to 3.0 Migration Guide — LEDC](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html#ledc)):**
  - In **Core 2.x** (ESP-IDF 4.4), LEDC used channel-based functions: `ledcSetup(channel, freq, resolution_bits)` and `ledcAttachPin(pin, channel)`. Calling `ledcSetup()` again on the same channel with a new `resolution_bits` (`10` $\rightarrow$ `16`) reconfigured the timer in-place.
  - In **Core 3.0+** (ESP-IDF 5.1+), `ledcSetup` and `ledcAttachPin` were **removed** and replaced by `ledcAttach(pin, freq, resolution_bits)` and `ledcAttachChannel(pin, freq, resolution_bits, channel)` managed by the ESP32 Peripheral Manager (`periman`).
  - **Effect on `ESP32Servo` and this project:**
    - If `ESP32Servo < 3.0.0` is used with Core 3.x, the sketch fails to compile (`ledcSetup was not declared in this scope`).
    - If `ESP32Servo >= 3.0.0` is used with Core 3.x, `ESP32PWM::detachPin(pin)` does not call `ledcDetach(pin)`, whereas `setTimerWidth(16)` after `attach()` calls `detachPin(pin)` followed by `attachPin(pin, 50, 16)` $\rightarrow$ `ledcAttachChannel(pin, 50, 16, channel)`. Meanwhile, `espreset.ino` never calls `setTimerWidth(16)` at all!
    - **How this research changes our code finding:** Known Issue 8 (`CLAUDE.md:67`) assumed `setTimerWidth(16)` should simply be moved *before* `attach()`. Inspection of `ESP32Servo.cpp` proves that moving `setTimerWidth(16)` *before* `attach()` will be **overwritten** by `attach()` (`this->timer_width = DEFAULT_TIMER_WIDTH`)! And calling `setTimerWidth(16)` *after* `attach()` triggers `detachPin()` without `ledcDetach(pin)` on Core 3.x!

### 6.4 ESP32 Strapping Pins: GPIO 2 vs. GPIO 4
- **Official Documentation ([Espressif Boot Mode Selection — GPIO2](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html#gpio2) and [ESP32 Datasheet](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)):**
  - **GPIO 0** and **GPIO 2** determine boot mode on rising edge of `EN` (`CHIP_PU`).
  - To enter serial flashing mode (`DOWNLOAD_BOOT`), **GPIO 0 must be Low** and **GPIO 2 must be Low or floating**.
  - On normal boot (`GPIO 0 = High`), GPIO 2 is ignored for boot mode selection, **but** on almost all ESP32 DevKit boards, GPIO 2 is wired to an onboard blue LED + resistor to GND.
  - **GPIO 4** is a standard GPIO (not a strapping pin, no onboard LED).

### 6.5 USB Serial Auto-Reset (`DTR` / `RTS`) and `pyserial`
- **Official Documentation ([Espressif Automatic Bootloader](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html#automatic-bootloader) and [ESP32 DevKitC v4 Schematic](https://dl.espressif.com/dl/schematics/esp32_devkitc_v4-sch-20180607a.pdf)):**
  - ESP32 dev boards wire the USB-UART bridge (`CP2102` / `CH340`) `DTR` and `RTS` outputs through a two-transistor cross-coupled circuit to `GPIO0` and `EN` (`CHIP_PU`).
  - When `DTR=1, RTS=0`, `GPIO0` is pulled Low; when `DTR=0, RTS=1`, `EN` is pulled Low (resetting the ESP32); when both `DTR=1, RTS=1` or both `0`, both `EN` and `GPIO0` stay High.
  - When `pyserial`'s `serial.Serial(port, BAUD, timeout=2)` (`esp/esp_usb.py:30`) opens the port on macOS/Linux, the OS driver transitions `DTR`/`RTS`, pulsing `EN` Low and resetting the ESP32.
  - To avoid resetting the ESP32 on port open in `pyserial` (when desired), instantiate `ser = serial.Serial()` with no port, set `ser.dtr = False; ser.rts = False`, and then call `ser.open()`. Conversely, if a deterministic reset *is* desired at `datalog.py` startup, `reset_input_buffer()` must be called **immediately before** entering the read loop (not before starting the HTTP server and camera), and `readReply()` / `isDataLine()` must discard any non-float boot/reset garbage bytes.

### 6.6 ESP32 3.3 V PWM Signal Level Driving MG90S at 5 V Supply & Common Ground
- **Signal Voltage Threshold ($V_{IH}$):**
  - The ESP32 GPIO high output is $V_{OH} \approx 3.3\text{ V}$ (or slightly lower on GPIO 2 due to the onboard LED load).
  - Genuine TowerPro MG90S and most CMOS-input digital servos have a logic-high threshold of $V_{IH} \approx 2.0\text{–}2.5\text{ V}$ even when powered at $V_{CC} = 5.0\text{ V}$, so `3.3 V` PWM usually works **provided there is a solid, low-impedance common ground (`GND`) wire between the external 5 V servo power supply and the ESP32 `GND`**.
  - However, some clone MG90S batches use 5 V CMOS controller ICs with $V_{IH} = 0.7 \times V_{CC} = 3.5\text{ V}$ at $V_{CC} = 5.0\text{ V}$, or fail when ground bounce ($I_{\text{stall}} \times R_{\text{GND wire}}$) lifts the servo's local ground by `0.3–0.5 V` during motor current spikes, reducing the effective 3.3 V signal seen by the servo to `< 2.8 V`.
  - Without a common ground between an external 5 V supply and the ESP32, the PWM signal floats relative to the servo and the servo will either not move at all or twitch randomly.

---

## 7. Phase 5: Other Findings Across Firmware, Laptop, Dashboard, and Docs

### 7.1 Serial Contract & Constants Audit Across Sketches and Python

#### Constants Across the Three Sketches
| Constant | `esp/esp.ino` | `esp/esptest/esptest.ino` | `esp/espreset/espreset.ino` | `architecture.md` | Match? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `SERVO_X_PIN` / `SERVO_Y_PIN` | `2` / `4` (`L21-22`) | `2` / `4` (`L22-23`) | `2` / `4` (`L11-12`) | `GPIO 2` / `GPIO 4` (`L146`) | Match |
| `SERVO_US_MIN` / `SERVO_US_MAX` | `500` / `2400` (`L29-30`) | `500` / `2400` (`L30-31`) | `500` / `2400` (`L13-14`) | `500` / `2400` (`L151`) | Match |
| `PULSE_CENTER_X` / `Y` | `1400` / `1400` (`L32-33`) | `1400` / `1400` (`L34-35`) | `1400` / `1400` (`L15-16`) | `1400` (`L152`) | Match |
| `PULSE_MIN` / `PULSE_MAX` | `1150` / `1950` (`L34-35`) | `1150` / `1950` (`L36-37`) | `1150` / `1950` (`L17-18`, unused) | `1150` / `1950` (`L153-154`) | Unused in `espreset.ino` |
| `PULSE_PER_DEG` | `100.0f` (`L37`) | `100.0f` (`L39`) | *Absent* | `100.0` (`L155`) vs **`10` (`L72`)** | **Mismatch in `architecture.md:72`** |
| `SERVO_DIR_X` / `Y` | `-1.0f` / `-1.0f` (`L38-39`) | `-1.0f` / `-1.0f` (`L40-41`) | *Absent* | `-1.0` (`L156`) | Match |
| `KP` / `KI` / `KD` | `0.03` / `0.0` / `0.02` (`L16-18`) | *N/A* | *N/A* | `0.4, 0, 0.15` (`L66`) | Doc example differs |

#### Serial & CSV Schema Contract (`esp.ino` $\leftrightarrow$ `datalog.py` $\leftrightarrow$ Dashboard)
1. **[Confirmed — Laptop] `isDataLine(line)` in `esp/datalog.py:43-45` Does Not Validate Floats:**
   - `esp/datalog.py:43-45`:
     ```python
     def isDataLine(line):
         """True for a data line. Lines starting with # are messages, not data."""
         return line != "" and not line.startswith("#") and len(line.split(",")) == 7
     ```
   - Any line containing 6 commas—including a line prefixed with 27 KB of serial garbage (`\x00\ufffd\x00...17845,-3.9,-23.1,0.0,0.0,0.12,0.69` in 5 CSV runs) or a mid-line NUL burst (`run_20261022_134858.csv:340`)—passes `isDataLine()` and is written directly to the CSV file and `lines` list.
   - If a client connects to `/stream` (`sendStream()`, `esp/datalog.py:102`) when `lines` contains such a row, `toSample(lines[sent])` (`esp/datalog.py:48-50`) calls `float(part)` and crashes with an unhandled `ValueError`.
2. **[Confirmed — Test Suite] `esp/test_datalog.py:1-20` Fails to Catch the `isDataLine` Bug:**
   - `test_datalog.py:7-11` only tests `isDataLine` on `"20,1.5,-0.3,0.0,0.0,0.8,-0.2"`, `"# ball-plate ready"`, `"20,1.5,-0.3"` (too few fields), and `""`. It never tests a 7-field non-numeric line like `"\x00\ufffd,1,2,3,4,5,6"` or the header `"t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg"` (in fact, `isDataLine(HEADER)` returns `True`!).

### 7.2 Documentation vs. Code Discrepancies
Per `CLAUDE.md:24` (*"If code and architecture.md disagree, do not pick a winner. Report it as a question for the user"*), here is every discrepancy found across `README.md`, `architecture.md`, `CLAUDE.md`, and the dashboard docs:

| # | Layer / File & Line | Claim in Documentation | Actual Implementation in Code |
| :-: | :--- | :--- | :--- |
| **D1** | **Docs vs. Firmware**<br>`architecture.md:72` vs `architecture.md:155` & `esp/esp.ino:37` | `architecture.md:72`: *"1° of plate tilt needs about 10 µs of servo pulse (`PULSE_PER_DEG`), so ±15° is ±150 µs around the middle."*<br>`architecture.md:155`: `PULSE_PER_DEG = 100.0` | `esp/esp.ino:37` and `esp/esptest/esptest.ino:39` set `PULSE_PER_DEG = 100.0f`. |
| **D2** | **Docs vs. Firmware**<br>`architecture.md:71,94`<br>`README.md:94,104`<br>`how-to-run/page.tsx:161` | `architecture.md:71`: *"Clamped to ±15° (`TILT_LIMIT`) so the servo can't push the plate too far."*<br>`architecture.md:94`: *"We limit this to ±15° (`TILT_LIMIT`)"* | Working tree `esp/plate.ino:21-26` sets asymmetric limits `tiltMin = -5.50°`, `tiltMax = +2.50°` derived from `[1150, 1950]` around `1400` at `100 µs/deg`. (Git `HEAD` `esp/pid.ino:2` had `TILT_LIMIT = 15.0f`). |
| **D3** | **Docs/Laptop vs. Firmware**<br>`README.md:94,104`<br>`architecture.md:39,65,86,101-106`<br>`esp/datalog.py:21,150,178`<br>`esp/esp.ino:9-10`<br>`how-to-run/page.tsx:161` | All of these document the `sp <x> <y>` serial command (e.g. `sp 50 0`) to change the target setpoint in mm. Even the comment at the top of `esp/esp.ino:9-10` still lists `sp <x> <y>   target position in mm`! | `handleCommand()` (`esp/esp.ino:93-124`) **removed `sp`** in commit `29d51a5`. Sending `sp 50 0` prints `# unknown command: sp 50 0`. Meanwhile `pid.spX` and `pid.spY` remain permanently `0.0` and are still printed as columns 4 and 5 of every CSV line (`esp.ino:138-139`). |
| **D4** | **Docs vs. Laptop**<br>`README.md:56`<br>`CLAUDE.md:50`<br>`esp/datalog.py:6,143,164-167`<br>`how-to-run/page.tsx:86` | Document running `.venv/bin/python esp/datalog.py run1 --mock` (`from mock import Esp`) to run a fake ESP32 without hardware. | `esp/mock.py` was **deleted** in commit `5b0ba2ad`. Running `datalog.py --mock` crashes with `ModuleNotFoundError: No module named 'mock'`. |
| **D5** | **Docs vs. Dashboard**<br>`architecture.md:109-120`<br>`esp/datalog.py:10,69-70,92-112` | `architecture.md:113`: *"`/stream`: Live data using Server-Sent Events (SSE). The browser opens this address once and keeps the connection open."* | The Next.js dashboard (`data_logging/dashboard/app/useLiveData.ts:56-98`) **never connects to `/stream`**. Instead, it polls `GET /runs` and re-downloads the entire `GET /runs/<latest>.csv` file every `500 ms`! |
| **D6** | **Docs vs. Dashboard**<br>`data_logging/dashboard/AGENTS.md:5` vs `package.json:15` | `AGENTS.md:5` states `"Next.js version: 16.2.0"`. | `package.json:15` has `"next": "16.2.3"`. |
| **D7** | **Docs vs. Repo**<br>`CLAUDE.md:23,58,65` | References `analysis/2026-10-22-servo-software.md`. | File does not exist in working tree or git history. |

### 7.3 Firmware Logic Findings (`esp/esp.ino`, `esp/pid.ino`, `esp/plate.ino`)
1. **[Confirmed — Firmware] Unbounded `dt` and Unreset `prevPos` / `integral` After `"pos none"` Dropouts (`esp/esp.ino:72-86,102-106,128-133`):**
   - As proved in Section 5.2 (H3), when the camera loses the ball, `datalog.py` sends `"pos none"` every `22 ms`.
   - Each `"pos none"` updates `lastSerialMs = millis()` (`esp.ino:70`), preventing the `500 ms` serial silence timeout (`esp.ino:72-86`) from ever triggering.
   - `handleCommand("pos none")` (`esp.ino:102-106`) calls `hold()`, which moves the servos to `0, 0` (`1400 µs`), but **does not reset `pid.x.prevPos`, `pid.y.prevPos`, `pid.x.integral`, `pid.y.integral`, or `lastControlMs`**.
   - On the first frame where the ball is found again, `dt = (now - lastControlMs) / 1000.0f` (`esp.ino:130`) equals the **entire duration of the ball dropout** (e.g., `14.79 s` or `40.67 s`), causing `axisStep()` (`pid.ino:29-36`) to divide `(pos - stale_prevPos)` by `dt` and integrate `err * dt` over the entire dropout!
2. **[Confirmed — Firmware] Derivative-on-Measurement Sign and First-Sample Behavior (`esp/pid.ino:28-39`):**
   - `axisStep()` computes `err = sp - pos` (`line 25`) and `speed = (pos - a.prevPos) / dt` (`line 30`, or `0.0f` on the first sample when `isnan(a.prevPos)`), then:
     $$u = k_p \cdot \text{err} + k_i \cdot \text{integral} - k_d \cdot \text{speed}$$
   - The sign `- kd * speed` is **correct** for derivative-on-measurement (avoiding derivative kick on setpoint changes) because $\frac{d(\text{err})}{dt} = -\frac{d(\text{pos})}{dt} = -\text{speed}$.
   - However, because raw camera position `pos` has `±0.1 to ±0.5 mm` pixel jitter at `dt = 0.021 s` (`47.6 Hz`) with no low-pass filter on `speed`, a `0.5 mm` single-frame jitter produces $\text{speed} = \frac{0.5}{0.021} = 23.8\text{ mm/s}$. At `KD = 0.06` (Runs 6–11), that adds `1.43°` (`143 µs`) of high-frequency derivative noise; at `KD = 0.02` (Runs 19–21), it adds `0.48°` (`48 µs`).
3. **[Confirmed — Firmware] First Sample After `pid <kp> <ki> <kd>` Command (`esp/esp.ino:113-120`):**
   - `handleCommand("pid ...")` calls `resetPID(pid)` (`prevPos = NAN`, `integral = 0`), so the next sample has `speed = 0`, which is clean, **except** `lastControlMs` is not reset if `pid` was sent after an idle pause.
4. **[Confirmed — Firmware] Integral Windup During Actuator Saturation (`esp/pid.ino:33-38`):**
   - When `ki > 0` (as in Runs 5–11 where `KI = 0.05`), `a.integral = constrain(a.integral + err * dt, -INTEGRAL_MAX, INTEGRAL_MAX)` (`INTEGRAL_MAX = 500.0f`, `pid.ino:3`) allows `ki * integral` to wind up to `0.05 × 500 = ±25.0°`—which is **10× larger than `tiltMax = +2.50°`**! Even after the ball crosses the center (`err` changes sign), the controller stays pinned at the `1150 µs` or `1950 µs` rail for seconds while unwinding `integral`.

### 7.4 Laptop Vision & Logger Findings (`vision/vision.py`, `esp/datalog.py`, `esp/esp_usb.py`)
1. **[Confirmed — Laptop] Synchronous Single-Threaded Lockstep Loop in `esp/datalog.py:176-200`:**
   - `datalog.py` runs `camera.read()` $\rightarrow$ `findBallMm()` $\rightarrow$ `esp.sendLine()` $\rightarrow$ `readReply(esp)` sequentially in one thread.
   - If the ESP32 ever drops a reply or fails to print `\n`, `readReply(esp)` blocks for `timeout=2` seconds (`esp_usb.py:30`), during which **no camera frames are read** and the OpenCV `VideoCapture` buffer fills with stale frames! When `readReply()` returns, the next 3–5 frames read from `camera.read()` are up to 2 seconds old.
2. **[Confirmed — Laptop] `findPort()` in `esp/esp_usb.py:16-21` Picks the First `"usb"` Port:**
   - `for info in list_ports.comports(): if "usb" in info.device.lower(): return info.device`. If a USB hub, Dock, or second serial device with `"usb"` in its device path is plugged in, `findPort()` may pick the wrong port unless `--port` is passed.
3. **[Confirmed — Laptop] `vision/vision.py:138-139` Recomputes Homography Matrix on Every Frame:**
   - `cv2.getPerspectiveTransform(pts, dst)` depends only on `corners` and `plate_mm`, which never change during a `datalog.py` run, yet it is recomputed on every frame inside `findBallMm()`.

### 7.5 Dashboard Findings (`data_logging/dashboard/`)
1. **[Confirmed — Dashboard] Full-CSV Polling Every `500 ms` Instead of SSE `/stream` (`app/useLiveData.ts:56-98`):**
   - Every `500 ms`, `useLiveData.ts` makes **two** HTTP requests to `127.0.0.1:8000`: first `GET /runs`, then `GET /runs/<latest>.csv`, and re-parses the entire CSV file in JavaScript (`parseCsv`). In a 10-minute run (`run_20261022_122846.csv`, 17,808 rows, ~620 KB), the browser downloads and parses 620 KB twice per second, while `datalog.py`'s `/stream` SSE endpoint goes completely unused.
2. **[Confirmed — Dashboard] `DataLogModal.tsx` Expects Completely Different CSV Column Names (`app/components/DataLogModal.tsx:16-30`):**
   - Look at `DataLogModal.tsx:22-29`:
     ```ts
     time_ms: Number(obj.time_ms ?? 0),
     ball_x: Number(obj.ball_x ?? 0),
     ball_y: Number(obj.ball_y ?? 0),
     plate_rx: Number(obj.plate_rx ?? 0),
     plate_ry: Number(obj.plate_ry ?? 0),
     servo_a: Number(obj.servo_a ?? 0),
     servo_b: Number(obj.servo_b ?? 0),
     ```
   - The actual CSV header (`esp/datalog.py:33`) is `t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg`. None of `time_ms`, `ball_x`, `plate_rx`, or `servo_a` exist in the CSV, so if `DataLogModal` is opened on any real CSV, **every single column displays `0`**!
3. **[Confirmed — Dashboard] Hardcoded `±15°` Scale in `BallPlateSimulation.tsx` and `TelemetryCharts.tsx`:**
   - `BallPlateSimulation.tsx:148,162` scales the X/Y Tilt progress bars by `Math.abs(latest.u_x_deg) / 15`, and `TelemetryCharts.tsx:53` hardcodes `yMin = -15, yMax = 15`. With `setTiltLimits()` clamping `u` to `[-5.5°, +2.5°]`, a fully saturated `+2.50°` command (`1150 µs` hard stop!) looks like only **16.7% of full scale** (`2.5 / 15`) on both the tilt bar and the chart, misleading the user into thinking the servo is nowhere near its limit!
4. **[Confirmed — Dashboard] 30-Second Stale Connection Timeout (`app/components/DashboardHeader.tsx:26`):**
   - `const STALE_MS = 30000` keeps the header status green (`"ESP32 Connected"`) for 30 seconds after the last sample, masking multi-second dropouts.

---

## 8. Bench Test Plan to Separate Software from Hardware (Step by Step)

Because hardware cannot be touched remotely, run the following **5-step bench test sequence** in order. It takes ~10 minutes and cleanly separates software issues from hardware/wiring/power issues for both **S2 (`espreset`)** and **S1 (runtime lag)**.

### Bench Test 1: Pre-Power Mechanical & Wiring Inspection (Power OFF)
1. **Unplug USB and external 5 V power.**
2. **Gently rotate both servo horns by hand** through a small arc:
   - *Pass:* Both horns turn smoothly with slight gear resistance and no clicking/binding.
   - *Fail:* If a horn is jammed against the plate frame or linkage at one end, the linkage geometry or horn spline mounting is mechanically stalled.
3. **Check 3 wires on Servo X (GPIO 2) and Servo Y (GPIO 4):**
   - Brown/Black $\rightarrow$ `GND`; Red $\rightarrow$ `5 V` supply; Orange/Yellow $\rightarrow$ `GPIO 2` (X) and `GPIO 4` (Y).
   - **Verify Common Ground:** If using an external 5 V supply for the servos, verify with a continuity meter (or visual wire trace) that the external 5 V supply `GND` is connected directly to an ESP32 `GND` pin.

### Bench Test 2: Isolate Why `espreset.ino` Did Not Move (Tests S2: "Already at 1400 µs" vs. Dead Servo/PWM)
1. With power **OFF**, gently move both servo horns by hand slightly away from their resting position (about `15°–20°` toward the middle of their free travel).
2. Plug in the ESP32 and turn on 5 V servo power while watching both servos and the **ESP32 onboard blue LED (tied to GPIO 2)**:
   - **Result 2A (Both servos snap back to their position once and hold stiffly; GPIO 2 blue LED glows dimly at ~7% brightness):**
     - **Diagnosis:** `espreset.ino` and the hardware PWM ARE working! The reason `espreset.ino` appeared not to move earlier is that **the servos were already sitting at `1400 µs`** (left there by `esp.ino`'s `hold()` function). If the plate is not level at this position, **`1400 µs` is the wrong center constant for the current horn mounting** (proceed to Bench Test 3).
   - **Result 2B (Servo Y on GPIO 4 snaps and holds, but Servo X on GPIO 2 does not move):**
     - Swap the Servo X and Servo Y signal wires between GPIO 2 and GPIO 4 and press the ESP32 `EN` (Reset) button:
       - If the dead servo stays with **GPIO 2**, the ESP32 GPIO 2 onboard LED load or pin is preventing the 3.3 V signal from driving the servo $\rightarrow$ move `SERVO_X_PIN` from GPIO 2 to a clean GPIO (e.g. GPIO 18, 19, 25, or 26).
       - If the dead servo stays with **Servo X** even on GPIO 4, **Servo X hardware or its 5 V/GND wire is faulty**.
   - **Result 2C (Neither servo moves and both horns remain limp/easy to turn by hand):**
     - Check whether the **onboard blue LED on GPIO 2** is glowing dimly (~7% duty cycle):
       - **Blue LED is glowing dimly:** The ESP32 IS outputting the 50 Hz PWM signal on GPIO 2! The failure is **hardware power/wiring** (missing 5 V on the servo red wires, missing common `GND` between 5 V supply and ESP32, or 3.3 V logic threshold incompatibility on clone servos).
       - **Blue LED is completely OFF or stuck at 100% full brightness:** The ESP32 is **not** generating valid 50 Hz PWM (or failed to boot). Proceed to Bench Test 3 (`esptest.ino` with Serial Monitor).

### Bench Test 3: Interactive Pulse Sweep with `esptest.ino` (Separates `ESP32Servo`/Core Issue from Power & Measures True Center/Range)
1. In Arduino IDE, record your exact versions from:
   - `Tools -> Board -> Boards Manager...` $\rightarrow$ search `esp32` (record version, e.g. `2.0.17` vs `3.0.7` / `3.1.x`).
   - `Sketch -> Include Library -> Manage Libraries...` $\rightarrow$ search `ESP32Servo` (record version, e.g. `1.1.2` vs `3.2.1`).
2. Flash `esp/esptest/esptest.ino` and open **Arduino IDE Serial Monitor at `115200` baud** (`Newline` line ending).
3. Press the `EN` button on the ESP32 and check the Serial Monitor:
   - Verify it prints:
     ```
     # servo test ready
     # pins: X=2 Y=4  center=1400/1400  range=1150..1950
     # pulse X=1400 Y=1400
     ```
4. Type the following commands one by one into the Serial Monitor, waiting 2 seconds between each:
   - `u 1500` (standard MG90S nominal center)
   - `u 1400` (current code center)
   - `u 1600`
   - `u 1300`
   - `x 1500` then `x 1300` (moves ONLY Servo X — halves peak current draw!)
   - `y 1500` then `y 1300` (moves ONLY Servo Y — halves peak current draw!)
5. **Interpret the results:**
   - **If `x 1300` and `y 1300` work one axis at a time, but `u 1300` (both together) stalls, twitches, or prints `ets Jun 8 2016 ... BROWNOUT_RST` in Serial Monitor:** **Confirmed 5 V power supply current-limit / brownout issue.**
   - **If `u 1500` levels the plate better than `u 1400`:** Find the exact microsecond values (`x <us>`, `y <us>`) where the plate is flat with a spirit level or resting ball—those are your true `PULSE_CENTER_X` and `PULSE_CENTER_Y`.
   - **Measure true `PULSE_PER_DEG`:** Command `u <center>`, measure plate angle, then command `u <center - 200>` and `u <center + 200>` and measure the plate tilt change in degrees (using a smartphone inclinometer app placed on the plate). Compute:
     $$\text{PULSE\_PER\_DEG} = \frac{200\text{ µs}}{\Delta\text{tilt\_deg}}$$
     *(This measurement is required before changing `PULSE_PER_DEG` or pulse limits in code.)*

### Bench Test 4: Closed-Loop Serial Trace Without Camera Noise (Tests S1 Firmware Lag)
1. Flash `esp/esp.ino` and open Arduino IDE Serial Monitor at `115200` baud.
2. Type synthetic position steps directly into the Serial Monitor at ~1-second intervals:
   - `pos 0 0` $\rightarrow$ should reply `...,0.0,0.0,0.0,0.0,0.00,0.00` (servos at `1400 µs`).
   - `pos 30 0` $\rightarrow$ should reply `...,30.0,0.0,0.0,0.0,-0.90,0.00` (Servo X moves immediately to `1490 µs`).
   - `pos 60 0` $\rightarrow$ should reply `...,60.0,0.0,0.0,0.0,-1.80,0.00` (Servo X moves immediately to `1580 µs`).
   - `pos -60 0` $\rightarrow$ should reply `...,-60.0,0.0,0.0,0.0,1.80,0.00` (Servo X moves immediately to `1220 µs`).
   - `pos -100 0` $\rightarrow$ replies `u_x = 2.50` (`1150 µs` clamp!).
   - `pos -120 0` $\rightarrow$ replies `u_x = 2.50` (**Servo X does NOT move** because `+2.50°` is already clamped at `1150 µs`!).
3. **Interpretation:** If the servo moves immediately on every step between `pos -60 0` and `pos 60 0`, but does not move between `pos -100 0` and `pos -120 0`, **H1 (the `+2.50°` / `1150 µs` saturation clamp) is 100% confirmed on hardware.**

### Bench Test 5: Camera Dropout (`# no ball`) Inspection During Live Run
1. Run `.venv/bin/python esp/datalog.py test_bench` while watching the terminal output.
2. Roll the ball across all four quadrants of the plate and watch how often `# no ball` prints in the terminal:
   - Every time `# no ball` prints, `esp.ino` calls `hold()` (snapping the servos back to `1400 µs`) while the dashboard freezes on the last `u_x_deg / u_y_deg`.
   - If `# no ball` appears whenever the ball is in a certain corner or moving fast, re-run `.venv/bin/python vision/vision.py` to tune the HSV sliders (`H, S, V`) and verify the 4 red plate corners.

---

## 9. Proposed Fixes (Kept Separate from Findings — Do Not Apply Until Approved)

> **Rule Compliance Note:** None of the proposed fixes below have been applied to the codebase. Proposals that touch calibration constants (`PULSE_CENTER_X/Y`, `PULSE_PER_DEG`, `PULSE_MIN/MAX`) are explicitly marked **[Requires Bench Measurement First]** and never hard-code a tilt limit.

### 9.1 Firmware Fixes (`esp/`)

1. **Fix `ESP32Servo` Timer-Width Initialization Order in `esp/esp.ino:46-54`, `esp/esptest/esptest.ino:50-56`, and `esp/espreset/espreset.ino:20-27`**
   - **Problem:** In `ESP32Servo`, `attach()` resets `this->timer_width = 10` (`19.53 µs/tick`) and `this->ticks = 4825`, while calling `setTimerWidth(16)` after `attach()` calls `detachPin()` without `ledcDetach(pin)` on Core 3.x. And `espreset.ino` omits `setTimerWidth(16)` completely and skips `PULSE_MIN/MAX` clamping.
   - **Proposed Change (`esp/espreset/espreset.ino:20-27`):** Clamp the center pulse to `[PULSE_MIN, PULSE_MAX]` and match the initialization sequence of `esp.ino` / `esptest.ino`:
     ```cpp
     int pulseX = constrain(PULSE_CENTER_X, PULSE_MIN, PULSE_MAX);
     int pulseY = constrain(PULSE_CENTER_Y, PULSE_MIN, PULSE_MAX);
     servoX.writeMicroseconds(pulseX);
     servoY.writeMicroseconds(pulseY);
     ```
   - **Note on `setTimerWidth(16)` (`esp/esp.ino:50-54`, `esp/esptest/esptest.ino:52-56`, `esp/espreset/espreset.ino:22-27`):** Verify the installed `ESP32Servo` and Arduino-ESP32 Core versions in Bench Test 3 first. If using `ESP32Servo >= 3.0.0` on Core 3.x where `setTimerWidth(16)` after `attach()` triggers `detachPin()` without `ledcDetach()`, either call `ledcDetach(pin)` before re-attaching or keep a single `attach()` call after verifying tick resolution on GPIO 2/4.

2. **Reset PID State (`prevPos`, `integral`) and `lastControlMs` on `"pos none"` in `esp/esp.ino:102-106`**
   - **Problem:** During `"pos none"` (ball lost), `lastSerialMs` keeps updating every `22 ms` so the `500 ms` timeout (`esp.ino:72-86`) never fires, and `handleCommand("pos none")` calls `hold()` without resetting `prevPos`, `integral`, or `lastControlMs`. When the ball reappears after a multi-second gap, `dt` spans the entire gap and corrupts `speed` and `integral`.
   - **Proposed Change (`esp/esp.ino:102-106`):**
     ```cpp
     if (arg == "none") {
       hold();
       resetPID(pid);
       lastControlMs = 0;
       return;
     }
     ```
     And in `controlStep()` (`esp/esp.ino:128-133`), guard against `lastControlMs == 0` or `dt > 0.2f`:
     ```cpp
     unsigned long now = millis();
     float dt = (lastControlMs == 0) ? 0.02f : (now - lastControlMs) / 1000.0f;
     if (dt <= 0.0f || dt > 0.2f) dt = 0.02f;
     lastControlMs = now;
     ```

3. **Restore the `sp <x> <y>` Command in `esp/esp.ino:93-124` (or Remove It from Docs/Logger Depending on User Decision)**
   - **Problem:** `sp <x> <y>` is documented in `README.md`, `architecture.md`, `esp.ino:9-10`, `datalog.py:21,150,178`, and `how-to-run/page.tsx:161`, and `sp_x_mm,sp_y_mm` are columns 4–5 of the CSV, but `handleCommand()` rejects `sp` as an unknown command.
   - **Proposed Change (`esp/esp.ino:112`):**
     ```cpp
     if (cmd == "sp") {
       float sx, sy;
       if (sscanf(arg.c_str(), "%f %f", &sx, &sy) == 2) {
         pid.spX = sx;
         pid.spY = sy;
       }
       return;
     }
     ```

4. **[Requires Bench Measurement First] Re-Center Servo Horns and Update `PULSE_CENTER_X/Y`, `PULSE_MIN/MAX`, and `PULSE_PER_DEG` (`esp/esp.ino:32-37`, `esp/esptest/esptest.ino:34-39`, `esp/espreset/espreset.ino:15-18`)**
   - **Problem:** `PULSE_CENTER = 1400` in `[1150, 1950]` leaves only `250 µs` of travel on the `1150` side, which at `PULSE_PER_DEG = 100.0` clamps positive tilt at **`+2.50°`** (`setTiltLimits()` in `esp/plate.ino:21-26`), pinning the servo at `1150 µs` for 35% of `run_20261022_142409.csv`.
   - **Proposed Action (after Bench Test 3):** Using the measured level pulse (`PULSE_CENTER_X/Y`), measured safe mechanical end-stops (`PULSE_MIN/MAX`), and measured `PULSE_PER_DEG` from Bench Test 3, update those constants in all three sketches and `architecture.md:148-158`. Because `setTiltLimits()` (`esp/plate.ino:21-26`) already computes `tiltMin` and `tiltMax` dynamically from `PULSE_MIN`, `PULSE_MAX`, `PULSE_CENTER_X/Y`, `PULSE_PER_DEG`, and `SERVO_DIR_X/Y`, no tilt limit is ever hard-coded.

### 9.2 Laptop Fixes (`esp/datalog.py`, `esp/esp_usb.py`, `esp/test_datalog.py`)

1. **Restore Numeric Validation in `isDataLine(line)` (`esp/datalog.py:43-45`) and Sanitize Serial Input (`esp/esp_usb.py:41-43`)**
   - **Problem:** `isDataLine(line)` only checks `len(line.split(",")) == 7`, allowing 27 KB bursts of `\x00\ufffd\x00` prefixed to line 2 (in 5 CSV files) and mid-line NUL bytes (`run_20261022_134858.csv:340`) to be written into the CSV files and `lines` list.
   - **Proposed Change (`esp/datalog.py:43-45`):**
     ```python
     def isDataLine(line):
         """True for a data line. Lines starting with # are messages, not data."""
         if line == "" or line.startswith("#"):
             return False
         parts = line.split(",")
         if len(parts) != len(COLUMNS):
             return False
         try:
             for part in parts:
                 float(part)
             return True
         except ValueError:
             return False
     ```
   - **Proposed Change (`esp/esp_usb.py:41-43`):** Strip NUL bytes (`\x00`) and non-ASCII replacement characters (`\ufffd`) before returning from `readLine()`, and call `esp.port.reset_input_buffer()` in `datalog.py` right before entering the `while True` loop (after `openCamera()` and `startWebsiteServer()` have finished).
   - **Proposed Change (`esp/test_datalog.py`):** Add unit test assertions `assert not isDataLine(HEADER)` and `assert not isDataLine("\x00\ufffd0,1,2,3,4,5,6")`.

### 9.3 Dashboard Fixes (`data_logging/dashboard/`)

1. **Fix CSV Column Mapping in `data_logging/dashboard/app/components/DataLogModal.tsx:16-30`**
   - **Problem:** `DataLogModal.tsx` reads `obj.time_ms`, `obj.ball_x`, `obj.ball_y`, `obj.plate_rx`, `obj.plate_ry`, `obj.servo_a`, `obj.servo_b`, which do not match `t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg`, resulting in all zeros.
   - **Proposed Change:** Map `t_ms`, `x_mm`, `y_mm`, `sp_x_mm`, `sp_y_mm`, `u_x_deg`, `u_y_deg` directly.
2. **Surface `"No Ball / Hold"` State and Lower Stale Threshold in `DashboardHeader.tsx:26`**
   - **Problem:** `STALE_MS = 30000` (`30 s`) hides multi-second `"# no ball"` dropouts while `SystemParametersBar.tsx` displays the frozen last `u_x_deg / u_y_deg`.
   - **Proposed Change:** Reduce `STALE_MS` in `DashboardHeader.tsx:26` from `30000` to `1500` (`1.5 s`), or switch `useLiveData.ts` to consume `/stream` (SSE) and emit a live `"ball_visible"` flag when `"# no ball"` is received.

---

## 10. Open Questions for the User

1. **Disagreement Between Code and `architecture.md` on `PULSE_PER_DEG` (`100.0` vs. `10.0`):**
   - `esp/esp.ino:37`, `esp/esptest/esptest.ino:39`, and the table in `architecture.md:155` specify `PULSE_PER_DEG = 100.0`, whereas the prose in `architecture.md:72` states: *"1° of plate tilt needs about 10 µs of servo pulse (`PULSE_PER_DEG`), so ±15° is ±150 µs around the middle."*
   - With `PULSE_PER_DEG = 100.0` and `PULSE_CENTER = 1400` in `[1150, 1950]`, the plate's maximum positive tilt is only **`+2.50°`** (`250 µs / 100 µs/deg`), which saturates the servo for 35% of `run_20261022_142409.csv`. Was `PULSE_PER_DEG = 100.0` measured with an inclinometer on the plate, or was it increased from `10.0` to `100.0` in commit `29d51a5` to make the servos move further for a given PID output `u`?

2. **Disagreement Between Code and Docs on `TILT_LIMIT` (`±15°` vs. `[-5.5°, +2.5°]`):**
   - `architecture.md:71,94` and the dashboard charts (`TelemetryCharts.tsx:53`, `BallPlateSimulation.tsx:148,162`) use a symmetric `±15°` tilt range, while the uncommitted working tree (`esp/plate.ino:21-26`, `esp/pid.ino:17-22,38`) clamps PID output `u` to the pulse-derived limits `[-5.50°, +2.50°]`. Should `architecture.md` be updated to describe the dynamic `setTiltLimits()` behavior?

3. **Disagreement Between Code and Docs on the `sp <x> <y>` Serial Command and `--mock` Mode:**
   - Should `sp <x> <y>` be restored in `esp/esp.ino:handleCommand()` (matching `README.md`, `architecture.md`, `datalog.py`, and the CSV `sp_x_mm,sp_y_mm` columns), or should `sp` be removed from the docs and `datalog.py`?
   - Similarly, should `esp/mock.py` be restored for `datalog.py --mock`, or should `--mock` be removed from `datalog.py` and `README.md`?

4. **Confirming S3 ("The `espreset` Sketch Works Fine 'on Arduino'") and Local Environment Details:**
   - Please confirm which of the following you meant by *"works on Arduino"*:
     - **(A)** Tested on a separate 5 V Arduino board (e.g., Arduino Uno/Nano/Mega) using standard `<Servo.h>`?
     - **(B)** Flashed `espreset.ino` to this ESP32 from the Arduino IDE (with `datalog.py` not running)?
     - **(C)** Ran a standard Arduino Servo example sketch (e.g., `Sweep` or `servo.write(90)`) on this ESP32?
     - **(D)** Ran an earlier version of `espreset.ino` (before Oct 22 13:01 when `PULSE_CENTER` was `1500 µs`)?
   - Please also confirm your exact bench setup:
     1. **Arduino IDE version** and **ESP32 Board Package version** (`Tools -> Board -> Boards Manager -> esp32`).
     2. **`ESP32Servo` library version** (`Sketch -> Include Library -> Manage Libraries -> ESP32Servo`).
     3. **Selected Board** in `Tools -> Board`.
     4. **Servo power source:** Are the two MG90S servos powered from the ESP32 `5V`/`VIN` pin over USB, or from an external 5 V power supply (and is its `GND` tied to ESP32 `GND`)?
     5. **Which servo(s) exhibit S1/S2:** Both Servo X (GPIO 2) and Servo Y (GPIO 4), or only one of them?
