import streamlit as st
import numpy as np
from PIL import Image
import cv2
import matplotlib.pyplot as plt
import io

# Konfigurasi halaman
st.set_page_config(
    page_title="Aplikasi Pengolahan Citra Digital",
    page_icon="🖼️",
    layout="wide"
)

# Fungsi-fungsi pengolahan citra
def biner(image, threshold):
    """Membuat citra biner dari citra berdasarkan nilai ambang (threshold)"""
    M, N = image.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    for i in range(M):
        for j in range(N):
            if image[i, j] < threshold:
                result[i, j] = 0
            else:
                result[i, j] = 255
    
    return result

def negatif(image):
    """Membuat citra negatif dari citra"""
    M, N = image.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    for i in range(M):
        for j in range(N):
            result[i, j] = 255 - image[i, j]
    
    return result

def image_brightening(image, b):
    """Pencerahan citra dengan menjumlahkan setiap pixel dengan skalar b"""
    M, N = image.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    for i in range(M):
        for j in range(N):
            temp = int(image[i, j]) + b
            
            # Clipping
            if temp < 0:
                result[i, j] = 0
            elif temp > 255:
                result[i, j] = 255
            else:
                result[i, j] = temp
    
    return result

def addition(imageA, imageB):
    """Menjumlahkan dua buah citra A dan B menjadi citra baru"""
    M, N = imageA.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    for i in range(M):
        for j in range(N):
            temp = int(imageA[i, j]) + int(imageB[i, j])
            if temp > 255:
                result[i, j] = 255
            else:
                result[i, j] = temp
    
    return result

def multiplication(imageA, imageB):
    """Mengalikan citra A dengan citra B menjadi citra C"""
    M, N = imageA.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    for i in range(M):
        for j in range(N):
            temp = int(imageA[i, j]) * int(imageB[i, j])
            
            # Clipping
            if temp < 0:
                result[i, j] = 0
            elif temp > 255:
                result[i, j] = 255
            else:
                result[i, j] = temp
    
    return result

def konvolusi(image, mask):
    """Mengkonvolusi citra dengan mask 3x3"""
    M, N = image.shape
    result = np.zeros((M, N), dtype=np.float32)
    
    for i in range(1, M-2):
        for j in range(1, N-2):
            result[i, j] = (
                image[i-1, j-1] * mask[0, 0] +
                image[i-1, j] * mask[0, 1] +
                image[i-1, j+1] * mask[0, 2] +
                image[i, j-1] * mask[1, 0] +
                image[i, j] * mask[1, 1] +
                image[i, j+1] * mask[1, 2] +
                image[i+1, j-1] * mask[2, 0] +
                image[i+1, j] * mask[2, 1] +
                image[i+1, j+1] * mask[2, 2]
            )
    
    # Normalisasi ke range 0-255
    result = np.clip(result, 0, 255)
    return result.astype(np.uint8)

def histogram(image):
    """Menghitung histogram citra"""
    hist = np.zeros(256)
    M, N = image.shape
    total_pixels = M * N
    
    for i in range(M):
        for j in range(N):
            hist[image[i, j]] += 1
    
    # Normalisasi histogram
    hist = hist / total_pixels
    return hist

def perataan_histogram(image):
    """Mengubah citra dengan melakukan perataan histogram (histogram equalization)"""
    M, N = image.shape
    result = np.zeros((M, N), dtype=np.uint8)
    
    # Hitung histogram citra
    hist = histogram(image)
    
    # Hitung histogram hasil perataan
    hist_eq = np.zeros(256, dtype=np.uint8)
    for i in range(256):
        sum_val = 0.0
        for j in range(i + 1):
            sum_val += hist[j]
        hist_eq[i] = int(np.floor(255 * sum_val))
    
    # Update citra sesuai histogram hasil perataan
    for i in range(M):
        for j in range(N):
            result[i, j] = hist_eq[image[i, j]]
    
    return result

def plot_histogram(image):
    """Membuat plot histogram"""
    fig, ax = plt.subplots(figsize=(6, 4))
    hist = cv2.calcHist([image], [0], None, [256], [0, 256])
    ax.plot(hist, color='black')
    ax.set_xlim((0, 256))
    ax.set_xlabel('Intensitas Pixel')
    ax.set_ylabel('Frekuensi')
    ax.set_title('Histogram')
    ax.grid(True, alpha=0.3)
    return fig

def convert_to_grayscale(image):
    """Konversi gambar ke grayscale"""
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return image

# Sidebar untuk pilihan fitur
st.sidebar.title("🎨 Fitur Pengolahan Citra")
st.sidebar.markdown("---")

feature = st.sidebar.selectbox(
    "Pilih Fitur:",
    [
        "Original",
        "Thresholding (Binerisasi)",
        "Citra Negatif",
        "Image Brightening",
        "Convolution (Konvolusi)",
        "Histogram Equalization"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("📝 Pilih fitur di atas untuk mengolah gambar yang Anda upload.")

# Header utama
st.title("🖼️ Aplikasi Pengolahan Citra Digital")
st.subheader("Kelompok 3 :")
st.markdown("Muhammad Ruhul Jadid (123230046)")
st.markdown("Ardhika Rizki Akbar Pratama (123230057)")
st.markdown("Brian Zahran Putra (123230195) ")
st.markdown("Ikhsan Fillah Hidayat (123230219)")
st.markdown("---")

# Inisialisasi session state untuk menyimpan captured image
if 'captured_image' not in st.session_state:
    st.session_state.captured_image = None
if 'camera_active' not in st.session_state:
    st.session_state.camera_active = False

# Pilihan sumber gambar
input_source = st.radio(
    "📷 Pilih Sumber Input:",
    ["Upload Gambar", "Capture Kamera", "Video Live"],
    horizontal=True
)

st.markdown("---")

uploaded_file = None
camera_image = None

if input_source == "Upload Gambar":
    # Reset captured image jika pindah ke mode upload
    st.session_state.captured_image = None
    
    # Upload gambar
    uploaded_file = st.file_uploader(
        "📁 Upload Gambar (JPG, JPEG, PNG)",
        type=["jpg", "jpeg", "png"],
        help="Drag and drop gambar atau klik untuk browse"
    )

elif input_source == "Capture Kamera":
    st.subheader("📸 Capture dari Kamera")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🎥 Capture Gambar", type="primary"):
            # Inisialisasi kamera
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                st.error("❌ Tidak dapat mengakses kamera. Pastikan kamera Anda terhubung dan tidak digunakan aplikasi lain.")
            else:
                # Tunggu sebentar agar kamera siap
                import time
                time.sleep(0.5)
                
                # Ambil frame dari kamera
                ret, frame = cap.read()
                
                if ret:
                    # Konversi BGR ke RGB untuk display
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    st.session_state.captured_image = frame_rgb
                    st.success("✅ Gambar berhasil di-capture!")
                else:
                    st.error("❌ Gagal membaca frame dari kamera.")
                
                # Release kamera
                cap.release()
    
    with col_btn2:
        if st.button("🗑️ Hapus Capture"):
            st.session_state.captured_image = None
            st.info("Capture dihapus. Silakan capture gambar baru.")
    
    # Tampilkan preview jika ada captured image
    if st.session_state.captured_image is not None:
        st.image(st.session_state.captured_image, caption="🖼️ Gambar yang Di-capture", use_container_width=True)
        camera_image = st.session_state.captured_image

elif input_source == "Video Live":
    st.subheader("🎥 Video Live dari Kamera")
    
    # Inisialisasi session state untuk video
    if 'video_running' not in st.session_state:
        st.session_state.video_running = False
    
    # Tambahkan parameter controls di sidebar untuk video live
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parameter untuk Video Live")
    
    if feature == "Thresholding (Binerisasi)":
        threshold_value = st.sidebar.slider("Nilai Threshold (0-255):", 0, 255, 127, key="live_threshold")
        st.session_state.threshold_value = threshold_value
    
    elif feature == "Image Brightening":
        brightness_value = st.sidebar.slider("Nilai Brightness (-100 sampai 100):", -100, 100, 50, key="live_brightness")
        st.session_state.brightness_value = brightness_value
    
    elif feature == "Convolution (Konvolusi)":
        mask_type = st.sidebar.selectbox(
            "Pilih Jenis Filter/Mask:",
            [
                "Smoothing (Average)",
                "Gaussian Blur",
                "Sharpening",
                "Edge Detection (Sobel X)",
                "Edge Detection (Sobel Y)",
                "Edge Detection (Laplacian)"
            ],
            key="live_mask"
        )
        st.session_state.mask_type = mask_type
    
    col_video1, col_video2 = st.columns(2)
    
    with col_video1:
        start_video = st.button("▶️ Mulai Video Live", type="primary")
        
    with col_video2:
        stop_video = st.button("⏸️ Stop Video")
    
    if start_video:
        st.session_state.video_running = True
    
    if stop_video:
        st.session_state.video_running = False
    
    if st.session_state.video_running:
        st.info("🎥 Video live sedang berjalan. Klik 'Stop Video' untuk menghentikan.")
        
        # Placeholder untuk video dan histogram
        video_placeholder = st.empty()
        histogram_placeholder = st.empty()
        
        # Inisialisasi kamera
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            st.error("❌ Tidak dapat mengakses kamera.")
            st.session_state.video_running = False
        else:
            # Frame counter untuk optimize refresh rate
            frame_count = 0
            
            while st.session_state.video_running:
                ret, frame = cap.read()
                
                if not ret:
                    st.error("❌ Gagal membaca frame dari kamera.")
                    break
                
                # Konversi BGR ke RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Konversi ke grayscale untuk processing
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Apply selected feature
                if feature == "Thresholding (Binerisasi)":
                    # Get threshold value from session state or use default
                    threshold_val = st.session_state.get('threshold_value', 127)
                    processed_frame = biner(gray_frame, threshold_val)
                    # Convert back to RGB for display
                    processed_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2RGB)
                
                elif feature == "Citra Negatif":
                    processed_frame = negatif(gray_frame)
                    processed_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2RGB)
                
                elif feature == "Image Brightening":
                    brightness_val = st.session_state.get('brightness_value', 50)
                    processed_frame = image_brightening(gray_frame, brightness_val)
                    processed_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2RGB)
                
                elif feature == "Convolution (Konvolusi)":
                    mask_type = st.session_state.get('mask_type', 'Smoothing (Average)')
                    masks = {
                        "Smoothing (Average)": np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]]) / 9,
                        "Gaussian Blur": np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]]) / 16,
                        "Sharpening": np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]),
                        "Edge Detection (Sobel X)": np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]),
                        "Edge Detection (Sobel Y)": np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]),
                        "Edge Detection (Laplacian)": np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
                    }
                    selected_mask = masks[mask_type]
                    processed_frame = konvolusi(gray_frame, selected_mask)
                    processed_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2RGB)
                
                elif feature == "Histogram Equalization":
                    processed_frame = perataan_histogram(gray_frame)
                    processed_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2RGB)
                
                else:  # Original
                    processed_frame = gray_frame
                    processed_rgb = frame_rgb.copy()
                
                # Display video side by side
                with video_placeholder.container():
                    col_display1, col_display2 = st.columns(2)
                    
                    with col_display1:
                        st.image(frame_rgb, caption="📹 Video Asli", use_container_width=True)
                    
                    with col_display2:
                        st.image(processed_rgb, caption=f"🎨 Hasil: {feature}", use_container_width=True)
                
                # Display histograms side by side (update setiap beberapa frame untuk performa)
                if frame_count % 5 == 0:  # Update histogram setiap 5 frame
                    with histogram_placeholder.container():
                        st.markdown("---")
                        st.subheader("📊 Histogram Real-Time")
                        col_hist1, col_hist2 = st.columns(2)
                        
                        with col_hist1:
                            st.markdown("**📈 Histogram Input**")
                            fig_input = plot_histogram(gray_frame)
                            st.pyplot(fig_input)
                            plt.close(fig_input)
                        
                        with col_hist2:
                            st.markdown("**📈 Histogram Output**")
                            if feature == "Original":
                                fig_output = plot_histogram(gray_frame)
                            else:
                                fig_output = plot_histogram(processed_frame)
                            st.pyplot(fig_output)
                            plt.close(fig_output)
                
                frame_count += 1
                
                # Refresh rate control - update setiap beberapa frame
                if frame_count % 3 == 0:  # Update every 3 frames untuk performa lebih baik
                    import time
                    time.sleep(0.03)
            
            cap.release()
            st.success("✅ Video live dihentikan.")
    else:
        st.info("👆 Klik tombol 'Mulai Video Live' untuk memulai streaming dari kamera.")

if uploaded_file is not None or camera_image is not None:
    # Baca gambar
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        image_array = np.array(image)
    else:
        # Gunakan gambar dari kamera
        image_array = camera_image
    
    # Simpan gambar asli untuk ditampilkan di input
    rgb_image = image_array.copy()
    gray_image = convert_to_grayscale(image_array)
    # Variabel untuk gambar output
    output_image = gray_image.copy()

    # Parameter untuk fitur yang membutuhkan input
    st.markdown("---")

    if feature == "Thresholding (Binerisasi)":
        st.subheader("⚙️ Parameter Thresholding")
        threshold_value = st.slider("Nilai Threshold (0-255):", 0, 255, 127)
        st.session_state.threshold_value = threshold_value  # Simpan ke session state
        output_image = biner(gray_image, threshold_value)

    elif feature == "Citra Negatif":
        output_image = negatif(gray_image)

    elif feature == "Image Brightening":
        st.subheader("⚙️ Parameter Brightening")
        brightness_value = st.slider("Nilai Brightness (-100 sampai 100):", -100, 100, 50)
        st.session_state.brightness_value = brightness_value  # Simpan ke session state
        output_image = image_brightening(gray_image, brightness_value)


    elif feature == "Convolution (Konvolusi)":
        st.subheader("⚙️ Parameter Konvolusi")
        mask_type = st.selectbox(
            "Pilih Jenis Filter/Mask:",
            [
                "Smoothing (Average)",
                "Gaussian Blur",
                "Sharpening",
                "Edge Detection (Sobel X)",
                "Edge Detection (Sobel Y)",
                "Edge Detection (Laplacian)"
            ]
        )
        st.session_state.mask_type = mask_type  # Simpan ke session state
        masks = {
            "Smoothing (Average)": np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]]) / 9,
            "Gaussian Blur": np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]]) / 16,
            "Sharpening": np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]),
            "Edge Detection (Sobel X)": np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]),
            "Edge Detection (Sobel Y)": np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]]),
            "Edge Detection (Laplacian)": np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]])
        }
        selected_mask = masks[mask_type]
        output_image = konvolusi(gray_image, selected_mask)

    elif feature == "Histogram Equalization":
        output_image = perataan_histogram(gray_image)

    elif feature == "Original":
        output_image = rgb_image.copy()

    # Tampilkan hasil dalam dua kolom: input dan output
    st.markdown("---")
    st.header("📊 Hasil Pengolahan")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🖼️ Gambar Input")
        st.image(rgb_image, width=200, clamp=True)
        st.subheader("📈 Histogram Input")
        fig_input = plot_histogram(gray_image)
        st.pyplot(fig_input)
        plt.close()
    with col2:
        st.subheader("🖼️ Gambar Output")
        if feature == "Original":
            st.image(output_image, width=200, clamp=True)
            st.subheader("📈 Histogram Output")
            fig_output = plot_histogram(gray_image)
            st.pyplot(fig_output)
            plt.close()
        else:
            st.image(output_image, width=200, clamp=True)
            st.subheader("📈 Histogram Output")
            fig_output = plot_histogram(output_image)
            st.pyplot(fig_output)
            plt.close()
    # Download hasil
    st.markdown("---")
    st.subheader("💾 Download Hasil")
    output_pil = Image.fromarray(output_image)
    buf = io.BytesIO()
    output_pil.save(buf, format="PNG")
    byte_im = buf.getvalue()
    st.download_button(
        label="📥 Download Gambar Output",
        data=byte_im,
        file_name=f"output_{feature.lower().replace(' ', '_')}.png",
        mime="image/png"
    )
    st.markdown("""
    ### 📋 Fitur yang Tersedia:
    1. **Thresholding (Binerisasi)** - Membuat citra biner berdasarkan nilai ambang
    2. **Citra Negatif** - Membalik intensitas pixel
    3. **Image Brightening** - Mengatur kecerahan gambar
    4. **Convolution** - Konvolusi dengan berbagai filter (smoothing, sharpening, edge detection)
    5. **Histogram Equalization** - Perataan histogram untuk meningkatkan kontras
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "© 2025 Aplikasi Pengolahan Citra Digital | Dibuat dengan Streamlit"
    "</div>",
    unsafe_allow_html=True
)
