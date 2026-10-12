"""Logger: tampilkan telemetry di terminal, tulis CSV, dan analisis step response.

Tidak ada logika kontrol di sini; hanya mencatat dan menghitung metrik.
Pakai: python -m laptop.logger --analyze file.csv --axis x [--plot]
"""
import argparse
import csv
import queue
import sys
from pathlib import Path

FIELDS = ["t_ms", "x_mm", "y_mm", "sp_x_mm", "sp_y_mm", "u_x_deg", "u_y_deg", "valid"]


def run(q_telemetry, stop, csv_path=None, out=print):
    """Konsumsi q_telemetry sampai `stop` (threading.Event) aktif dan queue kosong."""
    f = open(csv_path, "w", newline="") if csv_path else None
    try:
        w = csv.DictWriter(f, fieldnames=FIELDS) if f else None
        if w:
            w.writeheader()
            f.flush()
        while True:
            try:
                d = q_telemetry.get(timeout=0.1)
            except queue.Empty:
                if stop.is_set():
                    break
                continue
            out(
                f"t={d['t_ms']:>8} ms  pos=({d['x_mm']:7.1f},{d['y_mm']:7.1f})  "
                f"sp=({d['sp_x_mm']:6.1f},{d['sp_y_mm']:6.1f})  "
                f"u=({d['u_x_deg']:6.2f},{d['u_y_deg']:6.2f}) deg  "
                f"{'ok' if d['valid'] else 'LOST'}"
            )
            if w:
                w.writerow({k: d[k] for k in FIELDS})
                f.flush()  # flush tiap baris: data aman walau program mati mendadak
    finally:
        if f:
            f.close()


def step_metrics(t, y, sp_final, y0):
    """Metrik step response. t dalam detik (t[0] = awal step), y dalam mm.

    Mengembalikan dict: rise_time_s (10-90%), overshoot_pct, settling_time_s (pita 2%),
    steady_state_error (sp_final - rata-rata 10% sampel terakhir). None jika tak tercapai.
    """
    A = sp_final - y0
    if len(t) < 2 or A == 0:
        raise ValueError("butuh >=2 sampel dan step tidak nol")
    yn = [(v - y0) / A for v in y]  # ternormalisasi: 0 -> 1
    t0 = t[0]

    def first_cross(level):
        for ti, v in zip(t, yn):
            if v >= level:
                return ti
        return None

    t10, t90 = first_cross(0.1), first_cross(0.9)
    rise = t90 - t10 if t10 is not None and t90 is not None else None
    overshoot = max(0.0, max(yn) - 1.0) * 100
    # settling: sampel terakhir yang di luar pita 2%; waktu settle = sampel sesudahnya
    last_out = max((i for i, v in enumerate(yn) if abs(v - 1) > 0.02), default=-1)
    if last_out == len(t) - 1:
        settling = None  # belum settle sampai data habis
    else:
        settling = t[last_out + 1] - t0 if last_out >= 0 else 0.0
    n = max(1, len(y) // 10)
    sse = sp_final - sum(y[-n:]) / n
    return {"rise_time_s": rise, "overshoot_pct": overshoot,
            "settling_time_s": settling, "steady_state_error": sse}


def find_steps(sp, min_jump=1.0):
    """Indeks lonjakan setpoint (|selisih sampel berurutan| > min_jump mm)."""
    return [i for i in range(1, len(sp)) if abs(sp[i] - sp[i - 1]) > min_jump]


def analyze(csv_path, axis="x"):
    """Baca CSV, kembalikan list (t, y, sp, metrik) per step yang terdeteksi."""
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    t = [float(r["t_ms"]) / 1000 for r in rows]
    y = [float(r[f"{axis}_mm"]) for r in rows]
    sp = [float(r[f"sp_{axis}_mm"]) for r in rows]
    jumps = find_steps(sp)
    results = []
    for k, i in enumerate(jumps):
        end = jumps[k + 1] if k + 1 < len(jumps) else len(t)
        ts, ys = t[i:end], y[i:end]
        if len(ts) < 2:
            continue
        m = step_metrics(ts, ys, sp[i], y[i - 1])  # y0 = posisi tepat sebelum lonjakan
        results.append((ts, ys, sp[i], m))
    return results


def plot(results, axis, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    for k, (ts, ys, spf, _m) in enumerate(results):
        ax.plot([v - ts[0] for v in ts], ys, label=f"step {k + 1}")
        ax.axhline(spf, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("waktu sejak step (s)")
    ax.set_ylabel(f"{axis} (mm)")
    ax.legend()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)


def main(argv=None):
    p = argparse.ArgumentParser(description="Analisis step response dari CSV logger")
    p.add_argument("--analyze", required=True, metavar="FILE.csv")
    p.add_argument("--axis", choices=["x", "y"], default="x")
    p.add_argument("--plot", action="store_true", help="simpan PNG di samping CSV")
    a = p.parse_args(argv)
    results = analyze(a.analyze, a.axis)
    if not results:
        print("tidak ada lonjakan setpoint terdeteksi", file=sys.stderr)
        return 1
    for k, (_ts, _ys, spf, m) in enumerate(results, 1):
        fmt = lambda v, u: "n/a" if v is None else f"{v:.3f} {u}"
        print(f"step {k} (sp={spf:g} mm): rise={fmt(m['rise_time_s'], 's')}  "
              f"overshoot={m['overshoot_pct']:.1f} %  settling={fmt(m['settling_time_s'], 's')}  "
              f"sse={m['steady_state_error']:.2f} mm")
    if a.plot:
        png = Path(a.analyze).with_suffix(f".{a.axis}.png")
        plot(results, a.axis, png)
        print(f"plot: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
