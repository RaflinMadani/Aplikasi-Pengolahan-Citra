# Invisible Image Watermarking Berbasis Discrete Wavelet Transform (DWT) untuk Perlindungan Hak Cipta Citra Digital

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green)
![PyWavelets](https://img.shields.io/badge/PyWavelets-1.x-orange)
![License](https://img.shields.io/badge/License-MIT-brightgreen)

Dokumen ini berisi dokumentasi lengkap mengenai proyek akhir mata kuliah **Pengolahan Citra Digital**. Proyek ini bertujuan untuk mengimplementasikan dan menganalisis metode *Invisible Image Watermarking* berbasis **Discrete Wavelet Transform (DWT)** sebagai solusi perlindungan hak cipta citra digital yang tahan terhadap berbagai manipulasi/serangan (*image attacks*).

---

## 📋 Daftar Isi
1. [Latar Belakang & Permasalahan](#-latar-belakang--permasalahan)
2. [Tujuan Proyek](#-tujuan-proyek)
3. [Metodologi: Discrete Wavelet Transform (DWT)](#-metodologi-discrete-wavelet-transform-dwt)
4. [Skenario Pengujian & Metrik Evaluasi](#-skenario-pengujian--metrik-evaluasi)
5. [Arsitektur Sistem & Alur Kerja](#-arsitektur-sistem--alur-kerja)
6. [Struktur Repositori](#-struktur-repositori)
7. [Panduan Instalasi & Penggunaan](#-panduan-instalasi--penggunaan)
8. [Anggota Kelompok](#-anggota-kelompok)

---

## 🚨 Latar Belakang & Permasalahan

Di era digital saat ini, penyebaran konten visual (gambar/citra) di media sosial dan internet terjadi secara masif dan cepat. Namun, kemudahan akses ini membawa masalah serius terkait **pelanggaran hak cipta**, klaim kepemilikan ilegal, dan manipulasi citra tanpa izin pemilik aslinya.

### Mengapa *Invisible Watermarking*?
* **Visible Watermarking** (tanda air yang terlihat seperti logo/teks transparan) sering kali merusak estetika citra dan dapat dengan mudah dihapus menggunakan teknik *cropping* atau *retouching/inpainting*.
* **Invisible Watermarking** menyisipkan data tersembunyi (tanda pengenal/hak cipta) langsung ke dalam piksel atau frekuensi citra tanpa mengubah penampilan visual citra tersebut secara kasat mata.

### Tantangan Utama
Watermark yang disisipkan harus memenuhi dua kriteria utama yang saling bertolak belakang:
1. **Imperceptibility (Tidak Terlihat):** Kualitas citra ber-watermark harus tetap terjaga tinggi sehingga perbedaan dengan citra asli tidak dapat dibedakan oleh mata manusia.
2. **Robustness (Ketahanan):** Watermark harus tetap dapat diekstraksi/dibaca kembali meskipun citra telah mengalami berbagai gangguan atau serangan (*image attacks*) seperti kompresi JPEG, pemotongan (*cropping*), maupun pengubahan ukuran (*resizing*).

---

## 🎯 Tujuan Proyek

1. **Mengimplementasikan** algoritma *Invisible Image Watermarking* pada domain frekuensi menggunakan metode **Discrete Wavelet Transform (DWT)** dengan bahasa pemograman Python.
2. **Mengevaluasi** kualitas visual citra hasil penyisipan watermark (*imperceptibility*) menggunakan metrik **PSNR** dan **SSIM**.
3. **Menguji ketahanan** watermark (*robustness*) terhadap berbagai variasi serangan citra (Kompresi JPEG dan *Cropping*) menggunakan metrik **BER**.
4. **Menyediakan** analisis performa yang komprehensif sebagai bahan laporan akhir mata kuliah Pengolahan Citra Digital.

---

## 🔬 Metodologi: Discrete Wavelet Transform (DWT)

Pendekatan ini bekerja pada **domain frekuensi**. Citra akan diurai menjadi beberapa sub-band frekuensi menggunakan transformasi wavelet (misal: *Haar Wavelet*):

* **LL (Low-Low):** Berisi informasi frekuensi rendah (representasi citra secara umum/skala kecil).
* **LH (Low-High):** Berisi detail frekuensi horizontal (tepi horizontal).
* **HL (High-Low):** Berisi detail frekuensi vertikal (tepi vertikal).
* **HH (High-High):** Berisi detail frekuensi tinggi/diagonal (noise dan detail sangat halus).

```
+---------------+---------------+
|               |               |
|   Sub-band    |   Sub-band    |
|      LL       |      HL       |
|  (Approxim.)  |  (Horizontal) |
+---------------+---------------+
|               |               |
|   Sub-band    |   Sub-band    |
|      LH       |      HH       |
|   (Vertical)  |  (Diagonal)   |
+---------------+---------------+
```

Dalam proyek ini, watermark disisipkan pada **sub-band detail (LH / HL)** untuk menjaga keseimbangan terbaik antara transparansi visual (tidak merusak gambaran umum di LL) dan ketahanan terhadap gangguan.

---

## 📊 Skenario Pengujian & Metrik Evaluasi

### 1. Uji Kualitas Visual (*Imperceptibility*)
* **PSNR (Peak Signal-to-Noise Ratio):** Mengukur rasio antara daya maksimum sinyal citra asli dengan noise penyisipan. Target nilai $PSNR > 35\text{ dB}$ (menandakan penyisipan berkualitas baik tanpa distorsi kasat mata).
* **SSIM (Structural Similarity Index Measure):** Mengukur tingkat kemiripan struktur visual antara citra asli dan citra ber-watermark. Rentang nilai $0$ hingga $1$ (target $SSIM > 0.95$).

### 2. Uji Ketahanan (*Robustness*) terhadap Serangan
Citra ber-watermark akan diberi manipulasi buatan:
* **Kompresi JPEG:** Pengujian dengan faktor kualitas kompresi bervariasi (misal: Q = 90, 70, 50, 30).
* **Cropping (Pemotongan):** Pemotongan area citra sebesar 10%, 25%, dan 50%.
* **Resizing (Pengubahan Ukuran):** Downscaling lalu upscaling kembali ke ukuran semula.

### 3. Ekstraksi Watermark & Perhitungan Error
* **BER (Bit Error Rate):** Mengukur persentase rasio kesalahan bit watermark yang diekstraksi dibandingkan bit watermark asli setelah mengalami serangan. Semakin dekat nilai BER ke $0\%$, semakin handal sistem watermarking tersebut.

---

## 🛠️ Arsitektur Sistem & Alur Kerja

```
[Citra Asli] ---+
                |---> [DWT Decomposition] ---> [Penyisipan Watermark] ---> [IDWT] ---> [Citra Ber-Watermark]
[Watermark]  ---+                                                                             |
                                                                                              v
                                                                                    [Simulasi Serangan]
                                                                                              |
                                                                                              v
[Watermark Hasil Ekstraksi] <--- [DWT & Extraction] <-----------------------------------------+
            |
            v
 [Hitung BER & PSNR]
```

---

## 📁 Struktur Repositori

```text
├── app.py                 # Titik masuk dashboard web (Flask)
├── config.py              # Konfigurasi (env var WM_*)
├── main.py                # Skrip CLI: pengujian batch otomatis
├── run.sh / run.bat       # Peluncur satu langkah (venv + install + run)
├── requirements.txt
├── PROJECT_CONTEXT.md     # Dokumentasi teknis lengkap proyek
├── src/                   # Pustaka inti (tanpa dependensi web)
│   ├── dwt_watermark.py   # DWT + QIM: penyisipan & ekstraksi blind
│   ├── codec.py           # Logo / teks / biner <-> vektor bit
│   ├── attacks.py         # JPEG, crop, resize, derau
│   └── metrics.py         # PSNR, SSIM, BER
├── webapp/                # Dashboard web
│   ├── api.py             # REST API
│   ├── storage.py         # Riwayat per sesi (berkas)
│   ├── templates/index.html
│   └── static/{css,js}/
├── tests/                 # 14 unit/integration test (unittest)
├── dataset/{original,watermark}/
├── results/               # Keluaran main.py (CSV, grafik)
└── storage/               # Data sesi dashboard (otomatis)
```

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Prasyarat
Pastikan Python 3.8+ sudah terinstal di sistem Anda.

### 2. Kloning Repositori & Instalasi Dependensi
```bash
# Kloning repositori ini
git clone https://github.com/RaflinMadani/Aplikasi-Pengolahan-Citra
cd Aplikasi-Pengolahan-Citra

# Instal dependensi yang diperlukan
pip install -r requirements.txt
```

### 3. Menjalankan Pengujian
Untuk menjalankan alur lengkap penyisipan, simulasi serangan, dan kalkulasi metrik:
```bash
python main.py
```

### 4. Menjalankan Dashboard Web
```bash
python app.py          # lalu buka http://127.0.0.1:5000
# atau satu langkah:  bash run.sh   (Linux/macOS)  |  run.bat  (Windows)
```
Menu: Beranda, Penyisipan, Ekstraksi, Simulasi serangan, dan Riwayat. Dokumentasi teknis lengkap ada di [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).

### 5. Menjalankan Test
```bash
python -m unittest discover -s tests -v
```
