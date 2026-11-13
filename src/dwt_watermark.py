"""
Invisible Image Watermarking berbasis DWT (Haar) + QIM.

Alur:
  Citra -> kanal Y -> DWT 2 level -> sub-band detail level-2 (HL2 & LH2)
  -> bit watermark disisipkan dengan Quantization Index Modulation (QIM)
  -> tiap bit diulang (redundansi) pada posisi acak (kunci rahasia)
  -> IDWT -> citra ber-watermark.
Ekstraksi bersifat BLIND (tidak butuh citra asli), memakai soft-voting.
"""
import numpy as np
import cv2

try:
    import pywt
    _HAS_PYWT = True
except ImportError:  # fallback Haar murni NumPy
    _HAS_PYWT = False


# --------------------------------------------------------------------------
# Haar DWT (fallback) -- konvensi sama dengan pywt: cA, (cH, cV, cD)
# cH = detail horizontal (HL di README), cV = detail vertikal (LH di README)
# --------------------------------------------------------------------------
def _haar_dwt2(x):
    a, b = x[0::2, 0::2], x[0::2, 1::2]
    c, d = x[1::2, 0::2], x[1::2, 1::2]
    cA = (a + b + c + d) / 2.0
    cH = (a + b - c - d) / 2.0
    cV = (a - b + c - d) / 2.0
    cD = (a - b - c + d) / 2.0
    return cA, (cH, cV, cD)


def _haar_idwt2(coeffs):
    cA, (cH, cV, cD) = coeffs
    h, w = cA.shape
    out = np.zeros((h * 2, w * 2), dtype=np.float64)
    out[0::2, 0::2] = (cA + cH + cV + cD) / 2.0
    out[0::2, 1::2] = (cA + cH - cV - cD) / 2.0
    out[1::2, 0::2] = (cA - cH + cV - cD) / 2.0
    out[1::2, 1::2] = (cA - cH - cV + cD) / 2.0
    return out


def dwt2(x):
    return pywt.dwt2(x, "haar") if _HAS_PYWT else _haar_dwt2(x)


def idwt2(c):
    return pywt.idwt2(c, "haar") if _HAS_PYWT else _haar_idwt2(c)


# --------------------------------------------------------------------------
# QIM
# --------------------------------------------------------------------------
def _qim_embed(coef, bits, delta):
    off = bits * (delta / 2.0)
    return delta * np.round((coef - off) / delta) + off


def _qim_score(coef, delta):
    """Skor soft: >0 condong bit 1, <0 condong bit 0."""
    q0 = delta * np.round(coef / delta)
    off = delta / 2.0
    q1 = delta * np.round((coef - off) / delta) + off
    d0, d1 = np.abs(coef - q0), np.abs(coef - q1)
    return d0 - d1


def _positions(n_total, n_use, key):
    rng = np.random.RandomState(key)
    return rng.permutation(n_total)[:n_use]


def _decompose(img_y):
    cA1, (H1, V1, D1) = dwt2(img_y)
    cA2, (H2, V2, D2) = dwt2(cA1)
    return cA1, (H1, V1, D1), cA2, (H2, V2, D2)


# --------------------------------------------------------------------------
# Antarmuka publik
# --------------------------------------------------------------------------
def prepare_watermark(wm_img, size=32):
    """Citra/logo -> vektor bit 0/1 (size*size)."""
    if wm_img.ndim == 3:
        wm_img = cv2.cvtColor(wm_img, cv2.COLOR_BGR2GRAY)
    wm_img = cv2.resize(wm_img, (size, size), interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(wm_img, 127, 1, cv2.THRESH_BINARY)
    return binary.astype(np.uint8).flatten()


def bits_to_image(bits, size=32):
    return (bits.reshape(size, size) * 255).astype(np.uint8)


def embed(host_bgr, bits, delta=40.0, key=2024):
    """Sisipkan bit watermark ke citra BGR/gray. Return citra uint8 ber-watermark."""
    gray = host_bgr.ndim == 2
    if gray:
        y = host_bgr.astype(np.float64)
    else:
        ycc = cv2.cvtColor(host_bgr, cv2.COLOR_BGR2YCrCb)
        y = ycc[:, :, 0].astype(np.float64)

    h, w = y.shape
    assert h % 4 == 0 and w % 4 == 0, "Ukuran citra harus kelipatan 4"

    cA1, d1, cA2, (H2, V2, D2) = _decompose(y)

    # gabungkan HL2 & LH2 -> vektor koefisien
    flat = np.concatenate([H2.flatten(), V2.flatten()])
    n_bits = len(bits)
    reps = len(flat) // n_bits // 2          # pakai maks. separuh koefisien
    pos = _positions(len(flat), n_bits * reps, key)
    bit_map = np.tile(bits, reps).astype(np.float64)

    flat[pos] = _qim_embed(flat[pos], bit_map, delta)

    n = H2.size
    H2n, V2n = flat[:n].reshape(H2.shape), flat[n:].reshape(V2.shape)

    cA1n = idwt2((cA2, (H2n, V2n, D2)))
    yn = idwt2((cA1n, d1))
    yn = np.clip(np.round(yn), 0, 255).astype(np.uint8)

    if gray:
        return yn
    ycc[:, :, 0] = yn
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)


def extract(img_bgr, n_bits=1024, delta=40.0, key=2024):
    """Ekstraksi blind. Return vektor bit hasil voting."""
    if img_bgr.ndim == 2:
        y = img_bgr.astype(np.float64)
    else:
        y = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)[:, :, 0].astype(np.float64)

    _, _, _, (H2, V2, _) = _decompose(y)
    flat = np.concatenate([H2.flatten(), V2.flatten()])
    reps = len(flat) // n_bits // 2
    pos = _positions(len(flat), n_bits * reps, key)

    score = _qim_score(flat[pos], delta).reshape(reps, n_bits).sum(axis=0)
    return (score > 0).astype(np.uint8)
