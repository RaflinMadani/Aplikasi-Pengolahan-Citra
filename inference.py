"""Demo satu gambar: embed / extract / demo (embed -> serang -> extract).

  python inference.py embed   --image foto.jpg --text "Hak"  --output results/wm.png
  python inference.py extract --image results/wm.png
  python inference.py demo    --image foto.jpg --attack jpeg --param 50
"""
import argparse
import os
import random

import torch
from PIL import Image
from torchvision import transforms
from torchvision.utils import save_image

from models import Decoder, Encoder
from utils.metrics import ber, psnr, ssim, to01
from utils.noise_layers import ATTACKS, NoiseLayer

DEFAULT_PARAMS = {
    "identity": {}, "jpeg": {"quality": 50}, "crop": {"removed_ratio": 0.3},
    "gaussian_noise": {"sigma": 0.05}, "blur": {"sigma": 1.5},
    "resize": {"scale": 0.5}, "dropout": {"p": 0.2},
}


def load_models(path, dev):
    ck = torch.load(path, map_location=dev)
    L = ck["msg_len"]
    enc, dec = Encoder(L).to(dev), Decoder(L).to(dev)
    enc.load_state_dict(ck["encoder"]); dec.load_state_dict(ck["decoder"])
    return enc.eval(), dec.eval(), L, ck["image_size"]


def load_image(path, size, dev):
    img = Image.open(path).convert("RGB")
    if size:
        img = img.resize((size, size), Image.BICUBIC)
    t = transforms.ToTensor()(img) * 2 - 1
    return t.unsqueeze(0).to(dev)


def text_to_bits(text, L):
    bits = "".join(f"{b:08b}" for b in text.encode("utf-8"))
    if len(bits) > L:
        raise SystemExit(f"Teks terlalu panjang: butuh {len(bits)} bit, kapasitas model {L} bit "
                         f"(~{L // 8} karakter ASCII).")
    return bits.ljust(L, "0")


def bits_to_text(bits):
    n = len(bits) // 8
    data = bytes(int(bits[i * 8:(i + 1) * 8], 2) for i in range(n)).rstrip(b"\x00")
    return data.decode("utf-8", errors="replace")


def get_message(args, L):
    if args.bits:
        if len(args.bits) != L or set(args.bits) - {"0", "1"}:
            raise SystemExit(f"--bits harus string 0/1 sepanjang {L} karakter.")
        return args.bits
    if args.text:
        return text_to_bits(args.text, L)
    return "".join(random.choice("01") for _ in range(L))


def to_tensor_bits(bits, dev):
    return torch.tensor([[int(c) for c in bits]], dtype=torch.float32, device=dev)


def decode_bits(dec, img):
    with torch.no_grad():
        logits = dec(img)
    return logits, "".join("1" if v > 0 else "0" for v in logits[0].tolist())


def quantize(x):
    return ((x.clamp(-1, 1) + 1) / 2 * 255).round() / 255 * 2 - 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["embed", "extract", "demo"])
    p.add_argument("--image", required=True)
    p.add_argument("--model_path", default="./checkpoints/best_model.pth")
    p.add_argument("--output", default="./results/watermarked.png")
    p.add_argument("--bits", default=None, help="pesan biner, panjang = msg_len")
    p.add_argument("--text", default=None, help="pesan teks (muat dalam msg_len bit)")
    p.add_argument("--size", type=int, default=0, help="resize ke size x size (0 = ukuran asli)")
    p.add_argument("--attack", default="jpeg", choices=ATTACKS)
    p.add_argument("--param", type=float, default=None, help="parameter serangan (mode demo)")
    args = p.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    enc, dec, L, _ = load_models(args.model_path, dev)
    img = load_image(args.image, args.size, dev)
    os.makedirs("./results", exist_ok=True)

    if args.mode == "extract":
        _, bits = decode_bits(dec, img)
        print(f"Bit terekstrak ({L}): {bits}")
        print(f"Sebagai teks      : {bits_to_text(bits)!r}")
        if args.bits:
            msg = to_tensor_bits(get_message(args, L), dev)
            print(f"BER terhadap --bits: {ber(dec(img), msg) * 100:.2f}%")
        return

    bits = get_message(args, L)
    msg = to_tensor_bits(bits, dev)
    with torch.no_grad():
        wm = quantize(enc(img, msg))
    print(f"Pesan disisipkan ({L} bit): {bits}")
    print(f"PSNR = {psnr(wm, img):.2f} dB | SSIM = {ssim(wm, img):.4f}")

    if args.mode == "embed":
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        save_image(to01(wm), args.output)  # simpan PNG (lossless)!
        print(f"Tersimpan: {args.output}  (gunakan PNG; JPEG akan merusak watermark kecuali tahan)")
        return

    # mode demo
    params = dict(DEFAULT_PARAMS[args.attack])
    if args.param is not None and params:
        params[next(iter(params))] = args.param
    attacked = NoiseLayer.apply(args.attack, wm, img, **params)
    _, rec = decode_bits(dec, attacked)
    b = ber(dec(attacked), msg) * 100
    print(f"Serangan: {args.attack} {params}")
    print(f"Bit terekstrak     : {rec}")
    print(f"BER                : {b:.2f}%  ({'BERHASIL' if b < 5 else 'PERLU DICEK'})")
    diff = ((wm - img).abs() / 2 * 10).clamp(0, 1)
    save_image(torch.cat([to01(img), to01(wm), to01(attacked), diff]), "./results/demo.png", nrow=4)
    print("Panel [asli | watermarked | terserang | selisih x10] -> results/demo.png")


if __name__ == "__main__":
    main()
