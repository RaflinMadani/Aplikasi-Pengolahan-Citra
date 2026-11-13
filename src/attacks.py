"""Simulasi serangan citra: JPEG, cropping, resizing."""
import numpy as np
import cv2


def jpeg_compress(img, quality):
    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    flag = cv2.IMREAD_GRAYSCALE if img.ndim == 2 else cv2.IMREAD_COLOR
    return cv2.imdecode(enc, flag)


def crop(img, percent):
    """Hapus (hitamkan) blok di sudut kanan-bawah seluas `percent`% citra."""
    h, w = img.shape[:2]
    f = np.sqrt(percent / 100.0)
    ch, cw = int(h * f), int(w * f)
    out = img.copy()
    out[h - ch:, w - cw:] = 0
    return out


def resize_attack(img, scale=0.5):
    """Downscale lalu upscale kembali ke ukuran semula."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
