"""Metrik: PSNR, SSIM, BER. Citra masukan di [-1,1] dikonversi ke [0,1]."""
import torch
import torch.nn.functional as F


def to01(x):
    return ((x + 1) / 2).clamp(0, 1)


def psnr(a, b):
    mse = ((to01(a) - to01(b)) ** 2).flatten(1).mean(1).clamp_min(1e-10)
    return (10 * torch.log10(1.0 / mse)).mean().item()


def _window(size=11, sigma=1.5, c=3, device="cpu"):
    g = torch.arange(size, dtype=torch.float32, device=device) - size // 2
    g = torch.exp(-g ** 2 / (2 * sigma ** 2))
    g = g / g.sum()
    return (g[:, None] @ g[None, :]).expand(c, 1, size, size).contiguous()


def ssim(a, b, size=11):
    a, b = to01(a), to01(b)
    c = a.size(1)
    w = _window(size, 1.5, c, a.device)
    f = lambda x: F.conv2d(x, w, padding=size // 2, groups=c)
    mu_a, mu_b = f(a), f(b)
    var_a = f(a * a) - mu_a ** 2
    var_b = f(b * b) - mu_b ** 2
    cov = f(a * b) - mu_a * mu_b
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    s = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))
    return s.mean().item()


def ber(logits, message):
    """Bit Error Rate (0..1). logits: keluaran decoder, message: bit asli."""
    pred = (logits > 0).float()
    return (pred != message).float().mean().item()
