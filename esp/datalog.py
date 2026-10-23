# datalog.py - the one program that talks to the ESP32.
#
# It runs the camera, sends the ball position to the ESP32, saves every data
# line to a CSV file, and serves those files to the dashboard.
# Only one program can open the USB port, which is why all of this lives here.
#
# Run:  .venv/bin/python esp/datalog.py run1            real ESP32 + camera
#       .venv/bin/python esp/datalog.py                name from the date and time
# Stop: Ctrl+C
#
# Website addresses (only this laptop can open them):
#   http://127.0.0.1:8000/runs            list of saved CSV files
#   http://127.0.0.1:8000/runs/run1.csv   one saved CSV file

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The camera code lives in vision/, and esp_usb.py lives next to this file.
# Import them by their plain names, whatever folder you run this from.
sys.path.insert(0, str(Path(__file__).parent.parent / "vision"))
sys.path.insert(0, str(Path(__file__).parent))

HEADER = "t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg"

PORT = 8000

RUNS_FOLDER = Path(__file__).parent.parent / "data_logging" / "runs"


def isDataLine(line):
    """True only for a well-formed 7-number CSV line, never for startup noise."""
    if line == "" or line.startswith("#"):
        return False
    parts = line.split(",")
    if len(parts) != 7:
        return False
    try:
        for part in parts:
            float(part)
    except ValueError:
        return False
    return True


def readReply(esp):
    """Read until the answer to our pos line: a data line or "# no ball".
    Other messages (like "# timeout") are printed and skipped, so we never fall
    one line behind. "" means the ESP32 did not answer, so stop waiting."""
    while True:
        line = esp.readLine()
        if isDataLine(line) or line == "# no ball" or line == "":
            return line
        print(line)


def listRuns():
    """Names of all saved CSV files, oldest first."""
    return sorted(file.name for file in RUNS_FOLDER.glob("*.csv"))


class Website(BaseHTTPRequestHandler):
    """Answers the dashboard's GET requests for the run list and one CSV."""
    def do_GET(self):
        if self.path == "/runs":
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
        # Browsers block that unless we say it is allowed:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, format, *args):
        pass  # don't print every web request, the data lines are enough


def startWebsiteServer():
    # 127.0.0.1 = only this laptop can connect, not other people on the wifi
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Website)
    # The server waits for requests forever, so it gets its own thread (runs side
    # by side with the main loop). daemon=True: it stops when the main program stops.
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Website data at http://127.0.0.1:{PORT}/runs")


def main():
    parser = argparse.ArgumentParser(description="Save a ball-and-plate run to a CSV file.")
    parser.add_argument("name", nargs="?", help="file name, e.g. run1 (default: date and time)")
    parser.add_argument("--port", help="USB port of the ESP32 (default: find it)")
    args = parser.parse_args()

    # File name: the one you typed, or one made from the date and time.
    # Leave it out to keep every run without overwriting an older one.
    name = args.name or time.strftime("run_%Y%m%d_%H%M%S.csv")
    if not name.endswith(".csv"):
        name = name + ".csv"
    RUNS_FOLDER.mkdir(parents=True, exist_ok=True)  # make the folder if it is missing
    filename = RUNS_FOLDER / name

    # The camera finds the ball and the real ESP32 runs the PID.
    import vision
    from esp_usb import Esp

    vision.loadSettings()
    camera = vision.openCamera()
    if not camera.isOpened():
        sys.exit("Cannot open the camera. Check CAMERA in vision/vision.py and the camera permission.")
    esp = Esp(port=args.port)
    print("Using the real ESP32 and the camera.")

    startWebsiteServer()
    csv_file = open(filename, "w")
    csv_file.write(HEADER + "\n")
    print("Saving to", filename, "- press Ctrl+C to stop")

    # Throw away bytes that arrived while the camera and web server were starting.
    esp.clearBuffer()

    try:
        while True:
            # 1. Where is the ball? (x, y) in mm, or None when it is hidden.
            ok, frame = camera.read()
            ball = vision.findBallMm(frame) if ok else None

            # 2. Send the position to the ESP32, which does one control step.
            if ball is None:
                esp.sendLine("pos none")
            else:
                esp.sendLine(f"pos {ball[0]:.1f} {ball[1]:.1f}")

            # 3. Read the reply and save it if it is a data line.
            line = readReply(esp)
            if isDataLine(line):
                csv_file.write(line + "\n")
                csv_file.flush()  # write to disk now, so nothing is lost if it crashes
    except KeyboardInterrupt:
        print("Stopped. Data saved in", filename)
    finally:
        csv_file.close()
        camera.release()


if __name__ == "__main__":
    main()
