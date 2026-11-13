"""
Skrip utama: penyisipan -> serangan -> ekstraksi -> metrik -> tabel & grafik.
Jalankan:  python main.py
Letakkan citra host di dataset/original/ dan logo di dataset/watermark/.
Jika folder kosong, citra sampel dibuat otomatis agar program tetap berjalan.
"""
import os, glob
import numpy as np
import cv2
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import dwt_watermark as dw
from src import attacks as atk
from src import metrics as mt

IMG_SIZE = 512
WM_SIZE = 32
DELTA = 36.0
KEY = 2024
ORIG_DIR, WM_DIR, RES_DIR = "dataset/original", "dataset/watermark", "results"
os.makedirs(RES_DIR, exist_ok=True)


def make_sample_assets():
    """Buat sampel jika dataset kosong (tekstur sintetis + logo sederhana)."""
    if not glob.glob(f"{ORIG_DIR}/*"):
        try:
            from skimage import data
            samples = {"astronaut": cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR),
                       "coffee": cv2.cvtColor(data.coffee(), cv2.COLOR_RGB2BGR),
                       "chelsea": cv2.cvtColor(data.chelsea(), cv2.COLOR_RGB2BGR)}
        except Exception:
            rng = np.random.RandomState(0)
            base = cv2.GaussianBlur(rng.randint(0, 255, (IMG_SIZE, IMG_SIZE, 3), np.uint8), (0, 0), 6)
            samples = {"synthetic": base}
        for n, im in samples.items():
            cv2.imwrite(f"{ORIG_DIR}/{n}.png", im)
    if not glob.glob(f"{WM_DIR}/*"):
        logo = np.zeros((128, 128), np.uint8)
        cv2.rectangle(logo, (8, 8), (119, 119), 255, 6)
        cv2.putText(logo, "DWT", (14, 78), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 255, 4)
        cv2.circle(logo, (64, 100), 10, 255, -1)
        cv2.imwrite(f"{WM_DIR}/logo.png", logo)


def main():
    make_sample_assets()
    wm_path = sorted(glob.glob(f"{WM_DIR}/*"))[0]
    bits = dw.prepare_watermark(cv2.imread(wm_path), WM_SIZE)
    n_bits = len(bits)

    attack_list = (
        [(f"JPEG Q={q}", (lambda im, q=q: atk.jpeg_compress(im, q))) for q in (90, 70, 50, 30)]
        + [(f"Crop {p}%", (lambda im, p=p: atk.crop(im, p))) for p in (10, 25, 50)]
        + [("Resize 0.5x", lambda im: atk.resize_attack(im, 0.5)),
           ("Resize 0.75x", lambda im: atk.resize_attack(im, 0.75))]
    )

    rows, demo = [], None
    for path in sorted(glob.glob(f"{ORIG_DIR}/*")):
        host = cv2.imread(path)
        if host is None:
            continue
        host = cv2.resize(host, (IMG_SIZE, IMG_SIZE))
        name = os.path.splitext(os.path.basename(path))[0]

        wm_img = dw.embed(host, bits, DELTA, KEY)
        cv2.imwrite(f"{RES_DIR}/{name}_watermarked.png", wm_img)
        p, s = mt.psnr(host, wm_img), mt.ssim(host, wm_img)
        b0 = mt.ber(bits, dw.extract(wm_img, n_bits, DELTA, KEY))
        rows.append(dict(Citra=name, Serangan="Tanpa serangan", PSNR=p, SSIM=s, BER=b0))

        for aname, fn in attack_list:
            att = fn(wm_img)
            ext = dw.extract(att, n_bits, DELTA, KEY)
            rows.append(dict(Citra=name, Serangan=aname, PSNR=mt.psnr(host, att),
                             SSIM=mt.ssim(host, att), BER=mt.ber(bits, ext)))
            if name == os.path.splitext(os.path.basename(sorted(glob.glob(f'{ORIG_DIR}/*'))[0]))[0]:
                demo = demo or {}
                demo[aname] = dw.bits_to_image(ext, WM_SIZE)
        if demo is not None and "host" not in demo:
            demo.update(host=host, wm=wm_img)

    df = pd.DataFrame(rows)
    df.round(4).to_csv(f"{RES_DIR}/hasil_uji.csv", index=False)

    imper = df[df.Serangan == "Tanpa serangan"][["Citra", "PSNR", "SSIM", "BER"]]
    print("\n=== IMPERCEPTIBILITY (tanpa serangan) ===")
    print(imper.round(4).to_string(index=False))
    rob = df[df.Serangan != "Tanpa serangan"].pivot(index="Serangan", columns="Citra", values="BER")
    rob["Rata-rata BER (%)"] = rob.mean(axis=1)
    order = [a for a, _ in attack_list]
    rob = rob.loc[order]
    print("\n=== ROBUSTNESS: BER (%) ===")
    print(rob.round(2).to_string())
    rob.round(3).to_csv(f"{RES_DIR}/robustness_ber.csv")

    # grafik BER
    fig, ax = plt.subplots(figsize=(9, 4.5))
    rob["Rata-rata BER (%)"].plot(kind="bar", ax=ax, color="#3b7dd8")
    ax.set_ylabel("BER (%)"); ax.set_title("Ketahanan Watermark terhadap Serangan (rata-rata)")
    plt.xticks(rotation=35, ha="right"); plt.tight_layout()
    plt.savefig(f"{RES_DIR}/grafik_ber.png", dpi=150); plt.close()

    # panel visual
    if demo:
        keys = ["JPEG Q=50", "Crop 25%", "Resize 0.5x"]
        fig, axs = plt.subplots(2, 3, figsize=(10, 7))
        axs[0, 0].imshow(cv2.cvtColor(demo["host"], cv2.COLOR_BGR2RGB)); axs[0, 0].set_title("Citra asli")
        axs[0, 1].imshow(cv2.cvtColor(demo["wm"], cv2.COLOR_BGR2RGB)); axs[0, 1].set_title("Ber-watermark")
        axs[0, 2].imshow(bits_img := dw.bits_to_image(bits, WM_SIZE), cmap="gray"); axs[0, 2].set_title("Watermark asli")
        for ax, k in zip(axs[1], keys):
            ax.imshow(demo[k], cmap="gray"); ax.set_title(f"Ekstraksi: {k}")
        for ax in axs.flat: ax.axis("off")
        plt.tight_layout(); plt.savefig(f"{RES_DIR}/panel_visual.png", dpi=130); plt.close()

    print(f"\nHasil tersimpan di folder '{RES_DIR}/'")


if __name__ == "__main__":
    main()
