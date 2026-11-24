"""Metrik evaluasi: PSNR, SSIM, BER."""
import numpy as np
from skimage.metrics import structural_similarity


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def ssim(a, b):
    if a.ndim == 3:
        return structural_similarity(a, b, channel_axis=2, data_range=255)
    return structural_similarity(a, b, data_range=255)


def bit_errors(bits_orig, bits_ext):
    return int(np.sum(np.asarray(bits_orig) != np.asarray(bits_ext)))


def ber(bits_orig, bits_ext):
    """Bit Error Rate dalam persen."""
    return 100.0 * np.mean(np.asarray(bits_orig) != np.asarray(bits_ext))
