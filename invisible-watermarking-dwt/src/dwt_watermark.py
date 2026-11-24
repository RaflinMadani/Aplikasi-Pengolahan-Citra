"""
Invisible Image Watermarking berbasis DWT + QIM.

Alur:
  Citra -> kanal Y -> DWT level 1/2 -> sub-band detail (HL & LH) pada level terdalam
  -> bit watermark disisipkan dengan Quantization Index Modulation (QIM)
  -> tiap bit diulang (redundansi) pada posisi acak (kunci rahasia)
  -> IDWT -> citra ber-watermark.
Ekstraksi bersifat BLIND (tanpa citra asli) dengan soft-voting.

Wavelet: 'haar'/'db1' (NumPy murni) dan 'db4' (memerlukan PyWavelets).
"""
import numpy as np
import cv2

from .codec import image_to_bits as prepare_watermark, bits_to_image  # noqa: F401  (kompatibilitas)

try:
    import pywt
    HAS_PYWT = True
except ImportError:  # pragma: no cover
    pywt = None
    HAS_PYWT = False


class WaveletUnavailableError(ValueError):
    pass


def available_wavelets():
    return ["haar", "db1", "db4"] if HAS_PYWT else ["haar", "db1"]


def _canonical(wavelet):
    w = (wavelet or "haar").lower()
    return "haar" if w in ("haar", "db1") else w


# ---------------------------------------------------------------- DWT ---
def _haar_dwt2(x):
    a, b = x[0::2, 0::2], x[0::2, 1::2]
    c, d = x[1::2, 0::2], x[1::2, 1::2]
    return (a + b + c + d) / 2.0, ((a + b - c - d) / 2.0, (a - b + c - d) / 2.0, (a - b - c + d) / 2.0)


def _haar_idwt2(coeffs):
    cA, (cH, cV, cD) = coeffs
    h, w = cA.shape
    out = np.zeros((h * 2, w * 2), dtype=np.float64)
    out[0::2, 0::2] = (cA + cH + cV + cD) / 2.0
    out[0::2, 1::2] = (cA + cH - cV - cD) / 2.0
    out[1::2, 0::2] = (cA - cH + cV - cD) / 2.0
    out[1::2, 1::2] = (cA - cH - cV + cD) / 2.0
    return out


def _check(w):
    if w != "haar" and not HAS_PYWT:
        raise WaveletUnavailableError(
            f"Wavelet '{w}' memerlukan PyWavelets. Jalankan: pip install PyWavelets")


def dwt2(x, wavelet="haar"):
    w = _canonical(wavelet)
    _check(w)
    return _haar_dwt2(x) if w == "haar" else pywt.dwt2(x, w, mode="periodization")


def idwt2(c, wavelet="haar"):
    w = _canonical(wavelet)
    _check(w)
    return _haar_idwt2(c) if w == "haar" else pywt.idwt2(c, w, mode="periodization")


def _decompose(y, wavelet, level):
    approx, details = y, []
    for _ in range(level):
        approx, d = dwt2(approx, wavelet)
        details.append(d)
    return approx, details


def _reconstruct(approx, details, wavelet):
    for d in reversed(details):
        approx = idwt2((approx, d), wavelet)
    return approx


# ---------------------------------------------------------------- QIM ---
def _qim_embed(coef, bits, delta):
    off = bits * (delta / 2.0)
    return delta * np.round((coef - off) / delta) + off


def _qim_score(coef, delta):
    """Skor soft: >0 condong bit 1, <0 condong bit 0."""
    q0 = delta * np.round(coef / delta)
    q1 = delta * np.round((coef - delta / 2.0) / delta) + delta / 2.0
    return np.abs(coef - q0) - np.abs(coef - q1)


def _positions(n_total, n_use, key):
    return np.random.RandomState(key).permutation(n_total)[:n_use]


def _luma(img):
    if img.ndim == 2:
        return None, img.astype(np.float64)
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    return ycc, ycc[:, :, 0].astype(np.float64)


def capacity(shape, level, n_bits):
    """Jumlah pengulangan (redundansi) per bit yang tersedia."""
    h, w = shape[:2]
    total = 2 * (h // 2 ** level) * (w // 2 ** level)
    return total // n_bits // 2


# ------------------------------------------------------------- publik ---
def embed(host, bits, delta=36.0, key=2024, wavelet="haar", level=2):
    h, w = host.shape[:2]
    if h % (2 ** level) or w % (2 ** level):
        raise ValueError(f"Ukuran citra harus kelipatan {2 ** level} untuk level {level}.")
    if capacity(host.shape, level, len(bits)) < 1:
        raise ValueError("Citra terlalu kecil untuk jumlah bit watermark ini.")

    ycc, y = _luma(host)
    approx, details = _decompose(y, wavelet, level)
    H, V, D = details[-1]

    flat = np.concatenate([H.flatten(), V.flatten()])
    n_bits = len(bits)
    reps = len(flat) // n_bits // 2
    pos = _positions(len(flat), n_bits * reps, key)
    flat[pos] = _qim_embed(flat[pos], np.tile(bits, reps).astype(np.float64), delta)

    n = H.size
    details[-1] = (flat[:n].reshape(H.shape), flat[n:].reshape(V.shape), D)
    yn = np.clip(np.round(_reconstruct(approx, details, wavelet)), 0, 255).astype(np.uint8)

    if ycc is None:
        return yn
    ycc[:, :, 0] = yn
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)


def extract(img, n_bits=1024, delta=36.0, key=2024, wavelet="haar", level=2):
    _, y = _luma(img)
    _, details = _decompose(y, wavelet, level)
    H, V, _ = details[-1]
    flat = np.concatenate([H.flatten(), V.flatten()])
    reps = len(flat) // n_bits // 2
    pos = _positions(len(flat), n_bits * reps, key)
    score = _qim_score(flat[pos], delta).reshape(reps, n_bits).sum(axis=0)
    return (score > 0).astype(np.uint8)
