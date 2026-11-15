"""Menyiapkan data/train & data/val dari folder gambar mentah (mis. ImageNet/COCO).

Contoh:
  python -m utils.prepare_data --source D:/imagenet/val --num_train 10000 --num_val 1000

Gambar diacak (seed tetap), dipisah train/val tanpa tumpang tindih, lalu di-resize
(sisi terpendek = --size) + center-crop ke size x size agar training jauh lebih cepat.
"""
import argparse
import os
import random

from PIL import Image
from tqdm import tqdm

EXTS = (".jpg", ".jpeg", ".png", ".bmp")


def process(src, dst, size, png):
    img = Image.open(src).convert("RGB")
    w, h = img.size
    s = size / min(w, h)
    img = img.resize((max(size, round(w * s)), max(size, round(h * s))), Image.BICUBIC)
    w, h = img.size
    l, t = (w - size) // 2, (h - size) // 2
    img = img.crop((l, t, l + size, t + size))
    if png:
        img.save(dst, "PNG")
    else:
        img.save(dst, "JPEG", quality=95)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, help="folder gambar mentah (rekursif)")
    p.add_argument("--out", default="./data")
    p.add_argument("--num_train", type=int, default=10000)
    p.add_argument("--num_val", type=int, default=1000)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--png", action="store_true", help="simpan PNG (lebih besar), default JPEG q95")
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    files = []
    for d, _, fs in os.walk(a.source):
        files += [os.path.join(d, f) for f in fs if f.lower().endswith(EXTS)]
    files.sort()
    need = a.num_train + a.num_val
    if len(files) < need:
        print(f"[!] Hanya {len(files)} gambar ditemukan (butuh {need}); jumlah disesuaikan.")
        ratio = a.num_train / need
        a.num_train = int(len(files) * ratio)
        a.num_val = len(files) - a.num_train
    random.Random(a.seed).shuffle(files)
    splits = {"train": files[:a.num_train], "val": files[a.num_train:a.num_train + a.num_val]}
    ext = "png" if a.png else "jpg"
    for name, lst in splits.items():
        out_dir = os.path.join(a.out, name)
        os.makedirs(out_dir, exist_ok=True)
        ok = 0
        for i, f in enumerate(tqdm(lst, desc=name)):
            try:
                process(f, os.path.join(out_dir, f"{name}_{i:05d}.{ext}"), a.size, a.png)
                ok += 1
            except Exception as e:  # gambar rusak dilewati
                print(f"  lewati {f}: {e}")
        print(f"{name}: {ok} gambar -> {out_dir}")


if __name__ == "__main__":
    main()
