import json
import queue
import threading
import time

import pytest

from contracts.validate import ContractError
from laptop import bridge

TEL = {"t_ms": 1, "x_mm": 1.0, "y_mm": 2.0, "sp_x_mm": 0, "sp_y_mm": 0,
       "u_x_deg": 0.5, "u_y_deg": -0.5, "valid": True}


class FakePort:
    def __init__(self, lines=(), fail_read=False):
        self.lines, self.written, self.fail_read = list(lines), [], fail_read

    def write(self, b):
        self.written.append(b)

    def readline(self):
        if self.fail_read:
            raise OSError("unplugged")
        if self.lines:
            return self.lines.pop(0)
        time.sleep(0.01)
        return b""


def run(fn, *args):
    t = threading.Thread(target=fn, args=args)
    t.start()
    return t


def test_encode_envelope_and_rejects():
    line = bridge.encode("setpoint", {"x_mm": 5, "y_mm": 0})
    assert line.endswith(b"\n") and json.loads(line) == {"msg": "setpoint", "data": {"x_mm": 5, "y_mm": 0}}
    with pytest.raises(ContractError):
        bridge.encode("setpoint", {"x_mm": 999, "y_mm": 0})
    with pytest.raises(ContractError):
        bridge.encode("telemetry", TEL)


def test_tx_sends_commands_and_positions_skips_invalid():
    port, stop, stats = FakePort(), threading.Event(), {}
    qp, qc = queue.Queue(), queue.Queue()
    qc.put(("setpoint", {"x_mm": 5, "y_mm": 0}))
    qc.put(("setpoint", {"x_mm": 999, "y_mm": 0}))
    qp.put({"t_ms": 1, "x_mm": 1.0, "y_mm": 2.0, "valid": True})
    t = run(bridge.tx_loop, port, qp, qc, stop, stats, lambda m: None)
    time.sleep(0.2)
    stop.set(); t.join()
    msgs = [json.loads(b)["msg"] for b in port.written]
    assert msgs == ["setpoint", "ball_position"]
    assert stats["tx_invalid"] == 1


def test_rx_telemetry_in_garbage_ignored():
    good = (json.dumps({"msg": "telemetry", "data": TEL}) + "\n").encode()
    lines = [b"boot ok\n", b"{bad json\n", b'{"msg":"foo","data":{}}\n', b"[1]\n",
             json.dumps({"msg": "telemetry", "data": {"t_ms": 1}}).encode(), good]
    port, stop, stats, q = FakePort(lines), threading.Event(), {}, queue.Queue()
    t = run(bridge.rx_loop, port, q, stop, stats, lambda m: None)
    time.sleep(0.2)
    stop.set(); t.join()
    assert q.get_nowait() == TEL and q.empty()
    assert stats["rx_ignored"] == 5


def test_rx_port_lost_stops_cleanly():
    msgs, stop = [], threading.Event()
    t = run(bridge.rx_loop, FakePort(fail_read=True), queue.Queue(), stop, {}, msgs.append)
    t.join(timeout=2)
    assert not t.is_alive() and stop.is_set() and "terputus" in msgs[0]
