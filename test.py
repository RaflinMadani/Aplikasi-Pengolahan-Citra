"""Evaluasi imperceptibility (PSNR, SSIM) dan robustness (BER) per serangan."""
import argparse
import csv
import os
import torch
from torchvision.utils import save_image

from models.encoder import Encoder
from models.decoder import Decoder
from models.noise_layer import NoiseLayer
from utils.dataset_loader import get_dataloader
from utils.metrics import psnr, ssim, ber, to01

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
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model_path", default="./weights/best_model.pth")
    p.add_argument("--dataset_path", default="./dataset/val")
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--num_val", type=int, default=1000)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--out_dir", default="./results")
    args = p.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(args.model_path, map_location=dev)
    L, size = ck["msg_len"], ck["image_size"]
    enc, dec = Encoder(L).to(dev), Decoder(L).to(dev)
    enc.load_state_dict(ck["encoder"]); dec.load_state_dict(ck["decoder"])
    enc.eval(); dec.eval()

    dl = get_dataloader(args.dataset_path, size, args.batch_size, False,
                        args.num_workers, args.num_val)
    os.makedirs(args.out_dir, exist_ok=True)
    ps_sum = ss_sum = 0.0
    ber_sum = {s[0]: 0.0 for s in SCENARIOS}
    n = 0
    with torch.no_grad():
        for i, imgs in enumerate(dl):
            imgs = imgs.to(dev)
            msg = torch.randint(0, 2, (imgs.size(0), L), device=dev).float()
            enc_img = enc(imgs, msg).clamp(-1, 1)
            enc_img = (enc_img + 1) / 2
            enc_img = (enc_img * 255).round() / 255 * 2 - 1  # kuantisasi 8-bit (realistis)
            ps_sum += psnr(enc_img, imgs); ss_sum += ssim(enc_img, imgs)
            for name, atk, prm in SCENARIOS:
                ber_sum[name] += ber(dec(NoiseLayer.apply(atk, enc_img, imgs, **prm)), msg)
            n += 1
            if i == 0:
                diff = (enc_img - imgs).abs() * 10  # selisih diperbesar 10x
                save_image(torch.cat([to01(imgs[:4]), to01(enc_img[:4]), diff[:4].clamp(0, 1) ]),
                           os.path.join(args.out_dir, "samples.png"), nrow=4)

    psnr_v, ssim_v = ps_sum / n, ss_sum / n
    print("\n=== Imperceptibility ===")
    print(f"PSNR : {psnr_v:.2f} dB  (target > 38)  {'OK' if psnr_v > 38 else 'BELUM'}")
    print(f"SSIM : {ssim_v:.4f}     (target > 0.96) {'OK' if ssim_v > 0.96 else 'BELUM'}")
    print("\n=== Robustness (BER) ===")
    rows = []
    for name, _, _ in SCENARIOS:
        b = ber_sum[name] / n * 100
        rows.append((name, b))
        print(f"{name:<24}: BER = {b:6.2f}%")
    with open(os.path.join(args.out_dir, "results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric", "value"])
        w.writerow(["PSNR_dB", f"{psnr_v:.4f}"]); w.writerow(["SSIM", f"{ssim_v:.4f}"])
        for name, b in rows:
            w.writerow([f"BER_%_{name}", f"{b:.4f}"])
    print(f"\nHasil disimpan di {args.out_dir}/ (results.csv, samples.png)")


if __name__ == "__main__":
    main()
