"""Simulasi serangan citra: JPEG, cropping, resizing, derau Gaussian."""
import numpy as np
import cv2


def jpeg_compress(img, quality):
    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    flag = cv2.IMREAD_GRAYSCALE if img.ndim == 2 else cv2.IMREAD_COLOR
    return cv2.imdecode(enc, flag)


def crop(img, percent, position="br"):
    """Hitamkan blok seluas `percent`% citra pada salah satu sudut / tengah."""
    h, w = img.shape[:2]
    f = np.sqrt(percent / 100.0)
    ch, cw = int(h * f), int(w * f)
    y0 = {"t": 0, "b": h - ch, "c": (h - ch) // 2}[position[0]]
    x0 = {"l": 0, "r": w - cw, "c": (w - cw) // 2}[position[1]]
    out = img.copy()
    out[y0:y0 + ch, x0:x0 + cw] = 0
    return out


def crop_rect(img, x, y, w, h):
    """Hitamkan persegi panjang (x, y, w, h dalam pecahan 0..1 dari ukuran citra)."""
    H, W = img.shape[:2]
    x0, y0 = int(round(max(0.0, x) * W)), int(round(max(0.0, y) * H))
    x1, y1 = int(round(min(1.0, x + w) * W)), int(round(min(1.0, y + h) * H))
    out = img.copy()
    out[y0:y1, x0:x1] = 0
    return out


def resize_attack(img, scale=0.5):
    """Downscale lalu upscale kembali ke ukuran semula."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(8, int(w * scale)), max(8, int(h * scale))), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def gaussian_noise(img, sigma, seed=0):
    rng = np.random.default_rng(seed)
    noisy = img.astype(np.float64) + rng.normal(0, sigma, img.shape)
    return np.clip(np.round(noisy), 0, 255).astype(np.uint8)


def _num(step, key, lo, hi):
    try:
        v = float(step[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Parameter '{key}' pada serangan '{step.get('type')}' tidak valid.")
    if not lo <= v <= hi:
        raise ValueError(f"Parameter '{key}' harus di antara {lo} dan {hi}.")
    return v


def apply_step(img, step):
    t = step.get("type")
    if t == "jpeg":
        return jpeg_compress(img, int(_num(step, "quality", 1, 100)))
    if t == "crop":
        pos = step.get("position", "br")
        if pos not in ("tl", "tr", "bl", "br", "cc"):
            raise ValueError("Posisi crop tidak dikenal.")
        return crop(img, _num(step, "percent", 1, 90), pos)
    if t == "crop_rect":
        x, y = _num(step, "x", 0, 1), _num(step, "y", 0, 1)
        w, h = _num(step, "w", 0, 1), _num(step, "h", 0, 1)
        return crop_rect(img, x, y, w, h)
    if t == "resize":
        return resize_attack(img, _num(step, "scale", 0.1, 2.0))
    if t == "noise":
        return gaussian_noise(img, _num(step, "sigma", 0, 100))
    raise ValueError(f"Jenis serangan '{t}' tidak dikenal.")


def apply_chain(img, steps):
    for s in steps:
        img = apply_step(img, s)
    return img


def describe(step):
    t = step["type"]
    if t == "jpeg":
        return f"JPEG Q={int(step['quality'])}"
    if t == "crop":
        return f"Crop {step['percent']:g}%"
    if t == "crop_rect":
        return f"Crop area {step['w'] * step['h'] * 100:.0f}%"
    if t == "resize":
        return f"Resize {step['scale']:g}×"
    return f"Derau σ={step['sigma']:g}"
