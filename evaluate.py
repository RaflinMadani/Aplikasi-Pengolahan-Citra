"""Evaluasi: imperceptibility (PSNR, SSIM) + robustness (BER) per serangan."""
import argparse
import csv
import os

import torch
from torchvision.utils import save_image

from models import Decoder, Encoder
from utils.dataset_loader import get_dataloader
from utils.metrics import ber, psnr, ssim, to01
from utils.noise_layers import NoiseLayer

SCENARIOS = [
    ("Tanpa serangan", "identity", {}),
    ("JPEG QF=90", "jpeg", {"quality": 90}),
    ("JPEG QF=70", "jpeg", {"quality": 70}),
    ("JPEG QF=50", "jpeg", {"quality": 50}),
    ("Crop 10%", "crop", {"removed_ratio": 0.10}),
    ("Crop 30%", "crop", {"removed_ratio": 0.30}),
    ("Crop 50%", "crop", {"removed_ratio": 0.50}),
    ("Gaussian noise s=0.01", "gaussian_noise", {"sigma": 0.01}),
    ("Gaussian noise s=0.05", "gaussian_noise", {"sigma": 0.05}),
    ("Resize 75%", "resize", {"scale": 0.75}),
    ("Resize 50%", "resize", {"scale": 0.50}),
]


def main():
    p = argparse.ArgumentParser(description="Evaluasi model watermarking")
    p.add_argument("--model_path", default="./checkpoints/best_model.pth")
    p.add_argument("--data_dir", default="./data/val")
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--num_images", type=int, default=1000, help="0 = semua")
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--out_dir", default="./results")
    args = p.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(args.model_path, map_location=dev)
    L, size = ck["msg_len"], ck["image_size"]
    enc, dec = Encoder(L).to(dev), Decoder(L).to(dev)
    enc.load_state_dict(ck["encoder"]); dec.load_state_dict(ck["decoder"])
    enc.eval(); dec.eval()
    print(f"Model epoch {ck['epoch']} | msg_len={L} | image_size={size}")

    dl = get_dataloader(args.data_dir, size, args.batch_size, False,
                        args.num_workers, args.num_images or None)
    os.makedirs(args.out_dir, exist_ok=True)
    ps_sum = ss_sum = 0.0
    ber_sum = {s[0]: 0.0 for s in SCENARIOS}
    n = 0
    with torch.no_grad():
        for i, imgs in enumerate(dl):
            imgs = imgs.to(dev)
            msg = torch.randint(0, 2, (imgs.size(0), L), device=dev).float()
            e = (enc(imgs, msg).clamp(-1, 1) + 1) / 2
            e = (e * 255).round() / 255 * 2 - 1  # kuantisasi 8-bit seperti file gambar nyata
            ps_sum += psnr(e, imgs); ss_sum += ssim(e, imgs)
            for name, atk, prm in SCENARIOS:
                ber_sum[name] += ber(dec(NoiseLayer.apply(atk, e, imgs, **prm)), msg)
            n += 1
            if i == 0:
                k = min(4, imgs.size(0))
                diff = ((e[:k] - imgs[:k]).abs() / 2 * 10).clamp(0, 1)  # selisih x10
                save_image(torch.cat([to01(imgs[:k]), to01(e[:k]), diff]),
                           os.path.join(args.out_dir, "samples.png"), nrow=k)

    psnr_v, ssim_v = ps_sum / n, ss_sum / n
    print("\n=== Imperceptibility ===")
    print(f"PSNR : {psnr_v:6.2f} dB   (target > 38)   {'OK' if psnr_v > 38 else 'BELUM'}")
    print(f"SSIM : {ssim_v:6.4f}      (target > 0.96) {'OK' if ssim_v > 0.96 else 'BELUM'}")
    print("\n=== Robustness (BER, makin kecil makin baik; 50% = tebakan acak) ===")
    rows = []
    for name, _, _ in SCENARIOS:
        b = ber_sum[name] / n * 100
        rows.append((name, b))
        print(f"{name:<24}: {b:6.2f}%")
    with open(os.path.join(args.out_dir, "evaluation_results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["PSNR_dB", f"{psnr_v:.4f}"]); w.writerow(["SSIM", f"{ssim_v:.4f}"])
        for name, b in rows:
            w.writerow([f"BER_pct | {name}", f"{b:.4f}"])
    print(f"\nTersimpan di {args.out_dir}/: evaluation_results.csv, samples.png")


if __name__ == "__main__":
    main()
