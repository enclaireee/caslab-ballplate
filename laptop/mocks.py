"""Mock untuk tes tanpa hardware: FakeVision (posisi sintetis) dan FakeEsp32 (port serial palsu)."""
import json
import math
import queue
import threading
import time

from . import config

MODES = ("still", "circle", "dropout")


class FakeVision:
    """Hasilkan dict ball_position valid sesuai contract.

    still: diam di (0,0). circle: lingkaran radius 40 mm, periode 4 s.
    dropout: diam, tapi 5 dari tiap 30 frame valid=false.
    """

    def __init__(self, mode="still", rate_hz=None):
        assert mode in MODES, mode
        self.mode, self.rate = mode, rate_hz or config.POSITION_RATE_HZ

    def positions(self):
        """Generator tak berhingga; t_ms dari nomor frame (deterministik, tanpa sleep)."""
        i = 0
        while True:
            t = i / self.rate
            x = y = 0.0
            if self.mode == "circle":
                x, y = 40 * math.cos(2 * math.pi * t / 4), 40 * math.sin(2 * math.pi * t / 4)
            valid = not (self.mode == "dropout" and i % 30 >= 25)
            yield {"t_ms": int(t * 1000), "x_mm": x, "y_mm": y, "valid": valid}
            i += 1

    def run(self, q_position, stop):
        """Isi queue sesuai laju; jika penuh, buang data terlama (seperti thread vision asli)."""
        for msg in self.positions():
            if stop.is_set():
                return
            while True:
                try:
                    q_position.put_nowait(msg)
                    break
                except queue.Full:
                    try:
                        q_position.get_nowait()
                    except queue.Empty:
                        pass
            time.sleep(1 / self.rate)


class FakeEsp32:
    """Serial palsu (readline/write). Tiap ball_position masuk dibalas satu telemetry.

    Plant orde-2 (bola 1 sumbu, x'' = G*u - C*x') + kontrol P SEDERHANA ada di sini
    hanya sebagai stand-in untuk tes rantai laptop. Ini BUKAN firmware (PID asli di ESP32).
    """

    G, C, UMAX = 62.0, 6.0, 15.0  # mm/s^2 per derajat, redaman 1/s, batas tilt derajat

    def __init__(self):
        self._lock = threading.Lock()
        self._out = queue.Queue()
        self._buf = b""
        self._sp = [0.0, 0.0]
        self._kp = [0.4, 0.4]
        self._pos = [0.0, 0.0]
        self._vel = [0.0, 0.0]
        self._t_prev = None
        self.timeout = 0.05

    def write(self, data):
        with self._lock:
            self._buf += data
            *lines, self._buf = self._buf.split(b"\n")
            for line in lines:
                self._handle(line)
        return len(data)

    def readline(self):
        try:
            return self._out.get(timeout=self.timeout)
        except queue.Empty:
            return b""

    def close(self):
        pass

    def _handle(self, line):
        try:
            env = json.loads(line)
            msg, d = env["msg"], env["data"]
            if msg == "setpoint":
                self._sp = [d["x_mm"], d["y_mm"]]
            elif msg == "pid_gains":  # hanya kp yang dipakai mock
                for i, ax in enumerate("xy"):
                    if d["axis"] in (ax, "both"):
                        self._kp[i] = d["kp"]
            elif msg == "ball_position":
                self._step(d)
        except (ValueError, KeyError, TypeError):
            pass  # baris rusak diabaikan, seperti firmware

    def _step(self, d):
        t = d["t_ms"]
        dt = 0.0 if self._t_prev is None else min(max((t - self._t_prev) / 1000, 0.0), 0.05)
        self._t_prev = t
        u = [0.0, 0.0]
        if d["valid"]:  # bola hilang: pelat datar (u=0)
            for i in range(2):
                e = self._sp[i] - self._pos[i]
                u[i] = max(-self.UMAX, min(self.UMAX, self._kp[i] * e))
        for i in range(2):
            self._vel[i] += (self.G * u[i] - self.C * self._vel[i]) * dt
            self._pos[i] += self._vel[i] * dt
        tel = {"t_ms": t, "x_mm": self._pos[0], "y_mm": self._pos[1],
               "sp_x_mm": self._sp[0], "sp_y_mm": self._sp[1],
               "u_x_deg": u[0], "u_y_deg": u[1], "valid": bool(d["valid"])}
        self._out.put((json.dumps({"msg": "telemetry", "data": tel}) + "\n").encode())
