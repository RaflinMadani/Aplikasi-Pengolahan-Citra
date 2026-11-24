# PROJECT_CONTEXT — Lab Watermark DWT

Dokumen acuan teknis untuk **Invisible Image Watermarking berbasis DWT** beserta dashboard webnya. Ditujukan bagi anggota tim, dosen penguji, dan siapa pun yang akan melanjutkan proyek ini. Baca dari atas ke bawah untuk memahami proyek; atau lompat ke bagian yang dibutuhkan.

| | |
|---|---|
| Konteks | Proyek akhir mata kuliah Pengolahan Citra Digital |
| Tujuan | Melindungi hak cipta citra digital dengan watermark tak terlihat yang tahan terhadap manipulasi |
| Bahasa / runtime | Python 3.8+ (diuji pada 3.12), JavaScript ES2020 di browser |
| Antarmuka | Dashboard web (Flask + vanilla JS) dan CLI batch (`main.py`) |
| Lisensi | MIT |

---

## 1. Ringkasan Eksekutif

Sistem menyisipkan data tersembunyi (logo biner, teks, atau string bit) ke dalam **koefisien frekuensi** citra memakai Discrete Wavelet Transform (DWT) dan Quantization Index Modulation (QIM). Ekstraksi bersifat **blind**: hanya butuh citra yang diuji, kunci, dan parameter, tanpa citra asli.

Hasil terukur (Δ = 36, wavelet Haar, level 2, logo 32×32 = 1024 bit, rata-rata 3 citra uji 512×512):

- **Imperceptibility:** PSNR ≈ 40,1 dB (target > 35), SSIM ≈ 0,956 (target > 0,95).
- **Robustness:** BER 0% pada JPEG Q ≥ 70 dan crop 10%; ≈ 0,2% pada JPEG Q=50; ≈ 1,2% pada crop 25%; ≈ 1,6% pada resize 0,5×.
- **Titik lemah:** JPEG Q ≤ 30 (BER ≈ 9%) dan crop 50% (BER ≈ 20%). Lihat bagian 13 dan 16.

---

## 2. Tujuan dan Ruang Lingkup

**Tujuan**
1. Mengimplementasikan watermarking invisible pada domain frekuensi (DWT) dengan Python.
2. Mengevaluasi kualitas visual (PSNR, SSIM) dan ketahanan (BER) terhadap JPEG, cropping, resizing, dan derau.
3. Menyediakan dashboard interaktif untuk demo dan eksperimen parameter.
4. Menyediakan bahan analisis untuk laporan akhir.

**Di dalam lingkup:** penyisipan/ekstraksi blind, tiga jenis payload (logo, teks, biner), wavelet Haar/Db1/Db4, level 1–2, empat jenis serangan, metrik PSNR/SSIM/BER, riwayat per sesi.

**Di luar lingkup (saat ini):** serangan geometris (rotasi, perspektif, flip), autentikasi pengguna, basis data, deployment multi-instance, enkripsi payload, koreksi kesalahan (ECC). Lihat roadmap di bagian 17.

---

## 3. Teknologi

| Lapisan | Teknologi | Peran |
|---|---|---|
| Algoritma | **NumPy** | Aritmetika vektor, DWT Haar (implementasi sendiri), QIM |
| | **PyWavelets** (opsional untuk Haar, wajib untuk Db4) | DWT keluarga Daubechies, mode `periodization` |
| | **OpenCV** (`opencv-python`) | Baca/tulis citra, konversi YCrCb, JPEG, resize, Otsu |
| | **scikit-image** | SSIM |
| Backend | **Flask 3** | REST API dan penyajian halaman |
| Frontend | HTML + CSS + JavaScript murni | Tanpa build step, tanpa framework; font Google (dengan fallback sistem) |
| Penyimpanan | Berkas di folder `storage/` | Riwayat per sesi (PNG + `items.json`) |
| CLI / laporan | pandas, matplotlib | Tabel dan grafik di `main.py` |
| Pengujian | `unittest` (bawaan Python) | 14 test; opsional skrip E2E Playwright |

Pilihan "tanpa framework frontend" disengaja: proyek bisa dijalankan dengan `python app.py` tanpa Node.js, dan seluruh kode UI (±600 baris) mudah dibaca saat sidang.

---

## 4. Arsitektur

```
Browser (SPA vanilla JS, router berbasis hash)
   │  fetch + header X-Session-Id
   ▼
Flask  ── webapp/api.py  (validasi input, orkestrasi, format respons)
   │         │
   │         ├── webapp/storage.py   (riwayat per sesi: berkas PNG + items.json)
   │         └── src/                (pustaka inti, tanpa dependensi web)
   │               ├── dwt_watermark.py  embed / extract / DWT / QIM
   │               ├── codec.py          logo·teks·biner <-> bit
   │               ├── attacks.py        JPEG · crop · resize · derau
   │               └── metrics.py        PSNR · SSIM · BER
   ▼
storage/<session-id>/<item-id>/*.png  +  storage/<session-id>/items.json
```

Prinsip desain:
- **`src/` bebas dari Flask.** CLI, test, dan API memakai pustaka yang sama, sehingga hasil konsisten di mana pun.
- **API stateless terhadap proses.** Seluruh state ada di berkas; browser hanya menyimpan `session id`.
- **Parameter ikut tersimpan di tiap item riwayat** sehingga ekstraksi dan serangan dapat diulang tanpa mengetik ulang.

### Alur data

```
Penyisipan : cover + payload + parameter ──▶ embed() ──▶ watermarked.png
                                               └──▶ ekstraksi langsung ──▶ PSNR · SSIM · BER
Serangan   : watermarked.png ──▶ apply_chain() ──▶ attacked.png ──▶ extract() ──▶ BER
Ekstraksi  : citra uji + (ref riwayat | parameter manual) ──▶ extract() ──▶ payload [+ BER]
```

---

## 5. Struktur Folder

```text
invisible-watermarking-dwt/
├── app.py                  Titik masuk Flask:  python app.py
├── config.py               Konfigurasi dan batas; bisa di-override env var WM_*
├── main.py                 CLI batch: uji semua citra × semua serangan → results/
├── requirements.txt
├── run.sh / run.bat        Peluncur satu langkah (buat venv, instal, jalankan)
├── README.md               Dokumentasi singkat proyek
├── PROJECT_CONTEXT.md      Dokumen ini
├── .gitignore
│
├── src/                    ── PUSTAKA INTI ──
│   ├── dwt_watermark.py    DWT (Haar NumPy / PyWavelets), QIM, embed(), extract(), capacity()
│   ├── codec.py            image_to_bits, text_to_bits, binary_string_to_bits, dan kebalikannya
│   ├── attacks.py          jpeg_compress, crop, crop_rect, resize_attack, gaussian_noise, apply_chain
│   └── metrics.py          psnr, ssim, ber, bit_errors
│
├── webapp/                 ── DASHBOARD ──
│   ├── __init__.py         create_app(), error handler global, registrasi blueprint
│   ├── api.py              Semua endpoint /api/*, validasi, serialisasi
│   ├── storage.py          SessionStore: add/list/get/path/delete/clear (thread-safe)
│   ├── templates/index.html    Shell halaman (sidebar + <main>)
│   └── static/
│       ├── css/app.css     Design token, komponen, responsif
│       └── js/app.js       Router, komponen UI, 5 tampilan
│
├── tests/
│   ├── test_core.py        6 test pustaka inti
│   ├── test_api.py         8 test integrasi API (Flask test client)
│   └── e2e_playwright.py   Skrip E2E browser (opsional, perlu playwright)
│
├── dataset/
│   ├── original/           Citra host (3 sampel disertakan)
│   └── watermark/          Logo watermark (1 sampel disertakan)
├── results/                Keluaran main.py: CSV, grafik, citra ber-watermark
└── storage/                Data sesi dashboard (dibuat otomatis, di-ignore git)
```

---

## 6. Algoritma

### 6.1 Penyisipan (`dwt_watermark.embed`)

1. **Pisahkan luminans.** Citra BGR → YCrCb; hanya kanal **Y** yang dimodifikasi (kanal warna utuh, sehingga perubahan warna minimal dan tahan konversi JPEG yang men-subsample kroma).
2. **Dekomposisi DWT** level 1 atau 2 (`mode="periodization"`, sehingga ukuran sub-band tepat setengah dan transformasi ortonormal).
3. **Pilih sub-band** detail horizontal dan vertikal pada level terdalam (disebut HL/LH di README). Kedua sub-band digabung menjadi satu vektor koefisien.
4. **Posisi acak berkunci.** `np.random.RandomState(key).permutation(...)` memilih `n_bits × reps` posisi, dengan `reps = ⌊total / n_bits / 2⌋` (memakai separuh koefisien detail).
5. **QIM.** Tiap bit `b` diulang `reps` kali dan tiap koefisien `c` dikuantisasi ke kisi milik bit tersebut:

   ```
   Q_b(c) = Δ · round((c − b·Δ/2) / Δ) + b·Δ/2
   ```
6. **IDWT**, pembulatan ke `uint8`, gabungkan lagi dengan Cr dan Cb.

### 6.2 Ekstraksi blind (`dwt_watermark.extract`)

DWT citra uji → ambil koefisien pada posisi yang sama (kunci sama) → untuk tiap koefisien hitung skor `|c − Q₀(c)| − |c − Q₁(c)|` → **jumlahkan skor** semua salinan satu bit (*soft voting*) → skor > 0 berarti bit 1. Soft voting lebih tahan daripada mayoritas suara biasa karena koefisien yang "yakin" bobotnya lebih besar.

### 6.3 Mengapa desain ini tahan serangan

| Keputusan | Alasan |
|---|---|
| QIM, bukan penambahan aditif | Ekstraksi tidak butuh citra asli (blind) |
| Redundansi (reps ≈ 16–64×) | Kerusakan lokal (crop, JPEG) hanya merusak sebagian salinan |
| Posisi acak berkunci | Crop menghapus bagian koefisien yang tersebar merata, bukan satu bit utuh; tanpa kunci watermark tidak dapat dibaca |
| Level 2 sebagai default | Detail level 2 punya energi lebih besar sehingga lebih lestari saat kuantisasi JPEG |
| Hanya kanal Y | Menghindari artefak warna dan ketahanan terhadap subsampling kroma |

### 6.4 Kapasitas dan hubungan Δ–PSNR

- Jumlah bit maksimum ≈ `(2 · (H/2^L) · (W/2^L)) / 2` (reps ≥ 1). Untuk 512×512 level 2: 16.384 bit; praktis dipakai ≤ 4096 bit.
- Galat penyisipan per koefisien termodifikasi ≈ Δ²/12, sehingga **MSE ≈ (n_mod / N) · Δ²/12**. Contoh: level 2, 512×512, 1024 bit × 16 salinan → n_mod/N = 1/16 → MSE ≈ Δ²/192 → pada Δ=36, PSNR ≈ 39,8 dB (terukur 40,1 dB). Rumus ini membantu memilih Δ **sebelum** menjalankan eksperimen.

### 6.5 Payload (`codec.py`)

| Jenis | Bit | Catatan |
|---|---|---|
| Logo gambar | `size²` (16, 24, 32, 48, 64) | Otsu threshold; bit 1 = putih. Tanpa unggahan dipakai logo bawaan "DWT" |
| Teks | 256 tetap (32 byte UTF-8) | Dipadding `\x00`; dekode menghapus padding |
| Biner | 8–2048 | Panjang harus diberitahukan saat ekstraksi manual |

---

## 7. Metrik Evaluasi

| Metrik | Rumus | Target | Dipakai untuk |
|---|---|---|---|
| PSNR | `10·log10(255² / MSE)` dB | > 35 dB | Seberapa tak terlihat perubahan |
| SSIM | `skimage.metrics.structural_similarity` (per kanal) | > 0,95 | Kemiripan struktur visual |
| BER | `100 · (#bit salah / #bit total)` % | → 0% | Keterbacaan watermark setelah serangan |

PSNR/SSIM pada hasil serangan dihitung **terhadap citra asli sebelum penyisipan**. Jika MSE = 0, PSNR dilaporkan 100 dB (JSON tidak mendukung ∞).

Interpretasi BER di UI: 0% pulih sempurna · ≤ 5% hampir sempurna · ≤ 20% sebagian rusak · > 20% rusak. BER ≈ 50% berarti watermark tidak terbaca sama sekali (setara tebakan acak), misalnya saat kunci salah.

---

## 8. Fitur Dashboard (pemetaan ke kebutuhan)

| # | Kebutuhan | Implementasi |
|---|---|---|
| 1 | Beranda / ringkasan | Statistik (total citra, rata-rata PSNR, rata-rata BER), tombol aksi cepat, strip item terbaru, peta sub-band DWT |
| 2 | Penyisipan | Unggah drag-and-drop; watermark logo/teks/biner; pilihan wavelet (Haar, Db1, Db4), level 1/2, slider Alpha (Δ), kunci; pratinjau berdampingan + peta selisih 20×; unduh citra dan berkas kunci |
| 3 | Ekstraksi | Sumber dari riwayat atau unggahan manual; tombol ekstraksi; watermark hasil vs asli berdampingan (karakter salah ditandai merah) |
| 4 | Simulasi serangan | Slider JPEG 10–100, **crop interaktif** (seret area di atas citra atau pilih 10/25/50%), resize, derau Gaussian; hasil langsung tampil; **uji otomatis 13 serangan** dengan bar BER |
| 5 | Panel evaluasi | Kartu PSNR, SSIM, BER dengan status berwarna **dan** teks (tidak bergantung warna saja) pada setiap hasil |
| 6 | Riwayat & galeri | Per sesi, filter jenis, dialog detail, **Sisipkan ulang** (pakai ulang citra dan parameter tanpa unggah), uji serangan, ekstrak, unduh, hapus, kosongkan |

Catatan UX: urutan serangan berantai tetap, yaitu crop → resize → derau → JPEG (meniru alur nyata: edit lalu kompresi saat dibagikan).

---

## 9. Referensi REST API

Semua endpoint di bawah `/api`. Setiap request wajib membawa sesi lewat header `X-Session-Id` (atau query `?sid=` untuk `<img>`/unduhan). ID sesi: 8–64 karakter `[A-Za-z0-9_-]`; dibuat otomatis oleh browser. Galat selalu berbentuk `{"error": "pesan"}` dengan status 4xx/5xx.

| Metode & path | Fungsi | Masukan | Keluaran |
|---|---|---|---|
| `GET /health` | Cek hidup | — | `{status}` |
| `GET /options` | Opsi UI & batas | — | wavelet tersedia, `has_pywt`, ukuran watermark, rentang Δ |
| `GET /stats` | Statistik beranda | — | `total`, `counts`, `avg_psnr`, `avg_ber`, `recent` |
| `POST /embed` | Sisipkan | multipart: `cover` (atau `reuse_id`), `wm_type`, `wm_image`/`wm_text`/`wm_binary`, `wm_size`, `wavelet`, `level`, `delta`, `key` | `{item}` |
| `POST /extract` | Ekstrak | multipart: `image` dan/atau `ref_id`; bila tanpa `ref_id`: parameter + `wm_type`, `wm_size`/`wm_bits`, `ref_w`/`ref_h`, `exp_*` (watermark asli opsional) | `{item}` |
| `POST /attack` | Serang + ekstrak | JSON `{ref_id, attacks:[{type,...}]}` (1–6 langkah) | `{item}` |
| `POST /benchmark` | 13 serangan standar | JSON `{ref_id}` | `{rows:[{name,type,psnr,ssim,ber}]}` |
| `GET /history` | Daftar riwayat | — | `{items}` |
| `GET /history/<id>` | Satu item | — | `{item}` |
| `GET /history/<id>/config` | Unduh kunci | — | JSON terlampir |
| `DELETE /history/<id>` | Hapus item | — | `{ok}` |
| `DELETE /history` | Kosongkan sesi | — | `{ok}` |
| `GET /files/<id>/<nama>.png` | Citra item (`?download=1` untuk unduhan) | — | PNG |

Jenis serangan: `jpeg {quality 1–100}` · `crop {percent 1–90, position tl/tr/bl/br/cc}` · `crop_rect {x,y,w,h pecahan 0–1}` · `resize {scale 0,1–2}` · `noise {sigma 0–100}`.

### Model data item riwayat

```jsonc
{
  "id": "a1b2c3d4e5f6",            // 12 hex
  "kind": "embed",                 // embed | extract | attack
  "title": "foto.png · haar L2 Δ36",
  "created_at": 1789400000.0,
  "config": {                      // wajib sama saat ekstraksi
    "wavelet": "haar", "level": 2, "delta": 36.0, "key": 2024,
    "wm_type": "image", "wm_size": 32, "n_bits": 1024,
    "width": 512, "height": 512, "redundancy": 16
  },
  "metrics": { "psnr": 40.29, "ssim": 0.9573, "ber": 0.0, "bit_errors": 0, "n_bits": 1024 },
  "extracted": { "type": "image" },
  "files": ["cover", "diff", "thumb", "watermarked", "wm_extracted", "wm_original"],
  "urls": { "cover": "/api/files/<id>/cover.png?sid=..." },   // ditambahkan saat respons
  "notes": ["..."]
}
```
Bit watermark asli disimpan server (`bits`) tetapi **tidak dikirim** ke klien kecuali sebagai `wm_text` / `wm_binary` untuk jenis yang relevan.

---

## 10. Keamanan dan Batasan Operasional

| Risiko | Mitigasi yang diterapkan |
|---|---|
| Path traversal lewat nama file/sesi | `SID`, `item id`, dan nama berkas divalidasi regex ketat sebelum menyentuh sistem berkas (diuji di `test_path_traversal_and_isolation`) |
| Akses silang antar sesi | Semua operasi dibatasi ke folder `storage/<sid>/`; item sesi lain mengembalikan 404 (diuji) |
| Unggahan besar / bukan citra | `MAX_CONTENT_LENGTH` 16 MB; decode dengan OpenCV, gagal → 400; sisi terpanjang dipaksa ≤ 1024 px |
| XSS | UI membangun DOM dengan `textContent`/`createTextNode`; `innerHTML` hanya untuk string ikon statis |
| Beban CPU | Batas dimensi, batas rantai serangan (≤ 6), benchmark tetap 13 langkah |
| Penyimpanan membengkak | Maksimal 100 item per sesi (yang terlama otomatis dihapus) |

**Penting:** ID sesi bukan autentikasi. Siapa pun yang tahu ID sesi dapat melihat riwayatnya. Aplikasi dirancang untuk penggunaan lokal/demo (default hanya mendengarkan `127.0.0.1`). Jangan diekspos ke internet tanpa lapisan autentikasi dan reverse proxy.

---

## 11. Konfigurasi

Lewat environment variable (nilai bawaan di `config.py`):

| Variabel | Bawaan | Arti |
|---|---|---|
| `WM_HOST` | `127.0.0.1` | Alamat dengar. `0.0.0.0` agar dapat diakses dari perangkat lain di jaringan (pahami risiko di bagian 10) |
| `WM_PORT` | `5000` | Port |
| `WM_DEBUG` | `0` | `1` untuk auto-reload saat pengembangan |
| `WM_STORAGE_DIR` | `./storage` | Lokasi data sesi |

Batas lain (`MAX_SIDE`, `MIN_SIDE`, `MAX_HISTORY`, `MAX_CONTENT_LENGTH`) ada di `config.py`.

Contoh: `WM_PORT=8080 python app.py` (Linux/macOS) atau `set WM_PORT=8080 && python app.py` (Windows cmd).

---

## 12. Instalasi dan Cara Menjalankan

### 12.1 Prasyarat
Python 3.8+ dan `pip`. Tidak perlu Node.js maupun basis data.

### 12.2 Dashboard web
```bash
cd invisible-watermarking-dwt

# Opsi A — satu langkah
bash run.sh            # Linux/macOS
run.bat                # Windows (klik dua kali)

# Opsi B — manual
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Buka **http://127.0.0.1:5000**.

Alur demo yang disarankan (±3 menit): *Penyisipan* (unggah foto, biarkan logo bawaan, Δ=36) → *Uji ketahanan* → centang JPEG Q=30 lalu **Terapkan serangan** → **Uji semua serangan otomatis** → *Riwayat* → **Sisipkan ulang** dengan Δ lebih besar dan bandingkan hasilnya.

### 12.3 CLI batch (untuk tabel laporan)
```bash
python main.py
```
Membaca `dataset/original/*` dan `dataset/watermark/*` (bila kosong, sampel dibuat otomatis), lalu menulis `results/hasil_uji.csv`, `robustness_ber.csv`, `grafik_ber.png`, `panel_visual.png`.

### 12.4 Pengujian
```bash
python -m unittest discover -s tests -v      # 14 test, ±3 detik
pip install playwright && playwright install chromium
python tests/e2e_playwright.py               # opsional; server harus sedang berjalan
```

### 12.5 Produksi / berbagi di jaringan (rekomendasi, belum diuji dalam proyek ini)
Server bawaan Flask hanya untuk pengembangan. Untuk penggunaan bersama gunakan WSGI server, misalnya `pip install waitress` lalu `waitress-serve --listen=127.0.0.1:8000 app:app`, di belakang reverse proxy dengan autentikasi.

---

## 13. Hasil Pengujian

Konfigurasi: Haar, level 2, Δ = 36, logo 32×32, citra 512×512 (`astronaut`, `chelsea`, `coffee` dari scikit-image). Dihasilkan `python main.py`.

**Imperceptibility (tanpa serangan)**

| Citra | PSNR (dB) | SSIM | BER |
|---|---|---|---|
| astronaut | 40,29 | 0,9573 | 0% |
| chelsea | 40,04 | 0,9564 | 0% |
| coffee | 40,05 | 0,9548 | 0% |

**Robustness — BER (%)**

| Serangan | astronaut | chelsea | coffee | Rata-rata |
|---|---|---|---|---|
| JPEG Q=90 | 0,00 | 0,00 | 0,00 | 0,00 |
| JPEG Q=70 | 0,00 | 0,00 | 0,00 | 0,00 |
| JPEG Q=50 | 0,59 | 0,00 | 0,00 | 0,20 |
| JPEG Q=30 | 17,38 | 4,30 | 5,66 | 9,11 |
| Crop 10% | 0,10 | 0,00 | 0,00 | 0,03 |
| Crop 25% | 1,17 | 1,17 | 1,17 | 1,17 |
| Crop 50% | 19,63 | 19,73 | 19,73 | 19,69 |
| Resize 0,5× | 4,30 | 0,10 | 0,29 | 1,56 |
| Resize 0,75× | 0,88 | 0,00 | 0,00 | 0,29 |

Uji via dashboard pada `astronaut` (uji otomatis): derau Gaussian σ=5 → 0,00%; σ=10 → 0,29%; σ=20 → 30,47%; JPEG Q=10 → 33,98%.

**Pengaruh Δ** (rata-rata 3 citra): Δ=28 → SSIM 0,970, BER JPEG Q=30 ≈ 17,7%; Δ=32 → SSIM 0,963, ≈ 12,0%; **Δ=36 → SSIM 0,956, ≈ 9,1%**; Δ=40 → SSIM 0,946 (di bawah target 0,95) meski BER JPEG Q=30 turun ke ≈ 4,9%. Δ=36 dipilih sebagai bawaan karena memenuhi kedua target visual dengan ketahanan terbaik.

**Verifikasi sistem:** 14/14 test lolos; alur E2E browser (beranda → sisip → serang → uji otomatis → ekstrak → riwayat → dialog → tampilan mobile 390 px) berjalan tanpa error konsol maupun respons HTTP 4xx/5xx.

---

## 14. Panduan Memilih Parameter

| Tujuan | Saran |
|---|---|
| Tahan JPEG kuat | Naikkan Δ (40–50) dan pakai level 2; kecilkan payload agar redundansi naik |
| Kualitas visual setinggi mungkin | Turunkan Δ (24–30); periksa PSNR/SSIM di panel evaluasi |
| Tahan crop besar | Perkecil payload (teks 256 bit jauh lebih tahan daripada logo 1024 bit karena redundansinya 4× lipat) |
| Eksperimen level 1 | Redundansi dan MSE ikut berubah (lebih banyak koefisien termodifikasi); turunkan Δ (≈ 20–24) agar PSNR tetap > 35 dB |
| Demo "watermark tak terbaca" | Ekstrak dengan kunci berbeda → BER ≈ 50% |

---

## 15. Keputusan Desain (ringkas)

1. **QIM + redundansi, bukan penambahan aditif.** Memungkinkan ekstraksi blind dan mudah dianalisis trade-off Δ-nya.
2. **Implementasi Haar sendiri di NumPy.** Haar selalu tersedia tanpa dependensi tambahan dan sebagai rujukan pembuktian PyWavelets; wavelet lain memakai PyWavelets.
3. **`mode="periodization"`.** Menjaga ukuran sub-band tepat dan transformasi ortogonal, sehingga analisis MSE koefisien = MSE piksel berlaku.
4. **Riwayat berbasis berkas, bukan database.** Nol konfigurasi, mudah dilihat/dibersihkan manual, cukup untuk skala demo.
5. **ID sesi di localStorage, bukan login.** Memenuhi kebutuhan "riwayat selama sesi" tanpa kompleksitas akun.
6. **Citra dipotong ke kelipatan 8 dan dibatasi 1024 px.** Menjamin DWT dua level valid dan waktu respons wajar.
7. **Crop = area dihitamkan, ukuran citra tetap.** Mensimulasikan penghapusan area tanpa menggeser koordinat (ekstraksi blind tidak menangani pergeseran).
8. **Satu skrip JS tanpa framework.** Mudah dibaca dan dijelaskan; tidak ada langkah build.

---

## 16. Keterbatasan yang Diketahui

- **Db4 belum diuji end-to-end di lingkungan pengembangan.** Lingkungan tempat proyek ini dirakit tidak memiliki PyWavelets, sehingga jalur Haar/Db1 teruji penuh, sedangkan Db4 hanya tersambung lewat API `pywt.dwt2/idwt2` (mode `periodization`). Setelah `pip install -r requirements.txt`, jalankan sekali penyisipan Db4 dan pastikan BER 0% pada ekstraksi langsung. Jika ada masalah, jalur ini terisolasi di `dwt_watermark.dwt2/idwt2`.
- **Serangan geometris** (rotasi, flip, crop yang menggeser kanvas, perspektif) tidak ditangani; ekstraksi mengandalkan posisi koefisien yang tetap. Resize hanya didukung bila citra dikembalikan ke ukuran semula (atau ukuran referensi diberikan saat ekstraksi manual).
- **Ekstraksi manual** menuntut ukuran citra sama dengan saat penyisipan; bila tidak, BER ≈ 50%. Gunakan kolom Lebar/Tinggi referensi atau ekstraksi dari riwayat.
- **JPEG Q ≤ 30 dan crop ≥ 50%** menaikkan BER signifikan (bagian 13). Tidak ada koreksi kesalahan (ECC); menambahkan kode Hamming/BCH adalah peningkatan paling berdampak.
- **Teks dibatasi 32 byte;** karakter non-ASCII memakan lebih dari 1 byte.
- **Konkurensi:** kunci `RLock` hanya melindungi satu proses. Jangan menjalankan beberapa worker yang berbagi `storage/` tanpa mengganti mekanisme penyimpanan.
- **Tidak ada autentikasi** (bagian 10) dan tidak ada pembersihan riwayat berdasarkan umur; hapus `storage/` secara berkala bila perlu.
- Hasil di bagian 13 memakai tiga citra sampel; untuk laporan akhir, ulangi dengan dataset sendiri (≥ 10 citra beragam) agar kesimpulan statistik lebih kuat.

---

## 17. Roadmap Saran

1. Koreksi kesalahan (Hamming/BCH/repetisi berlapis) agar BER mendekati 0% pada JPEG Q=30.
2. Sinkronisasi geometris (template/pola rujukan) untuk rotasi dan crop yang menggeser kanvas.
3. Watermark adaptif (Δ per blok berdasarkan tekstur) untuk meningkatkan SSIM pada Δ yang sama.
4. Perbandingan metode (DWT vs DCT vs DWT-SVD) di dashboard.
5. Autentikasi, `Dockerfile`, dan deployment dengan WSGI server.
6. Ekspor laporan otomatis (PDF/Word) dari halaman riwayat.

---

## 18. Pemecahan Masalah

| Gejala | Penyebab / solusi |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Belum `pip install -r requirements.txt`, atau virtual env belum aktif |
| Pilihan **Db4** abu-abu, catatan "Mode Haar" di sidebar | PyWavelets belum terpasang: `pip install PyWavelets` lalu jalankan ulang |
| Halaman kosong / "Server tidak merespons" | Server tidak berjalan atau port berbeda; periksa terminal dan `WM_PORT` |
| Browser menolak `localhost` tetapi `127.0.0.1` jalan | Server hanya mendengarkan IPv4; buka `http://127.0.0.1:5000` |
| `Address already in use` | Port 5000 dipakai (mis. AirPlay di macOS): `WM_PORT=5001 python app.py` |
| Error 400 "Citra terlalu kecil…" | Sisi terpendek < 128 px, atau payload terlalu besar untuk citra; kecilkan watermark |
| BER ≈ 50% pada ekstraksi manual | Kunci, Δ, level, wavelet, jenis/ukuran watermark, atau ukuran citra berbeda dari saat penyisipan |
| Font tampak berbeda saat offline | Google Fonts tidak termuat; tampilan memakai font sistem, fungsi tidak terpengaruh |
| Ingin mengosongkan semua data | Hapus isi `storage/` (kecuali `.gitkeep`) atau gunakan **Kosongkan riwayat** |

---

## 19. Glosarium

- **DWT** — transformasi yang memecah citra menjadi sub-band frekuensi: LL (gambaran umum) dan tiga sub-band detail (tepi horizontal, vertikal, diagonal).
- **Wavelet Haar / Db1 / Db4** — keluarga filter DWT; Haar sama dengan Db1, Db4 memiliki filter lebih panjang (8 tap pada PyWavelets).
- **QIM** — Quantization Index Modulation: bit ditanam dengan memilih salah satu dari dua kisi kuantisasi.
- **Δ (Alpha)** — jarak kisi QIM; menentukan kekuatan penyisipan.
- **Blind extraction** — ekstraksi tanpa citra asli.
- **Imperceptibility / Robustness** — ketidakterlihatan perubahan / ketahanan terhadap serangan.
- **PSNR / SSIM / BER** — lihat bagian 7.
- **Soft voting** — penggabungan bukti dari semua salinan bit dengan bobot keyakinan.
