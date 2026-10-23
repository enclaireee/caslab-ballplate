# Ball and Plate: instructions for Claude

A two-axis ball-on-plate rig for Control Lab Task 4. A webcam finds the ball, the laptop sends its position to an ESP32 over USB, the ESP32 runs one PID per axis and tilts the plate with two MG90S servos, and the laptop logs each control step to CSV for a Next.js dashboard.

## Before changing or diagnosing anything

1. Read `architecture.md`. Its "Servo pulse and tilt (source of truth)" section defines the pulses, the tilt-to-pulse conversion, the tilt limits and the PID units. Follow it rather than re-deriving them. If the code and that section disagree, ask which one is right, then fix the other in the same change.
2. Read the newest file in `analysis/` and the "Known open issues" list below. Do not re-derive an issue that is already listed. Check whether it is still in the code.
3. Scan the whole project before concluding anything. A symptom can come from the firmware, the laptop (camera, serial, logger), the data, the docs, the dashboard or the hardware. Name the layer for every finding.

## Project map

| Path | What it is | Runs on |
|---|---|---|
| `esp/esp.ino`, `pid.ino`, `plate.ino`, `pid.h` | Main firmware: loop, `pos` command, PID, tilt to pulse | ESP32 (Arduino IDE, ESP32Servo library) |
| `esp/esptest/esptest.ino` | Servo test: sweeps the 8 extreme directions, forever | ESP32 |
| `esp/esptest2/esptest2.ino` | Servo test from the Serial Monitor: `test X+Y-` creeps slowly to that limit, `stop`, `flat` | ESP32 |
| `esp/espreset/espreset.ino` | Sets both servos to the centre pulse once, prints it, then stops | ESP32 |
| `esp/datalog.py`, `esp/esp_usb.py` | Camera to `pos` lines to ESP32, then CSV and a local web server | Laptop, Python 3 in `.venv` |
| `vision/vision.py`, `vision/settings.json` | Ball detection, pixel to mm, plate box and threshold | Laptop, OpenCV |
| `data_logging/runs/*.csv` | Recorded runs. These are evidence: never edit or delete them. | Data |
| `data_logging/dashboard/` | Next.js dashboard: Live (`/`), Runs (`/runs`), Setup | Laptop, Node |
| `analysis/` | Analysis reports and the evidence behind them | Laptop |
| `architecture.md`, `README.md`, `CLAUDE.md` | Design, how-to and this file | Docs |

Skip these when analysing: `.venv/` (macOS only, cannot run on Linux), `data_logging/dashboard/.next/`, `node_modules/`, `__pycache__/`, `.playwright-mcp/`.

## Hardware

- ESP32 dev board. Servo X on GPIO 2, servo Y on GPIO 4.
- Two MG90S servos: 4.8 to 6 V, 500 to 2400 µs pulses at 50 Hz, 180° of travel, stall current about 650 to 800 mA. They need their own 5 V supply with the grounds joined. Powering them from the ESP32 USB or 3.3 V rail can cause brownout resets.
- Webcam (`CAMERA` in `vision/vision.py`). Plate nominally 250 × 250 mm, not yet measured.

## Control chain and units

camera → `vision.findBallMm` (mm, picture y flipped) → `pos x y` over USB → `controlStep` → `axisStep` per axis (tilt in degrees) → `moveServos` / `tiltToPulse` → `writeMicroseconds` → plate → ball.

The ESP32 prints one CSV line per control step: `t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg`.

`u_x_deg` and `u_y_deg` are the commanded tilt. Nothing measures the plate or the servo angle. The dashboard's "tilt" is `u`.

## Rules for changes

- These constants must match in `esp/esp.ino`, `esp/esptest/esptest.ino`, `esp/esptest2/esptest2.ino` and `esp/espreset/espreset.ino`: pins, `PULSE_CENTER_X/Y`, `SERVO_US_MIN/MAX`, `PULSE_MIN/MAX`, `PULSE_PER_DEG`, `SERVO_DIR_X/Y`. Change every copy in the same change.
- Keep the timer setup identical in all four sketches: `ESP32PWM::allocateTimer`, `setPeriodHertz(50)`, `attach()`, then `setTimerWidth(16)`.
- `setTiltLimits()` is the only place that computes `pid.x/y.tiltMin/tiltMax`. Never hard-code a tilt limit.
- `PLATE_HALF_MM` in the dashboard must equal half of `PLATE_W_MM` / `PLATE_H_MM` in `vision/vision.py`; change them together.
- `hold()` must level the plate, reset both PID axes and set `lastControlMs = 0`, so no old speed or integral survives a gap.
- Do not change `PULSE_PER_DEG`, the pulse limits, the gains or the direction without a measurement, and cite that measurement.
- Keep the beginner style: short functions, plain comments that say why. The code is explained to the lab assistant (aslab).
- Do not edit `data_logging/runs/`, `.venv/` or `.next/`.
- Do not commit or push unless asked.
- Put proposed firmware or laptop fixes in a report first. Apply them only when asked.

## How to analyse (the procedure)

1. **Inventory.** List what you read and what you skipped, and why.
2. **Contract.** Compare the serial format on both sides (`handleCommand`, `controlStep` in `esp.ino` against `readReply`, `isDataLine` in `datalog.py`, and `parseCsv` in `dashboard/app/config.ts`). Compare the CSV header with the firmware's `printf`. Compare the pulse and tilt formulas with `architecture.md`. Check every copied constant across the three sketches.
3. **Docs against code.** Find every command, number and claim in `README.md` and `architecture.md` that the code does not implement.
4. **Firmware logic.** Check `dt` after gaps, the derivative (speed from position, not from error), what state survives the timeout and `pos none` paths, anti-windup, the first sample after `hold()`, and the timer-width call order.
5. **Runtime evidence.** Use the CSV files. Measure the effective rate, the gaps over 200 ms, the time at each tilt limit, whether `u` matches `kp*(sp − x) − kd*speed` (fit the gains per run), the jumps after gaps and how often the pulse really changes. Gains change between runs, so say which run used which firmware.
6. **Laptop.** Check camera timing and buffering, the mm scale per axis (`PLATE_W_MM`/`PLATE_H_MM` against the plate box in `settings.json`), mirroring, threshold and how often `pos none` is sent.
7. **Hardware or software.** For each symptom, say whether software can explain it, and name the bench test that separates hardware from software.
8. **Tests.** State what the tests cover and what is untested. There are currently no automated tests in the repo.

## Known open issues (as of 2026-10-23)

Confirmed from the code and the logs. Details and evidence: `analysis/2026-10-22-servo-no-move.md`.

1. `PULSE_PER_DEG = 100` is an unmeasured test value. Every tilt, limit and dashboard degree depends on it.
2. The plate size is nominal 250 × 250 mm. The saved plate box is 236 × 183 px, so the scale differs per axis (about 1.06 mm/px in x, 1.37 mm/px in y).
3. The derivative amplifies camera pixel steps. At 24 fps, one pixel is about 30 to 40 mm/s of apparent speed, which is 0.6 to 0.8° of noise per frame at `KD = 0.02`.
4. `SERVO_US_MAX = 2500` is above the MG90S spec of 2400 µs.
5. The setpoint is fixed at (0,0), so the Runs page step table stays empty for new runs (it needs a setpoint change). Use the position chart for the release test.
6. No automated test covers the PID, the tilt mapping or the serial parser.

## Report format (for analysis)

- Start with the answer in 3 to 5 sentences: what is confirmed, what is likely, what is unknown.
- For each finding give: layer (firmware / laptop / data / docs / hardware), file and line, evidence (numbers or a quoted line), confidence (confirmed / likely / guess), and one test that would confirm or rule it out.
- Keep proposed fixes separate from findings, and do not apply them.
- Write full file paths.
