# Workflow: membangun dengan sub-agent Sonnet yang hemat

Tujuan: mengerjakan proyek (software laptop + firmware ESP32) dengan biaya token rendah. Sesi utama hanya **mengatur dan memeriksa**; sub-agent Sonnet yang menulis kode dengan konteks kecil dan terfokus.

Baca `architecture.md` (apa yang dibangun) dan `instructions.md` (aturan dan spesifikasi). Perakitan hardware bukan bagian workflow ini.

## 1. Persiapan satu kali

1. Taruh `architecture.md`, `instructions.md`, `workflow.md` di akar repo.
2. Buat `CLAUDE.md` di akar repo:

   ```
   Proyek Ball and Plate: software laptop + firmware ESP32 (hardware dirakit teman).
   Baca architecture.md dan instructions.md sebelum bekerja.
   Ikuti workflow.md: delegasikan implementasi ke sub-agent builder (Sonnet).
   ```

3. Buat `.claude/agents/builder.md`:

```markdown
---
name: builder
description: Mengimplementasikan satu bagian proyek Ball and Plate (kode + tes) sesuai instructions.md. Dipakai untuk setiap fase.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---
Kamu mengimplementasikan SATU tugas kecil untuk proyek Ball and Plate.

Aturan:
- Baca hanya file yang disebut di tugas, plus bagian relevan dari instructions.md dan architecture.md. Jangan menjelajah seluruh repo.
- Ikuti instructions.md: sederhana, library yang disebut saja, jangan ubah contract tanpa diminta, PID hanya di firmware.
- Kode laptop: tulis tes, jalankan pytest, perbaiki sampai lulus.
- Firmware: tulis sesederhana mungkin; kompilasi jika arduino-cli/PlatformIO tersedia, jika tidak katakan "belum dikompilasi". Jangan mengklaim firmware sudah berfungsi.
- Jangan mengerjakan di luar lingkup tugas. Jika spesifikasi kurang jelas, pilih opsi paling sederhana dan catat di laporan.
- Laporan akhir MAKSIMAL 10 baris: file dibuat/diubah, hasil tes, asumsi, hal yang perlu dicek manusia.
```

4. (Opsional) `.claude/agents/reviewer.md`, sekali per fase besar:

```markdown
---
name: reviewer
description: Memeriksa hasil satu fase terhadap definisi selesai di instructions.md. Tidak mengubah file.
tools: Read, Glob, Grep, Bash
model: sonnet
---
Periksa hasil fase yang disebut terhadap "Definisi selesai" di instructions.md dan prinsip di architecture.md bagian 2.
Jalankan pytest. Cek: contract konsisten antara schema, bridge, dan firmware; tidak ada akses serial selain bridge.py; tidak ada logika kontrol di laptop; firmware punya failsafe, anti-windup, dan saturasi; tidak ada file di luar struktur.
Laporan maksimal 8 baris: lulus/tidak per poin, plus perbaikan konkret.
```

Opsional: pilih model Sonnet juga untuk sesi utama (`/model`).

## 2. Aturan hemat

1. **Satu sub-agent per tugas kecil**, bukan satu agent untuk seluruh proyek.
2. **Tugas eksplisit**: nama file, fungsi yang diminta, tes yang harus lulus.
3. **Jangan jalankan sub-agent paralel** kecuali benar-benar terpisah (misal firmware dan vision setelah contract terkunci).
4. **Sesi utama tidak membaca ulang kode** yang baru ditulis. Percayai laporan dan `pytest`; baca file hanya saat tes gagal.
5. **Reviewer sekali per fase besar** (setelah fase 2 dan 4), bukan tiap tugas kecil.
6. **Minta ringkasan, bukan salinan kode.**
7. **Berhenti dan tanya** bila butuh data hardware atau keputusan yang mengubah contract.
8. **Commit tiap fase selesai.**

## 3. Urutan kerja

Tiap fase: sesi utama memberi tugas ke `builder`, memeriksa laporan dan `pytest`, lalu commit.

### Fase 0: Kerangka repo

Builder: struktur `architecture.md` bagian 7, `config.py` dengan konstanta TODO, `requirements.txt` (`opencv-python`, `pyserial`, `jsonschema`, `pytest`, `matplotlib`), `__init__.py`, `.gitignore`.
Selesai bila: `pytest` berjalan dan struktur sesuai.

### Fase 1: Contracts

Builder: schema di `contracts/`, `validate.py`, `tests/test_contracts.py`.
Selesai bila: tes lulus. Manusia memeriksa `description` (satuan, arah sumbu). Nilai placeholder (batas posisi dan tilt) boleh diganti nanti.

### Fase 2: Logger, mock, bridge, main (tanpa hardware)

Dua tugas berurutan:
1. `logger.py` (+ `step_metrics`, `--analyze`) dan `mocks.py`, dengan tes.
2. `bridge.py` (port palsu) dan `main.py` (`--mock`, `--no-vision`, perintah ketikan), dengan tes.
Selesai bila: `python -m laptop.main --mock --csv demo.csv` menampilkan data live, `sp` dan `gains` bekerja, CSV terisi, `pytest` lulus. Jalankan `reviewer`.

### Fase 3: Vision dan calibrate

Dua tugas:
1. `vision.py` dengan tes gambar sintetis.
2. `calibrate.py`.
Manusia (butuh kamera dan pelat dari teman): jalankan `calibrate.py`, isi `config.py`, ukur fps dan latensi nyata. Jika tidak memadai, pertimbangkan rencana cadangan `architecture.md` bagian 11.

### Fase 4: Firmware

Builder: `firmware/controller/controller.ino` sesuai `instructions.md`, dengan komentar langkah uji manual.
Manusia mengompilasi dan mem-flash, lalu uji bertahap:
1. Telemetry muncul di logger (`python -m laptop.main --port <PORT> --no-vision`) tanpa servo terpasang.
2. Servo ke posisi datar; lakukan kalibrasi pusat, arah, dan rasio (`instructions.md`).
3. Kirim `ball_position` palsu lewat terminal, pastikan servo bereaksi ke arah yang benar dan failsafe bekerja saat data berhenti.
4. Servo terpasang di pelat, tanpa bola, uji sapuan kecil.
Jalankan `reviewer` pada firmware.

### Fase 5: Integrasi, tuning, bukti step response

Manusia memimpin di rig:
1. `python -m laptop.main --port <PORT> --csv run1.csv` dengan kamera dan ESP32 asli.
2. Tuning sesuai "Prosedur tuning PID" di `instructions.md`; builder hanya untuk perbaikan kode kecil (filter, anti-windup, dsb.).
3. Uji step (`architecture.md` bagian 10), simpan CSV per percobaan.
4. Builder (kecil): lengkapi `--plot` dan tabel metrik jika belum.
Selesai bila: minimal 3 CSV step per sumbu, plot, dan tabel metrik ada di `docs/`.

### Fase 6 (opsional): Dashboard web

Hanya setelah fase 5. Tambah pelanggan telemetry baru di bridge (WebSocket) dan halaman plot. Contract dan firmware tidak berubah.

## 4. Template tugas ke builder

```
Tugas: <satu kalimat>
Baca: instructions.md bagian <nama>, architecture.md bagian <nomor>
File yang dibuat/diubah: <daftar>
Harus lulus: pytest tests/<nama>.py   (untuk firmware: kompilasi jika bisa)
Jangan: <yang tidak boleh disentuh, misal contracts/>
Laporan: maksimal 10 baris
```

Contoh:

```
Tugas: Implementasikan laptop/logger.py (tampilan terminal, CSV, step_metrics, --analyze).
Baca: instructions.md bagian "laptop/logger.py", architecture.md bagian 10
File yang dibuat/diubah: laptop/logger.py, tests/test_logger.py
Harus lulus: pytest tests/test_logger.py
Jangan: ubah contracts/
Laporan: maksimal 10 baris
```

## 5. Yang dibutuhkan dari teman (hardware)

| Hal | Kapan dibutuhkan |
|---|---|
| Ukuran pelat (mm) | fase 3 (`PLATE_SIZE_MM`, batas contract) |
| Pin servo ESP32 dan posisi kamera | fase 4 |
| Rig siap untuk uji | fase 3-5 |
| Skematik, BOM, foto, video hardware | pengumpulan |

## 6. Jika macet

- **Tes gagal berulang:** minta builder melaporkan penyebab dan asumsi sebelum diulang; perbaiki spesifikasi, baru jalankan lagi.
- **Bola tidak terdeteksi stabil:** periksa cahaya, kontras, HSV, auto-exposure.
- **Telemetry tidak muncul:** periksa baud, port tidak dipakai program lain (tutup serial monitor Arduino), format envelope.
- **Sistem osilasi atau liar:** periksa urutan: arah servo, latensi kamera, backlash linkage, baru gain.
- **Servo jitter atau ESP32 reset:** hampir pasti daya (adaptor terpisah, common ground, kapasitor).
- **Kamera terlalu lambat:** rencana cadangan resistive panel.
