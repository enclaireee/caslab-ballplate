# mock.py - a FAKE ESP32, so the laptop side (datalog.py + the dashboard) can
# be tested without any hardware.
#
# It runs the same PID as esp/pid.ino on a simulated ball and prints the same
# CSV lines as the firmware, so datalog.py cannot tell the difference.
# Every 5 seconds it moves the setpoint, so there are step responses to look at.
# A "sp" command from the laptop switches that automatic cycle off.

import random
import time

DT = 0.02  # seconds between lines (50 lines per second)

# PID start values, the same as esp/esp.ino
KP = 0.074  # degrees of tilt per mm of error
KI = 0.0    # degrees per (mm * second)
KD = 0.025  # degrees per (mm/s) of ball speed

TILT_LIMIT = 15.0  # the plate can only tilt +-15 degrees

# The setpoint changes every 5 seconds, going through this list again and again
SETPOINTS = [(0, 0), (50, 0), (0, 0), (0, 50)]


def moveBall(pos, speed, integral, setpoint):
    """One control step for one axis. Returns the new position, speed, integral and tilt."""
    error = setpoint - pos

    next_integral = integral + error * DT
    tilt = KP * error + KI * next_integral - KD * speed

    # Anti-windup: at the tilt limit the integral stops growing.
    if abs(tilt) > TILT_LIMIT:
        next_integral = integral
    tilt = max(-TILT_LIMIT, min(TILT_LIMIT, tilt))

    # A tilted plate pushes the ball: 122 mm/s^2 of acceleration per degree.
    speed = speed + 122 * tilt * DT
    pos = pos + speed * DT
    return pos, speed, next_integral, tilt


class Esp:
    """Fake ESP32. The real one (esp_usb.py) has the same two functions."""

    def __init__(self):
        self.t = 0.0                # time since start (s)
        self.x, self.y = 0.0, 0.0   # ball position (mm)
        self.vx, self.vy = 0.0, 0.0  # ball speed (mm/s)
        self.ix, self.iy = 0.0, 0.0  # PID integrals
        self.sp = None              # setpoint from the laptop, None = auto cycle
        self.started = False

    def sendLine(self, text):
        """A command from the laptop, in the same words the firmware understands."""
        global KP, KI, KD
        parts = text.split()
        if len(parts) == 3 and parts[0] == "sp":
            self.sp = (float(parts[1]), float(parts[2]))
        elif len(parts) == 4 and parts[0] == "pid":
            KP, KI, KD = float(parts[1]), float(parts[2]), float(parts[3])
        # "pos ..." is ignored: the fake ball moves by itself, there is no camera.

    def readLine(self):
        """Wait for the next line and return it as text (without the newline)."""
        # The real ESP32 prints a message line when it boots, so the fake one does too
        if not self.started:
            self.started = True
            return "# fake ESP32 started"

        time.sleep(DT)  # the real ESP32 also needs 20 ms per line
        self.t = self.t + DT

        # The setpoint: from the laptop, or the automatic 5-second cycle.
        if self.sp is not None:
            sp_x, sp_y = self.sp
        else:
            sp_x, sp_y = SETPOINTS[int(self.t // 5) % len(SETPOINTS)]

        self.x, self.vx, self.ix, u_x = moveBall(self.x, self.vx, self.ix, sp_x)
        self.y, self.vy, self.iy, u_y = moveBall(self.y, self.vy, self.iy, sp_y)

        # A real camera is never perfectly still, so add +-0.5 mm of noise
        x_seen = self.x + random.uniform(-0.5, 0.5)
        y_seen = self.y + random.uniform(-0.5, 0.5)

        t_ms = int(self.t * 1000)
        return f"{t_ms},{x_seen:.1f},{y_seen:.1f},{sp_x},{sp_y},{u_x:.2f},{u_y:.2f}"
