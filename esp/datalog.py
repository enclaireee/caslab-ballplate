# datalog.py - the one program that talks to the ESP32.
#
# It runs the camera, sends the ball position to the ESP32, prints the reply,
# saves every data line to a CSV file, and hands the data to the website.
# Only one program can open the USB port, which is why all of this lives here.
#
# Run:  .venv/bin/python esp/datalog.py run1            real ESP32 + camera
#       .venv/bin/python esp/datalog.py run1 --mock     fake ESP32, no hardware
#       .venv/bin/python esp/datalog.py                name from the date and time
# Stop: Ctrl+C
#
# Website addresses (only this laptop can open them):
#   http://127.0.0.1:8000/stream          live data, one JSON sample per line (SSE)
#   http://127.0.0.1:8000/runs            list of saved CSV files
#   http://127.0.0.1:8000/runs/run1.csv   one saved CSV file

import argparse
import json
import select
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The camera code lives in vision/, and mock.py / esp_usb.py live next to this
# file. Import them by their plain names, whatever folder you run this from.
sys.path.insert(0, str(Path(__file__).parent.parent / "vision"))
sys.path.insert(0, str(Path(__file__).parent))

HEADER = "t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg"
COLUMNS = HEADER.split(",")

PORT = 8000

RUNS_FOLDER = Path(__file__).parent.parent / "data_logging" / "runs"

# Every data line of this run, so the website stream can send the new ones.
# ponytail: grows forever (~3 MB per hour), fine for lab runs of a few minutes.
lines = []


def isDataLine(line):
    """True for a data line. Lines starting with # are messages, not data."""
    return line != "" and not line.startswith("#") and len(line.split(",")) == 7


def toSample(line):
    """'20,1.5,...' -> {"t_ms": 20.0, "x_mm": 1.5, ...} so the website can read it."""
    values = [float(part) for part in line.split(",")]
    return dict(zip(COLUMNS, values))


def listRuns():
    """Names of all saved CSV files, oldest first."""
    return sorted(file.name for file in RUNS_FOLDER.glob("*.csv"))


class Website(BaseHTTPRequestHandler):
    """Answers the website's requests. Python runs do_GET for every GET request."""
    def do_GET(self):
        if self.path == "/stream":
            self.sendStream()
        elif self.path == "/runs":
            self.sendText(json.dumps(listRuns()), "application/json")
        elif self.path.startswith("/runs/"):
            name = self.path[len("/runs/"):]
            # Only send files that are in the list, so nobody can ask for /runs/../secret
            if name in listRuns():
                self.sendText((RUNS_FOLDER / name).read_text(), "text/csv")
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def sendText(self, text, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # The Next.js page runs on port 3000, a different "site" than port 8000.
        # Browsers block that unless we say it's allowed:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode())

    def sendStream(self):
        """Keep the connection open and send every new sample (Server-Sent Events)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        sent = len(lines)  # start from now, not from the beginning of the run
        try:
            while True:
                while sent < len(lines):
                    sample = toSample(lines[sent])
                    # SSE format: "data: <text>" and an empty line after each message
                    self.wfile.write(f"data: {json.dumps(sample)}\n\n".encode())
                    sent = sent + 1
                self.wfile.flush()
                time.sleep(0.02)  # check for new lines 50 times per second
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser tab was closed, stop this stream

    def log_message(self, format, *args):
        pass  # don't print every web request, the data lines are enough


def startWebsiteServer():
    # 127.0.0.1 = only this laptop can connect, not other people on the wifi
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Website)
    # The server waits for requests forever, so it gets its own thread (runs side by side
    # with the main loop). daemon=True: it stops by itself when the main program stops.
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Website data at http://127.0.0.1:{PORT}/stream")


def main():
    parser = argparse.ArgumentParser(description="Save a ball-and-plate run to a CSV file.")
    parser.add_argument("name", nargs="?", help="file name, e.g. run1 (default: date and time)")
    parser.add_argument("--mock", action="store_true", help="use the fake ESP32 (no hardware)")
    parser.add_argument("--port", help="USB port of the ESP32 (default: find it)")
    args = parser.parse_args()

    # File name: the one you typed, or one made from the date and time,
    # so a new run never overwrites an old one.
    name = args.name or time.strftime("run_%Y%m%d_%H%M%S.csv")
    if not name.endswith(".csv"):
        name = name + ".csv"
    RUNS_FOLDER.mkdir(parents=True, exist_ok=True)  # make the folder if it's not there yet
    filename = RUNS_FOLDER / name

    # Two ways to get data lines, same three functions afterwards:
    #   --mock    the fake ESP32 makes its own ball, no camera, no hardware
    #   default   the camera finds the ball and the real ESP32 runs the PID
    camera = None
    if args.mock:
        from mock import Esp
        esp = Esp()
        print("Using the fake ESP32 (no hardware needed).")
    else:
        import vision
        from esp_usb import Esp
        vision.load_settings()
        camera = vision.openCamera()
        esp = Esp(port=args.port)
        print("Using the real ESP32 and the camera.")

    startWebsiteServer()
    csv_file = open(filename, "w")
    csv_file.write(HEADER + "\n")
    print("Saving to", filename, "- press Ctrl+C to stop")

    try:
        while True:
            # A command typed here goes to the ESP32: sp 50 0, pid 0.4 0 0.15
            if select.select([sys.stdin], [], [], 0)[0]:
                command = sys.stdin.readline().strip()
                if command:
                    esp.sendLine(command)

            if camera is not None:
                # 1. Where is the ball? Tell the ESP32, so it can do one control step.
                ok, frame = camera.read()
                ball = vision.findBallMm(frame) if ok else None
                if ball is None:
                    esp.sendLine("pos none")
                else:
                    esp.sendLine(f"pos {ball[0]:.1f} {ball[1]:.1f}")

            # 2. Read the answer (one data line, or a # message).
            line = esp.readLine()
            if isDataLine(line):
                csv_file.write(line + "\n")
                csv_file.flush()  # write to disk now, so nothing is lost if it crashes
                lines.append(line)  # the website stream picks it up from here
            print(line)
    except KeyboardInterrupt:
        print("Stopped. Data saved in", filename)
    finally:
        csv_file.close()
        if camera is not None:
            camera.release()


if __name__ == "__main__":
    main()
