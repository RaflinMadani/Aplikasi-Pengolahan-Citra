# 🔐 Deep Learning Invisible Image Watermarking
### Encoder – Noise Layer – Decoder (CNN, PyTorch)

Proyek akhir **Pengolahan Citra Digital**. Model belajar menyisipkan pesan bit tak kasat mata ke dalam citra dan mengekstraknya kembali, bahkan setelah citra diserang (JPEG, crop, noise, blur, resize). Arsitektur mengikuti kerangka **HiDDeN** (Zhu et al., 2018).

---

## 📋 Daftar Isi
1. [Alur Kerja Proyek](#-alur-kerja-proyek)
2. [Struktur Repositori](#-struktur-repositori)
3. [Data yang Dibutuhkan](#-data-yang-dibutuhkan)
4. [Instalasi](#-instalasi)
5. [Langkah Menjalankan (Step-by-Step)](#-langkah-menjalankan-step-by-step)
6. [Cara Memeriksa Alur Kerja (Checklist)](#-cara-memeriksa-alur-kerja-checklist)
7. [Membaca Hasil & Target Metrik](#-membaca-hasil--target-metrik)
8. [Referensi Parameter](#-referensi-parameter)
9. [Troubleshooting](#-troubleshooting)
10. [Referensi](#-referensi)

---

## 🔄 Alur Kerja Proyek

```
 DATA                 TRAINING (train.py)                              OUTPUT
┌──────────┐   ┌──────────────────────────────────────────────┐   ┌───────────────────┐
│ data/    │   │ Cover ─┐                                      │   │ checkpoints/      │
│  train/  │──▶│        ├▶ ENCODER ─▶ NOISE LAYER ─▶ DECODER ─▶│──▶│  best_model.pth   │
│  val/    │   │ Pesan ─┘      │      (JPEG/crop/…)      │     │   │  last_model.pth   │
└──────────┘   │               ▼                         ▼     │   │ results/          │
               │        loss_enc (MSE)            loss_dec (BCE)│   │  training_log.csv │
               │         [+ Discriminator opsional]             │   └─────────┬─────────┘
               └──────────────────────────────────────────────┘             │
                                                                              ▼
        ┌─────────────────────────────┐    ┌──────────────────────────────────────┐
        │ inference.py  (demo 1 gambar)│◀───│ evaluate.py (PSNR, SSIM, BER/serangan)│
        └─────────────────────────────┘    └──────────────────────────────────────┘
```

Loss total: `L = λ_enc · MSE(cover, watermarked) + λ_dec · BCE(pesan, pesan_terekstrak) [+ λ_adv · loss_adversarial]`

---

## 📁 Struktur Repositori

```
Aplikasi-Pengolahan-Citra/
├── data/                      # Dataset (isi sendiri, lihat bagian Data)
│   ├── train/                 # citra latih
│   └── val/                   # citra validasi/uji
├── models/
│   ├── encoder.py             # Encoder CNN (cover + pesan -> watermarked)
│   ├── decoder.py             # Decoder CNN (citra -> logit bit pesan)
│   └── discriminator.py       # (Opsional) GAN untuk menjaga kualitas visual
├── utils/
│   ├── metrics.py             # PSNR, SSIM, BER
│   ├── noise_layers.py        # Simulasi serangan: JPEG, crop, noise, blur, resize, dropout
│   ├── dataset_loader.py      # PyTorch DataLoader
│   └── prepare_data.py        # Pembuat subset train/val dari dataset mentah
├── checkpoints/               # Bobot model (.pth) hasil training
├── results/                   # Log training, tabel evaluasi, gambar sampel
├── train.py                   # Training loop
├── evaluate.py                # Evaluasi imperceptibility + robustness
├── inference.py               # Demo embed / extract / demo serangan 1 gambar
├── smoke_test.py              # Uji alur kerja TANPA dataset (data sintetis)
├── requirements.txt
└── README.md
```

---

## 📦 Data yang Dibutuhkan

**Hanya gambar saja.** Label/anotasi (kelas ImageNet, bounding box) **tidak dipakai**, karena pesan rahasia dibuat acak oleh program saat training.

### Kebutuhan jumlah

| Tahap | Train | Val | Keterangan |
|---|---|---|---|
| Uji alur (`smoke_test.py`) | 0 | 0 | Data sintetis otomatis |
| Debug cepat (1–2 epoch) | 100–500 | 20–100 | Cukup untuk memastikan kode jalan |
| **Proyek utama (sesuai rancangan)** | **~10.000** | **~1.000** | Train dan val tidak boleh tumpang tindih |
| Benchmark tambahan (opsional) | – | 24–100 | Uji generalisasi di dataset berbeda |

Ukuran citra akhir **256 × 256** (diatur otomatis oleh `prepare_data.py` / DataLoader). Format jpg/png.

### Sumber dataset

| Dataset | Peran | Ukuran ± | Link |
|---|---|---|---|
| **ImageNet ILSVRC2012** (utama sesuai rancangan) | Train + Val | Val 50k citra ≈ 6 GB; train penuh ≈ 140 GB | Resmi: https://www.image-net.org/ · Kaggle: https://www.kaggle.com/c/imagenet-object-localization-challenge · Hugging Face: https://huggingface.co/datasets/ILSVRC/imagenet-1k |
| **Imagenette** (subset kecil ImageNet) | Debug / pengganti jika internet/disk terbatas | ≈ 0,3 GB (versi 320px) | https://github.com/fastai/imagenette |
| **MS COCO 2017** | Alternatif utama (tanpa akun) | val2017 ≈ 1 GB (5k citra); train2017 ≈ 18 GB | https://cocodataset.org/#download |
| **DIV2K** | Benchmark resolusi tinggi | valid ≈ 0,4 GB (100 citra) | https://data.vision.ee.ethz.ch/cvl/DIV2K/ |
| **Kodak (24 citra)** | Benchmark klasik PSNR/SSIM | ≈ 15 MB | http://r0k.us/graphics/kodak/ |
| **USC-SIPI** | Citra uji klasik (Lena, Baboon, dll.) | ≈ 0,2 GB | https://sipi.usc.edu/database/ |

> ⚠️ ImageNet butuh akun (gratis, ada persetujuan syarat penggunaan). Tidak perlu mengunduh seluruh train set: **cukup validation set (≈6 GB)** atau satu-dua bagian saja, lalu ambil 11.000 citra acak dengan skrip di bawah. Jika ada tautan yang berubah, cari nama dataset di situs resminya.

### Menyiapkan subset otomatis

```bash
# Dari folder gambar mentah (ImageNet val / COCO val2017 / Imagenette, dll.)
python -m utils.prepare_data --source /path/ke/gambar_mentah --num_train 10000 --num_val 1000
```
Hasilnya: `data/train/` dan `data/val/` berisi citra acak, tidak tumpang tindih, di-resize + center-crop ke 256×256 (training jadi jauh lebih cepat karena tidak perlu membaca file raksasa).

**Rekomendasi jalur cepat:** unduh **COCO val2017** (5k) atau **Imagenette** → `prepare_data` (misal `--num_train 4000 --num_val 500`) → training. Untuk hasil akhir laporan, gunakan 10.000/1.000 dari ImageNet.

---

## ⚙️ Instalasi

Prasyarat: **Python 3.9+**. GPU NVIDIA + CUDA sangat disarankan (tanpa GPU tetap jalan, tetapi lambat; alternatifnya Google Colab).

```bash
cd Aplikasi-Pengolahan-Citra
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```
Untuk GPU, install PyTorch versi CUDA lebih dulu mengikuti https://pytorch.org/get-started/locally/ lalu jalankan `pip install -r requirements.txt`.

---

## ▶️ Langkah Menjalankan (Step-by-Step)

### Langkah 0 — Uji alur tanpa data
```bash
python smoke_test.py
```
Harus berakhir dengan `SEMUA OK`. Ini memastikan model, serangan, metrik, backprop, dan DataLoader berfungsi sebelum menghabiskan waktu training.

### Langkah 1 — Siapkan data
```bash
python -m utils.prepare_data --source /path/ke/gambar_mentah
```
(atau salin gambar manual ke `data/train/` dan `data/val/`).

### Langkah 2 — Uji coba training singkat
```bash
python train.py --epochs 1 --batch_size 4 --num_train 100 --num_val 20 --num_workers 0
```

### Langkah 3 — Training penuh
```bash
python train.py --epochs 50 --batch_size 16 --lr 0.001
# dengan discriminator (GAN, opsional, citra lebih halus):
python train.py --epochs 50 --use_discriminator
# lanjutkan training yang terputus:
python train.py --epochs 50 --resume checkpoints/last_model.pth
```

### Langkah 4 — Evaluasi
```bash
python evaluate.py --model_path checkpoints/best_model.pth --data_dir data/val
```

### Langkah 5 — Demo satu gambar
```bash
# Sisipkan pesan teks (kapasitas default 30 bit ≈ 3 karakter ASCII)
python inference.py embed --image foto.jpg --text "Hak" --output results/watermarked.png

# Ekstrak kembali
python inference.py extract --image results/watermarked.png

# Sisip -> serang -> ekstrak sekaligus (hasil: results/demo.png)
python inference.py demo --image foto.jpg --attack jpeg --param 50
python inference.py demo --image foto.jpg --attack crop --param 0.3
```
Simpan hasil embed sebagai **PNG** (lossless). Menyimpan sebagai JPEG sama dengan serangan kompresi.

---

## ✅ Cara Memeriksa Alur Kerja (Checklist)

Centang berurutan. Jika satu langkah gagal, perbaiki dulu sebelum lanjut.

| # | Pemeriksaan | Perintah | Hasil yang diharapkan |
|---|---|---|---|
| 1 | Instalasi benar | `python -c "import torch, cv2; print(torch.__version__)"` | Versi tercetak tanpa error |
| 2 | Seluruh komponen berfungsi | `python smoke_test.py` | Semua baris `[OK]`, akhir `SEMUA OK` |
| 3 | Data terbaca | `python train.py --epochs 1 --num_train 50 --num_val 10 --batch_size 4 --num_workers 0` | Cetak `Train: 50 citra`, epoch selesai, `last_model.pth` muncul di `checkpoints/` |
| 4 | Loss turun | Buka `results/training_log.csv` setelah beberapa epoch | `train_loss` menurun, `train_ber_pct` turun dari ±50% |
| 5 | Model tidak overfit | Bandingkan `train_*` vs `val_*` | `val_ber_pct` mengikuti `train_ber_pct` (selisih kecil) |
| 6 | Watermark tak terlihat | Buka `results/samples.png` | Baris 1 (asli) dan 2 (watermarked) tampak identik; baris 3 (selisih ×10) hanya pola halus |
| 7 | Target kualitas | Output `evaluate.py` | PSNR > 38 dB, SSIM > 0,96 |
| 8 | Target ketahanan | Tabel BER `evaluate.py` | BER mendekati 0% (tanpa serangan, JPEG 90/70) |
| 9 | Pipeline end-to-end | `python inference.py demo --image foto.jpg --attack jpeg --param 70` | `BER` kecil, panel di `results/demo.png` |

**Tanda-tanda sehat saat training**
- Awal training: BER ≈ 50% (tebakan acak). Itu normal.
- Seiring epoch: BER turun, PSNR stabil di kisaran tinggi.
- BER tetap ≈ 50% setelah banyak epoch berarti bermasalah (lihat Troubleshooting).

---

## 📊 Membaca Hasil & Target Metrik

| Metrik | Arti | Target |
|---|---|---|
| **PSNR** | Kemiripan watermarked vs asli (dB), makin tinggi makin baik | > 38 dB |
| **SSIM** | Kemiripan struktur (0–1) | > 0,96 |
| **BER** | % bit pesan yang salah diekstrak. 0% = sempurna, 50% = acak | → 0% |

Skenario serangan di `evaluate.py`: JPEG (QF 90/70/50), Crop (10/30/50% area hilang), Gaussian noise (σ 0,01/0,05), Resize (75%/50%).
Hasil tersimpan di `results/evaluation_results.csv` (tabel untuk laporan) dan `results/samples.png` (bukti visual).

> Catatan: PSNR dan ketahanan saling tarik-menarik. Menaikkan `--lambda_enc` memperbaiki PSNR tetapi BER bisa naik, dan sebaliknya.

---

## 🧩 Referensi Parameter

| Parameter | Default | Fungsi |
|---|---|---|
| `--epochs` | 50 | Jumlah epoch |
| `--batch_size` | 16 | Turunkan jika memori GPU habis |
| `--lr` | 0.001 | Learning rate (Adam) |
| `--msg_len` | 30 | Kapasitas pesan (bit). Makin besar makin sulit |
| `--image_size` | 256 | Ukuran citra latih |
| `--num_train` / `--num_val` | 10000 / 1000 | Jumlah citra dipakai (0 = semua) |
| `--lambda_enc` | 0.7 | Bobot loss visual (↑ = PSNR naik) |
| `--lambda_dec` | 1.0 | Bobot loss pesan (↑ = BER turun) |
| `--use_discriminator` | off | Aktifkan GAN; `--lambda_adv` 0.001 |
| `--resume` | – | Lanjutkan dari checkpoint |
| `--num_workers` | 4 | Set 0 jika error di Windows |

---

## 🛠️ Troubleshooting

| Masalah | Solusi |
|---|---|
| `FileNotFoundError: Tidak ada citra` | Folder `data/train` atau `data/val` kosong atau salah path |
| `CUDA out of memory` | Turunkan `--batch_size` (8 atau 4) atau `--image_size` (128) |
| Error multiprocessing di Windows | Tambah `--num_workers 0` |
| Training sangat lambat | Pakai GPU/Colab; pra-proses data dengan `prepare_data` (256×256) |
| BER stagnan ≈ 50% | Latih lebih lama; turunkan `--msg_len` (misal 16); naikkan `--lambda_dec`; cek `smoke_test.py` |
| PSNR rendah (< 38 dB) | Naikkan `--lambda_enc` (misal 1.5); latih lebih lama; coba `--use_discriminator` |
| Ekstraksi gagal pada hasil embed | Pastikan disimpan sebagai **PNG**, bukan JPEG |
| `evaluate.py` lambat | Kurangi `--num_images` (misal 200); serangan JPEG berjalan di CPU |

---

## 📚 Referensi
- Zhu, J., Kaplan, R., Johnson, J., Fei-Fei, L. **HiDDeN: Hiding Data With Deep Networks**, ECCV 2018. https://arxiv.org/abs/1807.09937
- Implementasi acuan HiDDeN (PyTorch): https://github.com/ando-khachatryan/HiDDeN
- Deng, J. et al. **ImageNet: A Large-Scale Hierarchical Image Database**, CVPR 2009. https://www.image-net.org/
