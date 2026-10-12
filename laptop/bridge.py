"""Bridge serial: thread tx (queue -> kabel) dan rx (kabel -> q_telemetry).

Port = objek dengan readline()/write() (pyserial atau FakeEsp32). Hanya modul ini yang
membuka serial. Format: satu baris JSON {"msg":..,"data":..}\\n.
"""
import json
import queue

from contracts.validate import ContractError, validate

from . import config

TX_MSGS = ("ball_position", "setpoint", "pid_gains")


def open_port(path, baud=config.BAUD):
    import serial  # lazy: tidak dibutuhkan saat --mock / tes

    return serial.Serial(path, baud, timeout=0.1)


def encode(msg, data):
    """Validasi data lalu bungkus envelope. Raise ContractError jika msg/data salah."""
    if msg not in TX_MSGS:
        raise ContractError(f"msg '{msg}' tidak dikirim laptop, harus salah satu {TX_MSGS}")
    validate(msg, data)
    return (json.dumps({"msg": msg, "data": data}) + "\n").encode()


def decode_telemetry(line):
    """Kembalikan dict telemetry valid, atau None untuk baris apa pun yang harus diabaikan."""
    try:
        env = json.loads(line)
        if env["msg"] != "telemetry":
            return None
        return validate("telemetry", env["data"])
    except (ValueError, KeyError, TypeError):  # JSON rusak, bukan dict, ContractError (ValueError)
        return None


def tx_loop(port, q_position, q_commands, stop, stats=None, report=print):
    """Perintah didahulukan dari posisi. Data tak valid dibuang (dihitung), port putus -> stop."""
    stats = stats if stats is not None else {}
    while not stop.is_set():
        try:
            msg, data = q_commands.get_nowait()
        except queue.Empty:
            try:
                msg, data = "ball_position", q_position.get(timeout=0.02)
            except queue.Empty:
                continue
        try:
            line = encode(msg, data)
        except ContractError as e:
            stats["tx_invalid"] = stats.get("tx_invalid", 0) + 1
            report(f"[bridge] data tidak dikirim: {e}")
            continue
        try:
            port.write(line)
        except Exception as e:  # port putus
            report(f"[bridge] gagal menulis ke port: {e}. Berhenti.")
            stop.set()
            return


def rx_loop(port, q_telemetry, stop, stats=None, report=print):
    """Baca baris; yang rusak/tak dikenal/tak valid dihitung di stats['rx_ignored']."""
    stats = stats if stats is not None else {}
    while not stop.is_set():
        try:
            line = port.readline()
        except Exception as e:  # port putus
            report(f"[bridge] port terputus: {e}. Berhenti.")
            stop.set()
            return
        if not line:
            continue
        tel = decode_telemetry(line)
        if tel is None:
            stats["rx_ignored"] = stats.get("rx_ignored", 0) + 1
        else:
            q_telemetry.put(tel)
