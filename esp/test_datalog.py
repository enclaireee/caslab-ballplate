# test_datalog.py - check that readReply skips extra messages from the ESP32.
# Run: .venv/bin/python esp/test_datalog.py   (prints "ok")

from datalog import readReply


class FakeEsp:
    def __init__(self, lines):
        self.lines = lines

    def readLine(self):
        return self.lines.pop(0) if self.lines else ""


esp = FakeEsp(["# timeout: plate flat", "100,1.0,2.0,0,0,0.10,0.20", "# no ball"])
assert readReply(esp) == "100,1.0,2.0,0,0,0.10,0.20"
assert readReply(esp) == "# no ball"
assert readReply(esp) == ""
print("ok")
