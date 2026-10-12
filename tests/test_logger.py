import math
import queue
import threading

from laptop import logger
from laptop.logger import step_metrics

ZETA, WN, A = 0.5, 10.0, 50.0


def second_order(n=600, dt=0.005, y0=0.0):
    wd = WN * math.sqrt(1 - ZETA**2)
    t = [i * dt for i in range(n)]
    y = [y0 + A * (1 - math.exp(-ZETA * WN * s) * (math.cos(wd * s) + ZETA * WN / wd * math.sin(wd * s)))
         for s in t]
    return t, y


def test_step_metrics_second_order():
    t, y = second_order()
    m = step_metrics(t, y, A, 0.0)
    assert abs(m["overshoot_pct"] - 100 * math.exp(-math.pi * ZETA / math.sqrt(1 - ZETA**2))) < 0.5
    assert 0.12 < m["rise_time_s"] < 0.19  # ~ (2.16*zeta+0.6)/wn
    assert 0.5 < m["settling_time_s"] < 1.1  # ~ 4/(zeta*wn) = 0.8
    assert abs(m["steady_state_error"]) < 0.1


def test_step_metrics_never_settles():
    m = step_metrics([0, 1, 2], [0, 10, 20], 100, 0)
    assert m["rise_time_s"] is None and m["settling_time_s"] is None


def test_run_csv_and_analyze(tmp_path):
    t, y = second_order(n=400)
    q, stop, lines = queue.Queue(), threading.Event(), []
    # 0.2 s diam di 0, lalu setpoint melompat ke A
    rows = [(0.0, 0.0, 0.0)] * 40 + [(s + 0.2, v, A) for s, v in zip(t, y)]
    for ts, v, sp in rows:
        q.put({"t_ms": round(ts * 1000), "x_mm": v, "y_mm": 0.0, "sp_x_mm": sp, "sp_y_mm": 0.0,
               "u_x_deg": 0.0, "u_y_deg": 0.0, "valid": True})
    path = tmp_path / "log.csv"
    th = threading.Thread(target=logger.run, args=(q, stop, path, lines.append))
    th.start()
    stop.set()
    th.join(5)
    assert len(lines) == len(rows) and "pos=" in lines[0]
    text = path.read_text().splitlines()
    assert text[0] == ",".join(logger.FIELDS) and len(text) == len(rows) + 1

    results = logger.analyze(path, "x")
    assert len(results) == 1
    assert 10 < results[0][3]["overshoot_pct"] < 20
    assert logger.main(["--analyze", str(path), "--axis", "x", "--plot"]) == 0
    assert (tmp_path / "log.x.png").exists()
