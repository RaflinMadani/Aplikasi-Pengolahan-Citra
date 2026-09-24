# Pengolahan-Citra

Aplikasi Pengolahan Citra Digital menggunakan Streamlit dan OpenCV.

## Fitur

- **Thresholding (Binerisasi)** - Membuat citra biner berdasarkan nilai ambang
- **Citra Negatif** - Membalik intensitas pixel
- **Image Brightening** - Mengatur kecerahan gambar
- **Convolution** - Konvolusi dengan berbagai filter (smoothing, sharpening, edge detection)
- **Histogram Equalization** - Perataan histogram untuk meningkatkan kontras

## Input Gambar

Aplikasi mendukung 3 metode input:
1. **Upload Gambar** - Upload file gambar (JPG, JPEG, PNG)
2. **Capture Kamera** - Capture satu foto dari webcam menggunakan OpenCV
3. **Video Live** - Stream video real-time dari webcam dengan processing langsung

### Mode Video Live
Mode video live memungkinkan Anda untuk:
- 🎥 Melihat preview webcam secara real-time
- 🎨 Menerapkan filter pengolahan citra secara langsung ke setiap frame
- ⚙️ Mengatur parameter (threshold, brightness, filter type) dari sidebar
- 📺 Melihat perbandingan video asli vs hasil processing secara side-by-side

## Cara Menjalankan

1. Install dependencies:
```bash
pip install streamlit opencv-python numpy pillow matplotlib
```

2. Jalankan aplikasi:
```bash
streamlit run ProjectPC.py
```

3. **Pilih mode input:**
   - **Upload Gambar**: Upload file gambar dari komputer
   - **Capture Kamera**: Klik tombol "Capture Gambar" untuk mengambil 1 foto
   - **Video Live**: Klik tombol "Mulai Video Live" untuk streaming real-time

4. **Pilih fitur pengolahan** dari sidebar (Thresholding, Negatif, Brightening, dll.)

5. **Untuk Video Live:**
   - Atur parameter di sidebar (threshold, brightness, atau jenis filter)
   - Parameter akan diterapkan secara real-time ke video stream
   - Klik "Stop Video" untuk menghentikan streaming

6. **Untuk Upload/Capture:**
   - Lihat hasil processing dan histogram
   - Download gambar output yang sudah diproses

## Kelompok 3

- Muhammad Ruhul Jadid (123230046)
- Ardhika Rizki Akbar Pratama (123230057)
- Brian Zahran Putra (123230195)
- Ikhsan Fillah Hidayat (123230219)
