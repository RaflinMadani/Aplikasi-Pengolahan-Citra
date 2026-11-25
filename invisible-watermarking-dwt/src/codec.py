"""Konversi payload watermark (logo B&W / grayscale / teks / biner) <-> vektor bit."""
import numpy as np
import cv2

TEXT_BYTES = 32
TEXT_BITS = TEXT_BYTES * 8          # 256 bit
MIN_BINARY_BITS = 8
MAX_BINARY_BITS = 512 * 512         # 262.144 bit (mendukung watermark hingga 512x512)
MAX_WM_SIZE = 512


def image_to_bits(img, size=32, bit_depth=1):
    """
    Citra/logo -> vektor bit.
      - bit_depth=1: biner hitam-putih (Otsu threshold), total = size * size bit.
      - bit_depth=8: grayscale 256 tingkat keabuan, total = size * size * 8 bit.
    """
    if size < 8 or size > MAX_WM_SIZE:
        raise ValueError(f"Ukuran watermark harus antara 8 dan {MAX_WM_SIZE} piksel.")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)

    if bit_depth == 8:
        return np.unpackbits(gray.astype(np.uint8).flatten())

    _, binary = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary.astype(np.uint8).flatten()


def bits_to_image(bits, size=32, scale=8, bit_depth=1):
    """Vektor bit -> citra uint8, diperbesar nearest-neighbour bila scale > 1."""
    arr = np.asarray(bits, dtype=np.uint8)
    if bit_depth == 8:
        img = np.packbits(arr[: size * size * 8]).reshape(size, size)
    else:
        img = (arr[: size * size].reshape(size, size) * 255).astype(np.uint8)

    if scale > 1:
        img = cv2.resize(img, (size * scale, size * scale), interpolation=cv2.INTER_NEAREST)
    return img


def default_logo_bits(size=32, bit_depth=1):
    """Logo bawaan 'DWT' bila pengguna tidak mengunggah watermark."""
    dim = max(128, size)
    logo = np.zeros((dim, dim), np.uint8)
    thickness = max(4, dim // 20)
    cv2.rectangle(logo, (dim // 16, dim // 16), (dim - dim // 16, dim - dim // 16), 255, thickness)
    font_scale = dim / 80.0
    cv2.putText(
        logo, "DWT", (int(dim * 0.11), int(dim * 0.61)),
        cv2.FONT_HERSHEY_SIMPLEX, font_scale, 255, max(2, dim // 32)
    )
    cv2.circle(logo, (dim // 2, int(dim * 0.78)), max(6, dim // 12), 255, -1)
    return image_to_bits(logo, size, bit_depth=bit_depth)


def text_to_bits(text):
    raw = text.encode("utf-8")
    if not raw:
        raise ValueError("Teks watermark tidak boleh kosong.")
    if len(raw) > TEXT_BYTES:
        raise ValueError(f"Teks terlalu panjang: maksimal {TEXT_BYTES} byte (±{TEXT_BYTES} karakter ASCII).")
    raw = raw.ljust(TEXT_BYTES, b"\x00")
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))


def bits_to_text(bits):
    raw = np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes().rstrip(b"\x00")
    return raw.decode("utf-8", errors="replace")


def binary_string_to_bits(s):
    s = "".join(s.split())
    if not s or set(s) - {"0", "1"}:
        raise ValueError("Watermark biner hanya boleh berisi karakter 0 dan 1.")
    if not (MIN_BINARY_BITS <= len(s) <= MAX_BINARY_BITS):
        raise ValueError(f"Panjang biner harus {MIN_BINARY_BITS}–{MAX_BINARY_BITS} bit.")
    return np.array([int(c) for c in s], dtype=np.uint8)


def bits_to_string(bits):
    return "".join(str(int(b)) for b in bits)