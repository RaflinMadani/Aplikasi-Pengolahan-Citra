"""
Invisible Image Watermarking berbasis DWT + Adaptive QIM + Hamming(7,4) ECC.

Peningkatan:
  1. Mendukung watermark hingga 512x512 (262.144 bit) dengan memanfaatkan seluruh
     sub-band detail (HL, LH, HH).
  2. Texture-Adaptive QIM: menyesuaikan langkah kuantisasi (delta) berdasarkan
     energi tekstur lokal pada sub-band LL agar PSNR/SSIM tetap tinggi.
  3. Hamming(7,4) ECC opsional untuk memperbaiki galat bit akibat kompresi JPEG/derau.
  4. Ekstraksi BLIND (tanpa citra asli) dengan soft-voting.
"""
import numpy as np
import cv2

from .codec import image_to_bits as prepare_watermark, bits_to_image  # noqa: F401

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
    return (
        (a + b + c + d) / 2.0,
        ((a + b - c - d) / 2.0, (a - b + c - d) / 2.0, (a - b - c + d) / 2.0),
    )


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
            f"Wavelet '{w}' memerlukan PyWavelets. Jalankan: pip install PyWavelets"
        )


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


# -------------------------------------------------------- Hamming(7,4) ---
_G = np.array([
    [1, 0, 0, 0, 1, 1, 0],
    [0, 1, 0, 0, 1, 0, 1],
    [0, 0, 1, 0, 0, 1, 1],
    [0, 0, 0, 1, 1, 1, 1],
], dtype=np.uint8)

_H = np.array([
    [1, 1, 0, 1, 1, 0, 0],
    [1, 0, 1, 1, 0, 1, 0],
    [0, 1, 1, 1, 0, 0, 1],
], dtype=np.uint8)

# Lookup table sindrom 3-bit -> indeks bit yang salah (0..6), -1 jika tanpa galat
_SYNDROME_TO_IDX = {-1: -1}
for _col in range(7):
    _syn = int(_H[0, _col] * 4 + _H[1, _col] * 2 + _H[2, _col])
    _SYNDROME_TO_IDX[_syn] = _col


def _ecc_encode(bits):
    bits = np.asarray(bits, dtype=np.uint8).flatten()
    pad = (-len(bits)) % 4
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    blocks = bits.reshape(-1, 4)
    encoded = (blocks @ _G) % 2
    return encoded.flatten().astype(np.uint8)


def _ecc_decode(encoded_bits, orig_len):
    enc = np.asarray(encoded_bits, dtype=np.uint8).flatten()
    n_blocks = (orig_len + 3) // 4
    enc = enc[: n_blocks * 7].reshape(n_blocks, 7)
    syndromes = (enc @ _H.T) % 2
    syn_vals = syndromes[:, 0] * 4 + syndromes[:, 1] * 2 + syndromes[:, 2]
    for i, s in enumerate(syn_vals):
        if s != 0:
            err_idx = _SYNDROME_TO_IDX.get(int(s), -1)
            if err_idx >= 0:
                enc[i, err_idx] ^= 1
    return enc[:, :4].flatten()[:orig_len].astype(np.uint8)


# --------------------------------------------------------- Adaptive QIM ---
def _adaptive_delta_map(approx, base_delta, adaptive=True):
    """
    Hitung peta delta per koefisien dari sub-band LL (invarian terhadap modifikasi detail).
    Area bertekstur mendapat delta lebih besar; area halus mendapat delta lebih kecil.
    """
    if not adaptive:
        return np.full(approx.shape, float(base_delta), dtype=np.float64)

    # Estimasi tekstur lokal menggunakan deviasi standar 3x3 pada LL
    mean = cv2.blur(approx, (3, 3))
    sq_mean = cv2.blur(approx ** 2, (3, 3))
    std = np.sqrt(np.maximum(sq_mean - mean ** 2, 0.0))

    # Normalisasi lembut ke rentang [0.75 * delta, 1.35 * delta]
    med = np.median(std) + 1e-6
    scale = np.clip(std / med, 0.5, 2.0)
    factor = 0.75 + 0.30 * (scale - 0.5)  # [0.75 .. 1.20]
    return base_delta * factor


def _qim_embed(coef, bits, delta_vec):
    off = bits * (delta_vec / 2.0)
    return delta_vec * np.round((coef - off) / delta_vec) + off


def _qim_score(coef, delta_vec):
    """Skor soft: >0 condong bit 1, <0 condong bit 0."""
    q0 = delta_vec * np.round(coef / delta_vec)
    q1 = delta_vec * np.round((coef - delta_vec / 2.0) / delta_vec) + delta_vec / 2.0
    return np.abs(coef - q0) - np.abs(coef - q1)


def _positions(n_total, n_use, key):
    return np.random.RandomState(key).permutation(n_total)[:n_use]


def _luma(img):
    if img.ndim == 2:
        return None, img.astype(np.float64)
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    return ycc, ycc[:, :, 0].astype(np.float64)


def _effective_level(shape, requested_level, payload_bits):
    """
    Gunakan level yang diminta jika kapasitas mencukupi; jika tidak (mis. watermark 512x512
    pada citra 1024x1024), turunkan ke level 1 secara otomatis agar tidak gagal.
    """
    h, w = shape[:2]
    for lvl in range(requested_level, 0, -1):
        total = 3 * (h // (2 ** lvl)) * (w // (2 ** lvl))
        if total >= payload_bits:
            return lvl
    return requested_level


def capacity(shape, level, n_bits, use_ecc=False):
    """Jumlah pengulangan (redundansi) per bit yang tersedia di seluruh sub-band detail (HL, LH, HH)."""
    h, w = shape[:2]
    eff_bits = ((n_bits + 3) // 4) * 7 if use_ecc else n_bits
    lvl = _effective_level(shape, level, eff_bits)
    total = 3 * (h // (2 ** lvl)) * (w // (2 ** lvl))
    return total // eff_bits


# ------------------------------------------------------------- publik ---
def embed(host, bits, delta=36.0, key=2024, wavelet="haar", level=2, adaptive=True, use_ecc=True):
    h, w = host.shape[:2]
    bits = np.asarray(bits, dtype=np.uint8).flatten()
    orig_n_bits = len(bits)

    # Aktifkan ECC otomatis hanya jika kapasitas setelah ECC masih >= 1 pengulangan
    if use_ecc and capacity(host.shape, level, orig_n_bits, use_ecc=True) >= 1:
        payload = _ecc_encode(bits)
    else:
        payload = bits

    n_payload = len(payload)
    eff_level = _effective_level(host.shape, level, n_payload)

    if h % (2 ** eff_level) or w % (2 ** eff_level):
        raise ValueError(f"Ukuran citra harus kelipatan {2 ** eff_level} untuk level {eff_level}.")

    total_coeffs = 3 * (h // (2 ** eff_level)) * (w // (2 ** eff_level))
    reps = total_coeffs // n_payload
    if reps < 1:
        raise ValueError(
            f"Citra ({w}x{h}) terlalu kecil untuk {orig_n_bits} bit watermark "
            f"(maksimal {total_coeffs} bit pada level {eff_level})."
        )

    ycc, y = _luma(host)
    approx, details = _decompose(y, wavelet, eff_level)
    H, V, D = details[-1]

    # Bangun peta delta adaptif dari sub-band LL pada level terdalam
    d_map = _adaptive_delta_map(approx, delta, adaptive=adaptive).flatten()
    delta_flat = np.concatenate([d_map, d_map, d_map])

    flat = np.concatenate([H.flatten(), V.flatten(), D.flatten()])
    pos = _positions(len(flat), n_payload * reps, key)

    tiled_bits = np.tile(payload, reps).astype(np.float64)
    flat[pos] = _qim_embed(flat[pos], tiled_bits, delta_flat[pos])

    n = H.size
    details[-1] = (
        flat[:n].reshape(H.shape),
        flat[n : 2 * n].reshape(V.shape),
        flat[2 * n :].reshape(D.shape),
    )
    yn = np.clip(np.round(_reconstruct(approx, details, wavelet)), 0, 255).astype(np.uint8)

    if ycc is None:
        return yn
    ycc[:, :, 0] = yn
    return cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR)


def extract(img, n_bits=1024, delta=36.0, key=2024, wavelet="haar", level=2, adaptive=True, use_ecc=True):
    if use_ecc and capacity(img.shape, level, n_bits, use_ecc=True) >= 1:
        n_payload = ((n_bits + 3) // 4) * 7
        ecc_active = True
    else:
        n_payload = n_bits
        ecc_active = False

    eff_level = _effective_level(img.shape, level, n_payload)
    _, y = _luma(img)
    approx, details = _decompose(y, wavelet, eff_level)
    H, V, D = details[-1]

    d_map = _adaptive_delta_map(approx, delta, adaptive=adaptive).flatten()
    delta_flat = np.concatenate([d_map, d_map, d_map])

    flat = np.concatenate([H.flatten(), V.flatten(), D.flatten()])
    reps = len(flat) // n_payload
    if reps < 1:
        raise ValueError("Ukuran citra tidak mencukupi untuk mengekstrak jumlah bit yang diminta.")

    pos = _positions(len(flat), n_payload * reps, key)
    scores = _qim_score(flat[pos], delta_flat[pos]).reshape(reps, n_payload).sum(axis=0)
    raw_bits = (scores > 0).astype(np.uint8)

    if ecc_active:
        return _ecc_decode(raw_bits, n_bits)
    return raw_bits