import itertools
import json
import queue
import threading

from contracts.validate import validate
from laptop.mocks import FakeEsp32, FakeVision


def test_fakevision_modes_valid_contract():
    for mode in ("still", "circle", "dropout"):
        for m in itertools.islice(FakeVision(mode, 60).positions(), 200):
            validate("ball_position", m)
    ms = list(itertools.islice(FakeVision("dropout", 60).positions(), 60))
    assert any(not m["valid"] for m in ms) and any(m["valid"] for m in ms)
    c = list(itertools.islice(FakeVision("circle", 60).positions(), 60))
    assert len({round(m["x_mm"]) for m in c}) > 5


def test_fakevision_thread_drops_old():
    q, stop = queue.Queue(maxsize=2), threading.Event()
    th = threading.Thread(target=FakeVision("still", 500).run, args=(q, stop))
    th.start()
    import time
    time.sleep(0.1)
    stop.set()
    th.join(2)
    assert q.qsize() <= 2 and not th.is_alive()


def send(esp, msg, data):
    esp.write((json.dumps({"msg": msg, "data": data}) + "\n").encode())


def test_fakeesp32_step_converges():
    esp = FakeEsp32()
    assert esp.readline() == b""  # tak ada data -> b'' setelah timeout
    esp.write(b"sampah bukan json\n")
    send(esp, "setpoint", {"x_mm": 50, "y_mm": 0})
    send(esp, "pid_gains", {"axis": "both", "kp": 0.4, "ki": 0, "kd": 0.3})
    tels = []
    for i in range(300):  # 5 s @ 60 Hz
        send(esp, "ball_position", {"t_ms": i * 17, "x_mm": 0, "y_mm": 0, "valid": True})
        tels.append(json.loads(esp.readline())["data"])
    for d in tels:
        validate("telemetry", d)
    assert tels[0]["sp_x_mm"] == 50
    assert abs(tels[-1]["x_mm"] - 50) < 1 and abs(tels[-1]["y_mm"]) < 1


def test_fakeesp32_split_write_and_invalid():
    esp = FakeEsp32()
    line = (json.dumps({"msg": "ball_position", "data": {"t_ms": 5, "x_mm": 0, "y_mm": 0, "valid": False}}) + "\n").encode()
    esp.write(line[:10])
    assert esp.readline() == b""
    esp.write(line[10:])
    d = json.loads(esp.readline())["data"]
    assert d["valid"] is False and d["u_x_deg"] == 0
