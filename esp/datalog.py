# datalog.py - read data lines from the ESP32, show them, save them to a CSV file,
# and give the data to the website (Next.js dashboard).
#
# Run:  python esp/datalog.py            -> saves to data_logging/runs/run_<date>_<time>.csv
#       python esp/datalog.py test1.csv  -> saves to data_logging/runs/test1.csv
# Stop: Ctrl+C
#
# Website addresses (only this laptop can open them):
#   http://127.0.0.1:8000/stream          live data, one JSON sample per line (SSE)
#   http://127.0.0.1:8000/runs            list of saved CSV files
#   http://127.0.0.1:8000/runs/test1.csv  one saved CSV file

import json
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
# Mock ESP
from mock import Esp

HEADER = "t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg"
COLUMNS = HEADER.split(",")

PORT = 8000

RUNS_FOLDER = Path(__file__).parent.parent / "data_logging" / "runs"

# Every data line of this run, so the website stream can send the new ones.
# ponytail: grows forever (~3 MB per hour), fine for lab runs of a few minutes.
lines = []


def isDataLine(line):
    """True if the line is a data line. Lines starting with # are just messages."""
    if line == "" or line.startswith("#"):
        return False
    # A data line has exactly 7 numbers. Anything else is a broken line (e.g. cut off
    # while the ESP32 was starting), so we don't save it.
    parts = line.split(",")
    if len(parts) != 7:
        return False
    try:
        for part in parts:
            float(part)
    except ValueError:
        return False
    return True


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


class Server(ThreadingHTTPServer):
    def server_bind(self):
        # The normal server_bind also looks up this laptop's network name, which takes
        # ~35 s on some Macs. We don't need the name, so only do the basic part.
        socketserver.TCPServer.server_bind(self)


def startWebsiteServer():
    # 127.0.0.1 = only this laptop can connect, not other people on the wifi
    server = Server(("127.0.0.1", PORT), Website)
    # The server waits for requests forever, so it gets its own thread (runs side by side
    # with the main loop). daemon=True: it stops by itself when the main program stops.
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Website data at http://127.0.0.1:{PORT}/stream")


def main():
    # File name: the one you typed, or one made from the date and time,
    # so a new run never overwrites an old one.
    if len(sys.argv) > 1:
        name = sys.argv[1]
    else:
        name = time.strftime("run_%Y%m%d_%H%M%S.csv")
    if not name.endswith(".csv"):
        name = name + ".csv"
    RUNS_FOLDER.mkdir(parents=True, exist_ok=True)  # make the folder if it's not there yet
    filename = RUNS_FOLDER / name

    startWebsiteServer()
    esp = Esp()
    csv_file = open(filename, "w")
    csv_file.write(HEADER + "\n")
    print("Saving to", filename, "- press Ctrl+C to stop")

    try:
        while True:
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


if __name__ == "__main__":
    main()
