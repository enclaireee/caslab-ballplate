# Ball and Plate

Control Lab Task 4: an ESP32 keeps a ball at a setpoint on a tilting plate, using a camera as the sensor and PID control. How it all fits together: [architecture.md](architecture.md).

## Setup (once)

From the project folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run everything with `.venv/bin/python` (Homebrew Python blocks installing packages globally).

## 1. Vision: find the ball

```bash
.venv/bin/python vision/vision.py
```

- `p` = drag a box over the black plate, then Enter
- threshold slider (in the `mask` window): move it until only the ball is white
- `q` = save the settings to `vision/settings.json` and quit

Mac: if the camera doesn't open, allow it in System Settings → Privacy & Security → Camera for the app you run it from (e.g. VS Code), then restart that app.

## 2. Data logging: save a run

```bash
.venv/bin/python esp/datalog.py run1
```

- Saves to `data_logging/runs/run1.csv` (no name = a name with the date and time).
- Also starts the web server for the dashboard at `http://127.0.0.1:8000`.
- `Ctrl+C` stops it.

The data comes from `esp/mock.py` (a fake ESP32) for now. Once `esp/esp_usb.py` exists, switch to the real ESP32 by changing the import line at the top of `esp/datalog.py`:

```python
# from mock import Esp
from esp_usb import Esp
```

## 3. Dashboard

Keep `datalog.py` running, and in a second terminal:

```bash
cd data_logging/dashboard
npm install   # first time only
npm run dev
```

Then open `http://localhost:3000`.
