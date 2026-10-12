# Architecture: Ball and Plate 2-DOF (Control Lab Task 4)

Dokumen ini adalah sumber kebenaran arsitektur. Cakupan: **software laptop + firmware ESP32** (dikerjakan pengguna). Perakitan hardware dikerjakan teman satu tim. Jika kode dan dokumen ini berbeda, perbaiki salah satunya dan catat di bagian "Keputusan".

## 1. Tujuan sistem

Menjaga bola pingpong oranye di titik setpoint (default tengah pelat) secara otomatis.

- Sensor: kamera overhead, posisi bola (x, y) dalam mm
- Aktuator: 2 servo MG996R memiringkan pelat (sumbu X dan Y)
- Kontrol: PID closed loop per sumbu, **berjalan di ESP32**
- Logging: telemetry dari ESP32 ke terminal laptop + CSV (dashboard web menyusul belakangan)

| Syarat tugas | Dipenuhi oleh |
|---|---|
| ESP32 + sensor + aktuator + data logging | ESP32, kamera, servo, logger |
| Closed loop, bukan on/off | PID per sumbu |
| Variabel kontinu | posisi bola (mm) |
| Bukti step response lewat data logging | ubah setpoint, log CSV, hitung metrik |

Pembagian tugas:

| Pihak | Mengerjakan |
|---|---|
| Pengguna (software) | laptop (vision, bridge, logger), firmware ESP32 (PID, servo, serial), tes, bukti step response |
| Teman (hardware) | mekanik pelat, wiring, daya servo, skematik, BOM, foto; memberi data: ukuran pelat, pin servo, posisi kamera |

## 2. Gambaran besar

```
Kamera
  | frame mentah (private)
  v
[ vision ]   laptop: OpenCV, px -> mm
  | ball_position
  v
[ bridge ]   laptop: satu-satunya pemilik port serial
  |   ^
  |   | telemetry
  v   |
[ controller ]  ESP32: PID x/y -> servo -> pelat -> bola

bridge --telemetry--> [ logger ]  terminal + CSV
                  \-> (nanti) [ dashboard ]
```

Prinsip yang tidak boleh dilanggar:

1. **Semua algoritma kontrol di ESP32.** Laptop hanya vision, bridge, tampilan.
2. **Hanya `bridge` yang membuka port serial.**
3. **Antar-node hanya bertukar pesan sesuai contract.** Isi dalam node private.
4. **Setiap bagian software bisa dites tanpa hardware** (mock).

## 3. Node dan port

| Node | Berjalan di | Input | Output |
|---|---|---|---|
| vision | laptop + kamera | frame kamera | `ball_position`, `vision_status` |
| bridge | laptop | `ball_position`, perintah `setpoint`/`pid_gains`, baris serial dari ESP32 | baris serial ke ESP32, `telemetry` |
| controller | ESP32 | `ball_position`, `setpoint`, `pid_gains` | sudut servo (internal), `telemetry` |
| logger | laptop | `telemetry` | terminal, CSV |

## 4. Contract (JSON Schema)

Ada di `contracts/`.

| Contract | Field | Satuan / aturan |
|---|---|---|
| `ball_position` | `t_ms`, `x_mm`, `y_mm`, `valid` | origin (0,0) tengah pelat, x ke kanan, y ke atas (pandangan kamera), mm. `valid=false` jika bola tak terdeteksi |
| `setpoint` | `x_mm`, `y_mm` | sama dengan `ball_position` |
| `pid_gains` | `axis` (`x`/`y`/`both`), `kp`, `ki`, `kd` | output derajat tilt pelat: `kp` deg/mm, `ki` deg/(mm.s), `kd` deg.s/mm |
| `telemetry` | `t_ms`, `x_mm`, `y_mm`, `sp_x_mm`, `sp_y_mm`, `u_x_deg`, `u_y_deg`, `valid` | `u_*` = output PID (tilt, derajat) setelah saturasi |
| `vision_status` | `fps`, `latency_ms`, `ball_found` | memantau kecukupan kamera |

Nilai placeholder (ganti setelah hardware jadi): batas posisi/setpoint +-200 mm (ukuran pelat dari teman), batas tilt +-15 derajat. Karena pengguna memegang kedua sisi, contract boleh diubah, tapi **ubah schema dan firmware dalam satu kali kerja** dan catat di "Keputusan".

## 5. Format di kabel

Serial USB, 115200 baud, satu baris JSON per pesan diakhiri `\n`, dengan envelope:

```
{"msg":"ball_position","data":{"t_ms":1200,"x_mm":12.5,"y_mm":-3.0,"valid":true}}
{"msg":"setpoint","data":{"x_mm":0,"y_mm":0}}
{"msg":"pid_gains","data":{"axis":"both","kp":0.4,"ki":0.0,"kd":0.3}}
{"msg":"telemetry","data":{"t_ms":1210,"x_mm":12.5,"y_mm":-3.0,"sp_x_mm":0,"sp_y_mm":0,"u_x_deg":-1.2,"u_y_deg":0.4,"valid":true}}
```

- Laptop ke ESP32: `ball_position` (30-60 Hz), `setpoint` dan `pid_gains` saat berubah.
- ESP32 ke laptop: `telemetry` (10-50 Hz).
- Baris di luar format (log debug, boot message) **diabaikan dengan aman** oleh penerima di kedua sisi.
- Jika parsing JSON di ESP32 terbukti terlalu lambat, ganti ke CSV di adapter kedua sisi tanpa mengubah isi contract.

## 6. Firmware ESP32 (controller)

Loop kontrol dijalankan timer berperiode tetap (target 100 Hz, `dt = 0.01 s`), bukan `delay()`.

Setiap tick:

1. Salin posisi, setpoint, dan gain terakhir ke variabel lokal.
2. Jika data posisi lebih tua dari **150 ms** atau `valid=false`: mode aman, tilt = 0, reset integral.
3. Error per sumbu `e = setpoint - posisi`.
4. PID: P pada error, D pada **pengukuran** dengan low-pass sederhana, I dengan anti-windup (clamp). Output dibatasi +-15 derajat.
5. Konversi tilt ke sudut servo: `sudut = center + arah * rasio * tilt`, dengan konstanta hasil kalibrasi, dibatasi ke rentang sudut servo yang aman.
6. Tulis ke servo. Cetak telemetry tiap 2-5 tick.

Parsing serial dilakukan non-blocking di `loop()`; loop kontrol di timer. Variabel bersama ditandai `volatile` dan disalin di awal tick (cukup untuk tugas ini).

## 7. Struktur repo

```
ball-plate/
├─ contracts/        # JSON Schema + validate.py
├─ laptop/
│  ├─ vision.py      # OpenCV: frame -> ball_position
│  ├─ calibrate.py   # klik 4 sudut pelat, setel HSV bola, cek koordinat
│  ├─ bridge.py      # serial <-> queue
│  ├─ logger.py      # terminal + CSV + metrik step response
│  ├─ main.py        # menjalankan node + perintah ketikan
│  ├─ mocks.py       # FakeVision, FakeEsp32
│  └─ config.py      # port, resolusi, HSV, ukuran pelat
├─ firmware/
│  └─ controller/
│     └─ controller.ino
├─ tests/
├─ docs/             # untuk pengumpulan
├─ architecture.md
├─ instructions.md
└─ workflow.md
```

## 8. Threading di laptop

`main.py` menjalankan thread:

- **vision**: frame, posisi, `q_position`
- **bridge-tx**: `q_position` dan `q_commands`, tulis serial
- **bridge-rx**: baca serial, parse, validasi, `q_telemetry`
- **logger**: `q_telemetry`, tampilkan dan tulis CSV
- **command**: baca ketikan terminal (`sp 50 0`, `gains both 0.4 0 0.3`, `quit`), `q_commands`

Pakai `queue.Queue`. `q_position` kecil (`maxsize=2`) dan **buang data lama jika penuh**.

## 9. Perangkat keras (disediakan teman)

| Komponen | Catatan |
|---|---|
| ESP32 | disuplai USB laptop |
| 2x servo MG996R | **adaptor 5-6 V minimal 3 A sendiri**, common ground dengan ESP32, kapasitor 470-1000 uF di jalur daya servo |
| Linkage, horn, baut M3, joint coupling, pivot tengah | mekanik pelat |
| Pelat matte gelap + rim kecil, bola pingpong oranye | kontras untuk kamera |
| Kamera tegak lurus di atas tengah pelat | webcam atau RealSense D435 (stream warna saja) |

Data yang dibutuhkan dari teman: ukuran pelat (mm), pin servo ESP32, serta tinggi dan posisi kamera.

## 10. Pengujian dan bukti step response

Sistem stabil di (0,0), ketik `sp 50 0`, log CSV terekam, hitung rise time, overshoot, settling time, steady-state error dengan `logger --analyze`. Ulangi minimal 3 kali per sumbu. Simpan CSV, plot, dan tabel metrik di `docs/`.

## 11. Rencana cadangan

Jika kamera kurang cepat atau akurat, ganti sensor ke resistive touch panel yang dibaca ESP32 langsung. Bridge, logger, dan metrik tidak berubah.

## 12. Keputusan

- Contract JSON Schema (stack campur Python / C++).
- Logging awal terminal + CSV; dashboard web ditunda.
- Semua kontrol di ESP32; laptop hanya vision, bridge, tampilan.
- Satu proses pemilik serial (bridge), antar-thread lewat `queue`.
- Envelope serial `{"msg":..., "data":...}`; satuan gain deg/mm; batas tilt +-15 derajat (placeholder).
