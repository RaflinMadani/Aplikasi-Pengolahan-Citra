"""Uji alur kerja TANPA dataset asli (data sintetis). Jalankan:  python smoke_test.py"""
import os
import sys
import tempfile

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from models import Decoder, Discriminator, Encoder
from utils.dataset_loader import get_dataloader
from utils.metrics import ber, psnr, ssim
from utils.noise_layers import ATTACKS, NoiseLayer

fails = []


def check(name, ok):
    print(f"  [{'OK' if ok else 'GAGAL'}] {name}")
    if not ok:
        fails.append(name)


def main():
    torch.manual_seed(0)
    L = 30
    x = torch.rand(2, 3, 64, 64) * 2 - 1
    msg = torch.randint(0, 2, (2, L)).float()
    enc, dec, disc = Encoder(L), Decoder(L), Discriminator()

    print("1) Model")
    e = enc(x, msg)
    check("Encoder: output shape = input shape", e.shape == x.shape)
    check("Decoder: output (B, msg_len)", dec(e).shape == (2, L))
    check("Discriminator: output (B, 1)", disc(e).shape == (2, 1))

    print("2) Noise layers")
    for a in ATTACKS:
        out = NoiseLayer.apply(a, e.detach(), x, **NoiseLayer.sample_params(a))
        check(f"{a}: shape sama & nilai finite", out.shape == e.shape and torch.isfinite(out).all().item())
    xg = x.clone().requires_grad_(True)
    NoiseLayer.apply("jpeg", xg, x, quality=50).sum().backward()
    check("JPEG: gradien mengalir (straight-through)", xg.grad is not None)

    print("3) Metrik")
    check("PSNR(x, x) sangat tinggi", psnr(x, x) >= 99)
    check("SSIM(x, x) ~ 1", ssim(x, x) > 0.999)
    check("BER = 0 untuk prediksi sempurna", ber((msg * 2 - 1) * 5, msg) == 0.0)
    check("BER = 1 untuk prediksi terbalik", ber((1 - msg * 2) * 5, msg) == 1.0)

    print("4) Backpropagation")
    loss = nn.MSELoss()(e, x) + nn.BCEWithLogitsLoss()(dec(NoiseLayer.apply("blur", e, x, sigma=1.0)), msg)
    loss.backward()
    check("Gradien Encoder ada", all(p.grad is not None for p in enc.parameters()))
    check("Gradien Decoder ada", all(p.grad is not None for p in dec.parameters()))

    print("5) DataLoader (6 gambar sintetis)")
    with tempfile.TemporaryDirectory() as d:
        for i in range(6):
            arr = (np.random.rand(80, 96, 3) * 255).astype("uint8")
            Image.fromarray(arr).save(os.path.join(d, f"img_{i}.jpg"))
        batch = next(iter(get_dataloader(d, 64, 2, True, num_workers=0)))
        check("Batch shape (2,3,64,64)", tuple(batch.shape) == (2, 3, 64, 64))
        check("Rentang nilai [-1, 1]", batch.min() >= -1 and batch.max() <= 1)

    print("\nSEMUA OK - alur kerja siap dipakai." if not fails else f"\n{len(fails)} pemeriksaan GAGAL: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
