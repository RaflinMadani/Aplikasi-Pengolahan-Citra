"""Konversi payload watermark (logo / teks / biner) <-> vektor bit."""
import numpy as np
import cv2

TEXT_BYTES = 32
TEXT_BITS = TEXT_BYTES * 8          # 256 bit
MIN_BINARY_BITS = 8
MAX_BINARY_BITS = 2048


def image_to_bits(img, size=32):
    """Citra/logo -> vektor bit 0/1 (size*size), binarisasi Otsu."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary.astype(np.uint8).flatten()


def bits_to_image(bits, size=32, scale=8):
    """Vektor bit -> citra uint8 (255 untuk bit 1), diperbesar nearest-neighbour."""
    img = (np.asarray(bits, dtype=np.uint8).reshape(size, size) * 255).astype(np.uint8)
    if scale > 1:
        img = cv2.resize(img, (size * scale, size * scale), interpolation=cv2.INTER_NEAREST)
    return img


def default_logo_bits(size=32):
    """Logo bawaan 'DWT' bila pengguna tidak mengunggah watermark."""
    logo = np.zeros((128, 128), np.uint8)
    cv2.rectangle(logo, (8, 8), (119, 119), 255, 6)
    cv2.putText(logo, "DWT", (14, 78), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 255, 4)
    cv2.circle(logo, (64, 100), 10, 255, -1)
    return image_to_bits(logo, size)


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
