"""Training end-to-end: Encoder -> Noise Layer -> Decoder (+ Discriminator opsional)."""
import argparse
import csv
import os
import random

import numpy as np
import torch
import torch.nn as nn
from tqdm import tqdm

from models import Decoder, Discriminator, Encoder
from utils.dataset_loader import get_dataloader
from utils.metrics import ber, psnr
from utils.noise_layers import NoiseLayer


def parse():
    p = argparse.ArgumentParser(description="Training DL Invisible Watermarking")
    p.add_argument("--train_dir", default="./data/train")
    p.add_argument("--val_dir", default="./data/val")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--msg_len", type=int, default=30, help="panjang pesan (bit)")
    p.add_argument("--image_size", type=int, default=256)
    p.add_argument("--num_train", type=int, default=10000, help="0 = pakai semua")
    p.add_argument("--num_val", type=int, default=1000, help="0 = pakai semua")
    p.add_argument("--lambda_enc", type=float, default=0.7)
    p.add_argument("--lambda_dec", type=float, default=1.0)
    p.add_argument("--use_discriminator", action="store_true")
    p.add_argument("--lambda_adv", type=float, default=0.001)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--ckpt_dir", default="./checkpoints")
    p.add_argument("--log_dir", default="./results")
    p.add_argument("--resume", default=None, help="path checkpoint untuk melanjutkan")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def forward_batch(enc, dec, noise, imgs, msg_len):
    msg = torch.randint(0, 2, (imgs.size(0), msg_len), device=imgs.device).float()
    encoded = enc(imgs, msg)
    noised = noise(encoded, imgs)
    return msg, encoded, dec(noised)


def main():
    args = parse()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {dev}")

    train_dl = get_dataloader(args.train_dir, args.image_size, args.batch_size, True,
                              args.num_workers, args.num_train or None)
    val_dl = get_dataloader(args.val_dir, args.image_size, args.batch_size, False,
                            args.num_workers, args.num_val or None)
    print(f"Train: {len(train_dl.dataset)} citra | Val: {len(val_dl.dataset)} citra")

    enc, dec = Encoder(args.msg_len).to(dev), Decoder(args.msg_len).to(dev)
    noise = NoiseLayer("random")
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=args.lr)
    disc = opt_d = None
    if args.use_discriminator:
        disc = Discriminator().to(dev)
        opt_d = torch.optim.Adam(disc.parameters(), lr=args.lr)
    mse, bce = nn.MSELoss(), nn.BCEWithLogitsLoss()  # BCE + sigmoid (stabil numerik)

    start_ep, best = 1, float("inf")
    if args.resume:
        ck = torch.load(args.resume, map_location=dev)
        enc.load_state_dict(ck["encoder"]); dec.load_state_dict(ck["decoder"])
        opt.load_state_dict(ck["optimizer"])
        if disc is not None and "discriminator" in ck:
            disc.load_state_dict(ck["discriminator"]); opt_d.load_state_dict(ck["optimizer_d"])
        start_ep, best = ck["epoch"] + 1, ck.get("best_val_loss", best)
        print(f"Resume dari epoch {ck['epoch']}")

    os.makedirs(args.ckpt_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    log_path = os.path.join(args.log_dir, "training_log.csv")
    if not os.path.exists(log_path) or start_ep == 1:
        with open(log_path, "w", newline="") as f:
            csv.writer(f).writerow(["epoch", "train_loss", "train_psnr", "train_ber_pct",
                                    "val_loss", "val_psnr", "val_ber_pct"])

    for ep in range(start_ep, args.epochs + 1):
        # ---------------- TRAIN ----------------
        enc.train(); dec.train()
        if disc is not None:
            disc.train()
        tl = tp = tb = 0.0
        for imgs in tqdm(train_dl, desc=f"Epoch {ep}/{args.epochs}", leave=False):
            imgs = imgs.to(dev)
            msg, encoded, logits = forward_batch(enc, dec, noise, imgs, args.msg_len)
            loss_adv = torch.zeros((), device=dev)
            if disc is not None:
                ones = torch.ones(imgs.size(0), 1, device=dev)
                zeros = torch.zeros(imgs.size(0), 1, device=dev)
                loss_d = bce(disc(imgs), ones) + bce(disc(encoded.detach()), zeros)
                opt_d.zero_grad(); loss_d.backward(); opt_d.step()
                loss_adv = bce(disc(encoded), ones)
            loss = (args.lambda_enc * mse(encoded, imgs) + args.lambda_dec * bce(logits, msg)
                    + args.lambda_adv * loss_adv)
            opt.zero_grad(); loss.backward(); opt.step()
            tl += loss.item(); tp += psnr(encoded.detach(), imgs); tb += ber(logits.detach(), msg)
        n = len(train_dl)
        tl, tp, tb = tl / n, tp / n, tb / n * 100

        # ---------------- VALIDATION ----------------
        enc.eval(); dec.eval()
        vl = vp = vb = 0.0
        with torch.no_grad():
            for imgs in val_dl:
                imgs = imgs.to(dev)
                msg, encoded, logits = forward_batch(enc, dec, noise, imgs, args.msg_len)
                vl += (args.lambda_enc * mse(encoded, imgs) + args.lambda_dec * bce(logits, msg)).item()
                vp += psnr(encoded, imgs); vb += ber(logits, msg)
        n = len(val_dl)
        vl, vp, vb = vl / n, vp / n, vb / n * 100

        print(f"Ep {ep:3d} | train loss {tl:.4f} PSNR {tp:5.2f} BER {tb:5.2f}% "
              f"| val loss {vl:.4f} PSNR {vp:5.2f} BER {vb:5.2f}%")
        with open(log_path, "a", newline="") as f:
            csv.writer(f).writerow([ep, f"{tl:.5f}", f"{tp:.3f}", f"{tb:.3f}",
                                    f"{vl:.5f}", f"{vp:.3f}", f"{vb:.3f}"])

        ck = {"encoder": enc.state_dict(), "decoder": dec.state_dict(),
              "optimizer": opt.state_dict(), "epoch": ep, "best_val_loss": min(best, vl),
              "msg_len": args.msg_len, "image_size": args.image_size}
        if disc is not None:
            ck["discriminator"] = disc.state_dict(); ck["optimizer_d"] = opt_d.state_dict()
        torch.save(ck, os.path.join(args.ckpt_dir, "last_model.pth"))
        if vl < best:
            best = vl
            torch.save(ck, os.path.join(args.ckpt_dir, "best_model.pth"))
            print("      -> best_model.pth diperbarui")


if __name__ == "__main__":
    main()
