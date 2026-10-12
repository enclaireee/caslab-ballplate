# Instructions untuk Claude Code: Ball and Plate (software laptop + firmware ESP32)

Baca `architecture.md` dulu. File ini berisi aturan kerja dan spesifikasi implementasi. Pengguna adalah mahasiswa Teknik Elektro (Control Lab Task 4). Hasil harus **sederhana, mudah dijelaskan ke aslab, dan bisa dibangun tanpa alat canggih**.

## Ruang lingkup

**Dikerjakan di sini:** contracts, vision, calibrate, bridge, logger, mocks, main, tes, skrip plot/metrik, **dan firmware ESP32**.

**Tidak dikerjakan di sini:** perakitan hardware, wiring, mekanik, skematik, BOM (milik teman). Jika butuh data hardware (ukuran pelat, pin servo, port serial), pakai konstanta TODO dan laporkan.

## Aturan umum

1. **Sederhana dulu.** Python: `opencv-python`, `pyserial`, `jsonschema`, `pytest`, `matplotlib`. ESP32: Arduino framework, `ESP32Servo`, `ArduinoJson`. Tanpa framework besar, tanpa async/await, tanpa hierarki kelas berlapis.
2. **Satu file satu tanggung jawab**, fungsi pendek, komentar bahasa Indonesia untuk bagian yang menjelaskan *kenapa*.
3. **Contract hanya diubah atas izin pengguna.** Jika berubah, perbarui schema, kode laptop, dan firmware dalam satu kali kerja, lalu catat di `architecture.md` bagian 12.
4. **PID hanya di firmware**, tidak ada logika kontrol di laptop.
5. **Hanya `bridge.py` yang membuka port serial.**
6. **Software laptop harus bisa dites tanpa hardware** lewat `mocks.py`. Jalankan `pytest` sebelum menyatakan selesai.
7. **Firmware tidak bisa dites otomatis.** Tulis sesederhana mungkin, kompilasi jika `arduino-cli` atau PlatformIO tersedia, jika tidak katakan jelas "belum dikompilasi". Jangan mengklaim firmware sudah berfungsi.
8. **Jangan membuat file di luar struktur `architecture.md` bagian 7.** Jangan membuat dashboard web sebelum diminta.
9. **Data yang butuh hardware** (ukuran pelat, port serial, HSV bola, sudut pelat di gambar, pin servo, konstanta kalibrasi servo) masuk konstanta dengan komentar `# TODO: isi setelah hardware jadi`. Jangan menebak lalu menyembunyikannya.
10. Bahasa ke pengguna: Indonesia santai. Jawaban akhir singkat: apa yang jadi, cara menjalankan, apa yang belum diuji di hardware asli.

## Spesifikasi laptop

### contracts/

- Schema sesuai `architecture.md` bagian 4, `additionalProperties: false`, tiap schema punya `description` yang menyebut satuan dan arah sumbu.
- `validate.py`: `validate(name, message)` mengembalikan pesan atau melempar `ContractError` dengan pesan jelas.
- Tes: contoh valid lulus; invalid (field hilang, tipe salah, di luar rentang, field asing) ditolak.

### laptop/config.py

`SERIAL_PORT`, `BAUD=115200`, `CAMERA_INDEX`, `FRAME_W=640`, `FRAME_H=480`, `PLATE_SIZE_MM`, `PLATE_CORNERS_PX`, `HSV_LOW`, `HSV_HIGH`, `POSITION_RATE_HZ`, `QUEUE_SIZE`.

### laptop/vision.py

- `detect_ball(frame, cfg) -> (cx_px, cy_px) | None`: BGR ke HSV, `cv2.inRange`, `erode`/`dilate` kecil, kontur terbesar di atas luas minimum, centroid dari `cv2.moments`.
- `pixel_to_mm(cx, cy, cfg)`: pemetaan linear area pelat di gambar ke mm, origin di tengah, x ke kanan, y ke atas (sumbu y gambar dibalik).
- Loop kamera: set resolusi, `CAP_PROP_BUFFERSIZE=1`, matikan auto-exposure jika didukung, ambil frame terbaru, hasilkan `ball_position` (`valid=false` jika tak ketemu), `t_ms` dari `time.monotonic()`. Ukur fps dan latensi sebagai `vision_status`.
- Mode debug opsional: `cv2.imshow` dengan lingkaran di bola dan fps.
- Tes: gambar sintetis (lingkaran oranye di latar gelap) pada posisi diketahui, hasil mm dalam toleransi; tanpa bola mengembalikan `None`.

### laptop/calibrate.py

Alat bantu interaktif: (1) klik 4 sudut pelat, simpan ke JSON konfigurasi yang dibaca `config.py`; (2) trackbar `cv2.createTrackbar` untuk `HSV_LOW/HIGH` dengan pratinjau mask; (3) mode cek koordinat yang menampilkan `x_mm, y_mm` live (kanan-atas harus positif).

### laptop/bridge.py

- Thread tx: ambil `ball_position`/`setpoint`/`pid_gains` dari queue, bungkus envelope, tulis satu baris JSON.
- Thread rx: baca baris, parse, validasi `data`, taruh `telemetry` ke queue.
- Baris rusak, bukan JSON, atau `msg` tak dikenal: abaikan dan hitung, jangan crash. Port putus: laporkan jelas dan keluar rapi.
- Port serial dibungkus agar bisa diganti objek palsu (`readline()` dan `write()`).
- Tes dengan port palsu: envelope keluar benar, telemetry masuk benar, baris rusak diabaikan.

### laptop/logger.py

- Tampilkan tiap telemetry satu baris di terminal, tulis CSV dengan header dan `flush` tiap baris.
- `step_metrics(t, y, sp_final, y0)`: rise time 10-90%, overshoot persen, settling time (pita 2%), steady-state error. Fungsi murni, dites dengan respons orde-2 sintetis.
- `python -m laptop.logger --analyze file.csv --axis x`: hitung metrik dari CSV, deteksi otomatis lonjakan setpoint sebagai awal step, opsional `--plot` menyimpan PNG.

### laptop/mocks.py

- `FakeVision`: `ball_position` sintetis (diam, melingkar, sesekali hilang).
- `FakeEsp32`: objek serial palsu yang membaca baris masuk dan membalas telemetry dengan plant orde-2 dan P sederhana **di dalam mock saja**. Ini stand-in untuk tes rantai laptop, bukan firmware.

### laptop/main.py

Thread seperti `architecture.md` bagian 8. Argumen: `--mock`, `--port`, `--csv`, `--no-vision` (bridge + logger saja, untuk menguji firmware dengan data posisi dari terminal). Perintah ketikan: `sp <x> <y>`, `gains <axis> <kp> <ki> <kd>`, `quit`. Ctrl+C menghentikan semua thread dan menutup file dengan rapi.

## Spesifikasi firmware: firmware/controller/controller.ino

- Library: `ESP32Servo`, `ArduinoJson`. Pin servo dan semua konstanta kalibrasi di bagian atas file.
- `setup()`: serial 115200, attach servo, pelat ke posisi datar, mulai timer 100 Hz.
- Loop kontrol (timer) sesuai `architecture.md` bagian 6:
  - `dt` tetap 0.01.
  - D pada pengukuran: `d = -(pos - pos_prev)/dt`, difilter `d_f = a*d_f + (1-a)*d` dengan `a` sekitar 0.7-0.8.
  - I: `integral += e*dt`, di-clamp, reset saat mode aman.
  - `u = kp*e + ki*integral + kd*d_f`, di-clamp +-15 derajat.
  - Konversi ke sudut servo dengan `SERVO_X_CENTER`, `SERVO_Y_CENTER`, `SERVO_X_DIR`, `SERVO_Y_DIR`, `SERVO_DEG_PER_TILT_DEG`, serta batas sudut servo aman.
- Parsing serial non-blocking di `loop()`: kumpulkan karakter sampai `\n`, `deserializeJson`, tangani `ball_position`, `setpoint`, `pid_gains`; baris tidak valid diabaikan.
- Gain awal konservatif (`kp` kecil, `ki=0`, `kd` sekitar sepertiga sampai setengah `kp`) agar tidak liar saat pertama dihidupkan.
- Telemetry satu baris JSON dengan envelope, tiap 2-5 tick.
- Failsafe: posisi lebih tua dari 150 ms atau `valid=false` mengembalikan pelat datar dan mereset integral.
- Komentar di atas file: langkah uji manual bertahap (lihat `workflow.md` fase 4).

## Kalibrasi hardware (dikerjakan manusia di rig)

1. **Pelat datar:** cari sudut servo yang membuat pelat datar (waterpass/aplikasi level HP), isi `SERVO_*_CENTER`.
2. **Arah servo:** gerakkan servo +5 derajat, lihat ke mana bola menggelinding, atur `SERVO_*_DIR` (+1/-1) agar tilt positif menggerakkan bola ke arah koordinat positif.
3. **Rasio linkage:** ukur kemiringan pelat nyata untuk perubahan sudut servo, isi `SERVO_DEG_PER_TILT_DEG`.
4. **Kamera:** tegak lurus di atas tengah pelat, cahaya merata, jalankan `calibrate.py` (4 sudut, HSV, cek koordinat), isi `PLATE_SIZE_MM`.

## Prosedur tuning PID

1. Mulai `ki=0`. Naikkan `kp` perlahan sampai bola merespons, naikkan `kd` sampai osilasi teredam.
2. Jika bola berhenti jauh dari tengah, tambah `ki` sangat kecil.
3. Jika bola lepas atau osilasi membesar: turunkan `kp`, naikkan `kd`, periksa backlash linkage dan latensi kamera.
4. Ubah gain lewat perintah `gains` di terminal tanpa flash ulang. Catat tiap set gain yang bagus dan CSV-nya.

## Definisi selesai

- contracts: semua tes lulus.
- vision: tes gambar sintetis lulus; di hardware, deteksi stabil dan fps/latensi terukur.
- bridge + logger + mocks: `python -m laptop.main --mock --csv demo.csv` menampilkan data live, `sp` dan `gains` bekerja, CSV terisi, `pytest` lulus.
- calibrate: berjalan dan menghasilkan konfigurasi yang dibaca vision.
- firmware: terkompilasi, telemetry muncul di logger, pelat datar saat tidak ada data, `sp` dan `gains` mengubah perilaku.
- sistem: bola menyeimbang di tengah, step response terekam di CSV dengan metrik terhitung.

## Pengumpulan

Di `docs/` dan repo: source code ESP32 dan laptop, CSV hasil uji, plot dan tabel metrik, video layar logger saat sistem bekerja. Skematik, BOM, foto hardware, dan video hardware dari teman; semuanya dikumpulkan dalam satu folder per kelompok.
