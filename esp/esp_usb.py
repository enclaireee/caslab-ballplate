# esp_usb.py - the real ESP32 over USB.
#
# Same two functions as mock.py, so datalog.py can use either one:
#   sendLine("pos 12.5 -3.0")   send one command line to the ESP32
#   readLine()                  wait for the next line the ESP32 prints
#
# The port is found automatically. Pass a name if that picks the wrong one:
#   Esp(port="/dev/cu.usbserial-0001")     (Arduino IDE -> Tools -> Port)

import time

import serial
from serial.tools import list_ports

BAUD = 115200


def findPort():
    """Name of the first USB serial port, e.g. /dev/cu.usbserial-0001."""
    for info in list_ports.comports():
        if "usb" in info.device.lower():
            return info.device
    return None


class Esp:
    def __init__(self, port=None):
        port = port or findPort()
        if port is None:
            raise RuntimeError(
                "No ESP32 found. Plug it in, or pass the port: "
                "Esp(port='/dev/cu.usbserial-0001')"
            )
        self.port = serial.Serial(port, BAUD, timeout=2)
        print("ESP32 on", port)
        # Opening the port restarts the ESP32, so give it time to boot.
        time.sleep(1.5)
        self.port.reset_input_buffer()

    def sendLine(self, text):
        """Send one command line to the ESP32."""
        self.port.write((text + "\n").encode())

    def readLine(self):
        """Wait for the next line and return it as text (without the newline)."""
        return self.port.readline().decode(errors="replace").strip()
