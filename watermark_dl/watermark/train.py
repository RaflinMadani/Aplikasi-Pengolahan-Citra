"""Training end-to-end Encoder - Noise Layer - Decoder."""
import argparse
import os
import torch
import torch.nn as nn
from tqdm import tqdm

from models.encoder import Encoder
from models.decoder import Decoder
from models.noise_layer import NoiseLayer
from utils.dataset_loader import get_dataloader
from utils.metrics import psnr, ber


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=0.001)
    p.add_argument("--dataset_path", default="./dataset/train")
    p.add_argument("--val_path", default=None, help="default: sibling folder 'val'")
    p.add_argument("--msg_len", type=int, default=30)
    p.add_argument("--image_size", type=int, default=256)
    p.add_argument("--num_train", type=int, default=10000)
    p.add_argument("--num_val", type=int, default=1000)
    p.add_argument("--lambda_enc", type=float, default=0.7)
    p.add_argument("--lambda_dec", type=float, default=1.0)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--save_dir", default="./weights")
    return p.parse_args()


def step(enc, dec, noise, imgs, msg_len, mse, bce, args):
    msg = torch.randint(0, 2, (imgs.size(0), msg_len), device=imgs.device).float()
    encoded = enc(imgs, msg)
    noised = noise(encoded, imgs)
    logits = dec(noised)
    l_enc, l_dec = mse(encoded, imgs), bce(logits, msg)
    loss = args.lambda_enc * l_enc + args.lambda_dec * l_dec
    return loss, l_enc, l_dec, psnr(encoded.detach(), imgs), ber(logits.detach(), msg)


def main():
    args = parse()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    val_path = args.val_path or os.path.join(os.path.dirname(os.path.normpath(args.dataset_path)), "val")
    train_dl = get_dataloader(args.dataset_path, args.image_size, args.batch_size, True,
                              args.num_workers, args.num_train)
    val_dl = get_dataloader(val_path, args.image_size, args.batch_size, False,
                            args.num_workers, args.num_val)

    enc, dec = Encoder(args.msg_len).to(dev), Decoder(args.msg_len).to(dev)
    noise = NoiseLayer("random")
    opt = torch.optim.Adam(list(enc.parameters()) + list(dec.parameters()), lr=args.lr)
    mse, bce = nn.MSELoss(), nn.BCEWithLogitsLoss()  # BCE + sigmoid (stabil numerik)
    os.makedirs(args.save_dir, exist_ok=True)
    best = float("inf")

    for ep in range(1, args.epochs + 1):
        enc.train(); dec.train()
        agg = [0.0] * 4
        for imgs in tqdm(train_dl, desc=f"Epoch {ep}/{args.epochs}", leave=False):
            imgs = imgs.to(dev)
            loss, le, ld, ps, be = step(enc, dec, noise, imgs, args.msg_len, mse, bce, args)
            opt.zero_grad(); loss.backward(); opt.step()
            for i, v in enumerate((loss.item(), ps, be, ld.item())):
                agg[i] += v
        n = len(train_dl)
        print(f"[Train] ep {ep} loss={agg[0]/n:.4f} PSNR={agg[1]/n:.2f}dB "
              f"BER={agg[2]/n*100:.2f}% dec={agg[3]/n:.4f}")

        enc.eval(); dec.eval()
        agg = [0.0] * 3
        with torch.no_grad():
            for imgs in val_dl:
                imgs = imgs.to(dev)
                loss, _, _, ps, be = step(enc, dec, noise, imgs, args.msg_len, mse, bce, args)
                agg[0] += loss.item(); agg[1] += ps; agg[2] += be
        n = len(val_dl)
        vloss = agg[0] / n
        print(f"[Val]   ep {ep} loss={vloss:.4f} PSNR={agg[1]/n:.2f}dB BER={agg[2]/n*100:.2f}%")

        ckpt = {"encoder": enc.state_dict(), "decoder": dec.state_dict(),
                "msg_len": args.msg_len, "image_size": args.image_size, "epoch": ep}
        torch.save(ckpt, os.path.join(args.save_dir, "last_model.pth"))
        if vloss < best:
            best = vloss
            torch.save(ckpt, os.path.join(args.save_dir, "best_model.pth"))
            print("  -> best_model.pth diperbarui")


if __name__ == "__main__":
    main()
