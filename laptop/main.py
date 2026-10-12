"""Program utama laptop. Contoh: python -m laptop.main --mock --csv demo.csv

Perintah: sp <x> <y> | gains <x|y|both> <kp> <ki> <kd> | quit
"""
import argparse
import queue
import sys
import threading

from contracts.validate import ContractError, validate

from . import bridge, config, logger


def parse_command(line):
    """Baris ketikan -> ("quit", None) | (msg, data) | None (baris kosong).
    Raise ValueError berpesan ramah jika salah."""
    parts = line.split()
    if not parts:
        return None
    cmd, args = parts[0].lower(), parts[1:]
    try:
        if cmd == "quit":
            return ("quit", None)
        if cmd == "sp" and len(args) == 2:
            msg, data = "setpoint", {"x_mm": float(args[0]), "y_mm": float(args[1])}
        elif cmd == "gains" and len(args) == 4:
            msg, data = "pid_gains", {"axis": args[0], "kp": float(args[1]),
                                      "ki": float(args[2]), "kd": float(args[3])}
        else:
            raise ValueError("perintah: sp <x> <y> | gains <x|y|both> <kp> <ki> <kd> | quit")
        validate(msg, data)
    except ContractError as e:
        raise ValueError(f"nilai ditolak: {e}")
    except ValueError as e:
        raise ValueError(str(e) if str(e).startswith("perintah") else f"angka tidak valid: {e}")
    return (msg, data)


def command_loop(lines, q_commands, stop, report=print):
    for line in lines:
        if stop.is_set():
            return
        try:
            cmd = parse_command(line)
        except ValueError as e:
            report(f"[cmd] {e}")
            continue
        if cmd is None:
            continue
        if cmd[0] == "quit":
            break
        q_commands.put(cmd)
    stop.set()  # quit atau stdin habis


def main(argv=None, stdin=None):
    p = argparse.ArgumentParser(description="Ball and plate: sisi laptop")
    p.add_argument("--mock", action="store_true", help="FakeVision + FakeEsp32, tanpa hardware")
    p.add_argument("--port", default=config.SERIAL_PORT)
    p.add_argument("--csv", help="tulis telemetry ke file CSV")
    p.add_argument("--no-vision", action="store_true", help="bridge + logger saja")
    a = p.parse_args(argv)

    if not a.mock and not a.no_vision:
        print("Vision asli belum tersedia (Fase 3). Pakai --mock atau --no-vision.", file=sys.stderr)
        return 2

    if a.mock:
        from .mocks import FakeEsp32, FakeVision
        port = FakeEsp32()
    else:
        try:
            port = bridge.open_port(a.port)
        except Exception as e:
            print(f"Tidak bisa membuka port {a.port}: {e}", file=sys.stderr)
            return 1

    stop = threading.Event()
    q_pos = queue.Queue(maxsize=config.QUEUE_SIZE)
    q_cmd, q_tel = queue.Queue(), queue.Queue()
    stats = {}
    targets = [
        (bridge.tx_loop, (port, q_pos, q_cmd, stop, stats), "bridge-tx"),
        (bridge.rx_loop, (port, q_tel, stop, stats), "bridge-rx"),
        (logger.run, (q_tel, stop, a.csv), "logger"),
    ]
    if a.mock and not a.no_vision:
        targets.append((FakeVision("circle").run, (q_pos, stop), "vision"))
    threads = [threading.Thread(target=f, args=args, name=n) for f, args, n in targets]
    # command: daemon, karena bisa terblokir di stdin saat Ctrl+C
    threads.append(threading.Thread(target=command_loop, name="command", daemon=True,
                                    args=(stdin if stdin is not None else sys.stdin, q_cmd, stop)))
    for t in threads:
        t.start()
    try:
        while not stop.wait(0.2):
            pass
    except KeyboardInterrupt:
        print("\nCtrl+C, menutup...")
    stop.set()
    for t in threads:
        if not t.daemon:
            t.join(timeout=3)
    if hasattr(port, "close"):
        port.close()
    if stats.get("rx_ignored") or stats.get("tx_invalid"):
        print(f"[bridge] baris rx diabaikan: {stats.get('rx_ignored', 0)}, "
              f"tx tak valid: {stats.get('tx_invalid', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
