"""Konfigurasi laptop. Tidak boleh import cv2 (supaya mudah dites tanpa kamera)."""

BAUD = 115200
FRAME_W = 640
FRAME_H = 480
POSITION_RATE_HZ = 60  # laju kirim ball_position; firmware loop 100 Hz
QUEUE_SIZE = 2  # q_position kecil, data lama dibuang jika penuh

SERIAL_PORT = "/dev/ttyUSB0"  # TODO: isi setelah hardware jadi
CAMERA_INDEX = 0  # TODO: isi setelah hardware jadi
PLATE_SIZE_MM = (300.0, 300.0)  # TODO: isi setelah hardware jadi (lebar, tinggi mm)
# Sudut pelat di gambar (px): kiri-atas, kanan-atas, kanan-bawah, kiri-bawah
PLATE_CORNERS_PX = [(80, 0), (560, 0), (560, 480), (80, 480)]  # TODO: isi setelah hardware jadi
HSV_LOW = (5, 120, 120)  # TODO: isi setelah hardware jadi (oranye)
HSV_HIGH = (20, 255, 255)  # TODO: isi setelah hardware jadi
