# mock.py - a FAKE ESP32, so we can build the data logging without any hardware.
#
# It pretends to balance a ball and gives the same text lines the real ESP32 will send:
#   t_ms,x_mm,y_mm,sp_x_mm,sp_y_mm,u_x_deg,u_y_deg
# Every 5 seconds it moves the setpoint, so there are step responses to look at.

import random
import time

DT = 0.02  # seconds between lines (50 lines per second, like the real ESP32)

# Fake PID gains, picked so the ball overshoots a little and settles in ~3 s
KP = 0.074  # degrees of tilt per mm of error
KD = 0.025  # degrees of tilt per (mm/s) of ball speed

# The setpoint changes every 5 seconds, going through this list again and again
SETPOINTS = [(0, 0), (50, 0), (0, 0), (0, 50)]


def moveBall(pos, speed, setpoint):
    """Simulate one axis for one DT. Returns the new position, speed and plate tilt."""
    tilt = KP * (setpoint - pos) - KD * speed  # simple PD controller
    tilt = max(-15, min(15, tilt))             # plate can only tilt +-15 degrees
    accel = 122 * tilt                         # tilted plate pushes the ball (mm/s^2 per degree)
    speed = speed + accel * DT
    pos = pos + speed * DT
    return pos, speed, tilt


class Esp:
    """Fake ESP32. The real one (later) must have the same readLine() function."""

    def __init__(self):
        self.t = 0.0                   # time since start (s)
        self.x, self.y = 0.0, 0.0      # ball position (mm)
        self.vx, self.vy = 0.0, 0.0    # ball speed (mm/s)
        self.started = False

    def readLine(self):
        """Wait for the next line and return it as text (without the newline)."""
        # The real ESP32 prints a message line when it boots, so the fake one does too
        if not self.started:
            self.started = True
            return "# fake ESP32 started"

        time.sleep(DT)  # the real ESP32 also needs 20 ms per line
        self.t = self.t + DT

        # Which setpoint are we at? Changes every 5 seconds.
        sp_x, sp_y = SETPOINTS[int(self.t // 5) % len(SETPOINTS)]

        self.x, self.vx, u_x = moveBall(self.x, self.vx, sp_x)
        self.y, self.vy, u_y = moveBall(self.y, self.vy, sp_y)

        # A real camera is never perfectly still, so add +-0.5 mm of noise
        x_seen = self.x + random.uniform(-0.5, 0.5)
        y_seen = self.y + random.uniform(-0.5, 0.5)

        t_ms = int(self.t * 1000)
        return f"{t_ms},{x_seen:.1f},{y_seen:.1f},{sp_x},{sp_y},{u_x:.2f},{u_y:.2f}"
