"""Noise Layer: simulasi serangan yang dapat dilewati gradien.

- JPEG   : kompresi JPEG asli (OpenCV) + straight-through estimator.
- Crop   : area acak dipertahankan, sisanya dihitamkan.
- Noise  : Gaussian noise (sigma pada skala piksel [0,1]).
- Blur   : Gaussian blur.
- Dropout: sebagian piksel dikembalikan ke piksel cover.
Semua input/output berada pada rentang [-1, 1].
"""
import random
import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms.functional as TF

ATTACKS = ["identity", "jpeg", "crop", "gaussian_noise", "blur", "dropout"]


def jpeg_compress(x, quality):
    arr = ((x.detach().clamp(-1, 1) + 1) * 127.5).round().byte()
    arr = arr.permute(0, 2, 3, 1).cpu().numpy()
    out = []
    for img in arr:
        bgr = cv2.cvtColor(np.ascontiguousarray(img), cv2.COLOR_RGB2BGR)
        _, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
        out.append(cv2.cvtColor(dec, cv2.COLOR_BGR2RGB))
    out = torch.from_numpy(np.stack(out)).to(x.device).permute(0, 3, 1, 2).float() / 127.5 - 1
    return x + (out - x).detach()  # forward = JPEG, backward = identitas


def crop_attack(x, removed_ratio):
    b, _, h, w = x.shape
    s = (1.0 - removed_ratio) ** 0.5
    ch, cw = max(1, int(h * s)), max(1, int(w * s))
    out = torch.full_like(x, -1.0)
    for i in range(b):
        t, l = random.randint(0, h - ch), random.randint(0, w - cw)
        out[i, :, t:t + ch, l:l + cw] = x[i, :, t:t + ch, l:l + cw]
    return out


def gaussian_noise(x, sigma):
    return (x + torch.randn_like(x) * sigma * 2).clamp(-1, 1)  # x2: skala [-1,1]


def blur(x, sigma):
    return TF.gaussian_blur(x, kernel_size=5, sigma=float(sigma))


def dropout(x, cover, p):
    keep = (torch.rand(x.size(0), 1, x.size(2), x.size(3), device=x.device) > p).float()
    return x * keep + cover * (1 - keep)


class NoiseLayer(nn.Module):
    """mode='random' -> pilih satu serangan acak per batch (untuk training)."""

    def __init__(self, mode="random"):
        super().__init__()
        self.mode = mode

    @staticmethod
    def sample_params(name):
        return {
            "identity": {},
            "jpeg": {"quality": random.randint(50, 90)},
            "crop": {"removed_ratio": random.uniform(0.1, 0.5)},
            "gaussian_noise": {"sigma": random.uniform(0.01, 0.05)},
            "blur": {"sigma": random.uniform(0.5, 2.0)},
            "dropout": {"p": random.uniform(0.1, 0.3)},
        }[name]

    @staticmethod
    def apply(name, x, cover=None, **p):
        if name == "identity":
            return x
        if name == "jpeg":
            return jpeg_compress(x, p["quality"])
        if name == "crop":
            return crop_attack(x, p["removed_ratio"])
        if name == "gaussian_noise":
            return gaussian_noise(x, p["sigma"])
        if name == "blur":
            return blur(x, p["sigma"])
        if name == "dropout":
            return dropout(x, cover, p["p"])
        raise ValueError(f"Serangan tidak dikenal: {name}")

    def forward(self, encoded, cover):
        name = random.choice(ATTACKS) if self.mode == "random" else self.mode
        return self.apply(name, encoded, cover, **self.sample_params(name))
