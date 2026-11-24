"""REST API dashboard watermarking DWT."""
import json
import statistics

import cv2
import numpy as np
from flask import Blueprint, Response, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from src import attacks as atk
from src import codec
from src import dwt_watermark as dw
from src import metrics as mt
from .storage import SID_RE

bp = Blueprint("api", __name__, url_prefix="/api")

WM_SIZES = (16, 24, 32, 48, 64)
PRESET_ATTACKS = (
    [{"type": "jpeg", "quality": q} for q in (90, 70, 50, 30, 10)]
    + [{"type": "crop", "percent": p, "position": "br"} for p in (10, 25, 50)]
    + [{"type": "resize", "scale": s} for s in (0.75, 0.5)]
    + [{"type": "noise", "sigma": s} for s in (5, 10, 20)]
)


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


@bp.errorhandler(ApiError)
def _api_error(e):
    return jsonify(error=e.message), e.status


# ------------------------------------------------------------ helpers ---
def store():
    return current_app.extensions["wm_store"]


def sid():
    s = request.headers.get("X-Session-Id") or request.args.get("sid")
    if not s or not SID_RE.match(s):
        raise ApiError("Session ID tidak valid. Muat ulang halaman.")
    return s


def _f(x, nd=4):
    x = float(x)
    return 100.0 if x == float("inf") else round(x, nd)


def _int(v, name, lo, hi, default=None):
    try:
        x = int(default if v in (None, "") else v)
    except (TypeError, ValueError):
        raise ApiError(f"{name} tidak valid.")
    if not lo <= x <= hi:
        raise ApiError(f"{name} harus di antara {lo} dan {hi}.")
    return x


def _float(v, name, lo, hi, default):
    try:
        x = float(default if v in (None, "") else v)
    except (TypeError, ValueError):
        raise ApiError(f"{name} tidak valid.")
    if not lo <= x <= hi:
        raise ApiError(f"{name} harus di antara {lo} dan {hi}.")
    return x


def view(item):
    v = {k: val for k, val in item.items() if k != "bits"}
    s = sid()
    v["urls"] = {n: f"/api/files/{item['id']}/{n}.png?sid={s}" for n in item["files"]}
    return v


def get_item(item_id, kinds=None):
    item = store().get(sid(), item_id) if item_id else None
    if item is None:
        raise ApiError("Item riwayat tidak ditemukan atau sudah dihapus.", 404)
    if kinds and item["kind"] not in kinds:
        raise ApiError("Jenis item riwayat tidak sesuai untuk operasi ini.")
    return item


def read_upload(field, required=True):
    f = request.files.get(field)
    if f is None or not f.filename:
        if required:
            raise ApiError("Citra belum dipilih.")
        return None, None
    img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ApiError("File bukan citra yang valid. Gunakan PNG atau JPG.")
    return img, secure_filename(f.filename)


def fit_cover(img):
    cfg, notes = current_app.config, []
    h, w = img.shape[:2]
    if max(h, w) > cfg["MAX_SIDE"]:
        s = cfg["MAX_SIDE"] / max(h, w)
        img = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
        notes.append(f"Citra diperkecil dari {w}×{h} ke {img.shape[1]}×{img.shape[0]} px.")
    h, w = img.shape[:2]
    h8, w8 = h - h % 8, w - w % 8
    if min(h8, w8) < cfg["MIN_SIDE"]:
        raise ApiError(f"Citra terlalu kecil. Minimal {cfg['MIN_SIDE']} px pada sisi terpendek.")
    if (h8, w8) != (h, w):
        notes.append(f"Tepi citra dipangkas ke {w8}×{h8} px (kelipatan 8).")
    return img[:h8, :w8], notes


def parse_params(src):
    wavelet = str(src.get("wavelet", "haar")).lower()
    if wavelet not in dw.available_wavelets():
        raise ApiError(f"Wavelet '{wavelet}' tidak tersedia. Untuk Db4 jalankan: pip install PyWavelets")
    return {
        "wavelet": wavelet,
        "level": _int(src.get("level"), "Level dekomposisi", 1, 2, 2),
        "delta": _float(src.get("delta"), "Alpha (Δ)", 4, 150, 36),
        "key": _int(src.get("key"), "Kunci", 0, 2 ** 31 - 1, 2024),
    }


def bits_from_str(s):
    return np.array([int(c) for c in s], dtype=np.uint8)


def describe_bits(bits, wm_type):
    if wm_type == "text":
        return {"type": "text", "text": codec.bits_to_text(bits)}
    if wm_type == "binary":
        return {"type": "binary", "binary": codec.bits_to_string(bits)}
    return {"type": "image"}


def wm_images(bits, cfg, prefix_orig=None, ext_bits=None):
    out = {}
    if cfg["wm_type"] == "image":
        if bits is not None:
            out["wm_original"] = codec.bits_to_image(bits, cfg["wm_size"])
        if ext_bits is not None:
            out["wm_extracted"] = codec.bits_to_image(ext_bits, cfg["wm_size"])
    return out


def clean_steps(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 6:
        raise ApiError("Pilih 1–6 serangan.")
    allowed = {"jpeg": ("quality",), "crop": ("percent", "position"),
               "crop_rect": ("x", "y", "w", "h"), "resize": ("scale",), "noise": ("sigma",)}
    out = []
    for s in raw:
        t = s.get("type") if isinstance(s, dict) else None
        if t not in allowed:
            raise ApiError(f"Jenis serangan '{t}' tidak dikenal.")
        step = {"type": t}
        for k in allowed[t]:
            if k in s:
                step[k] = s[k] if k == "position" else float(s[k])
        if t == "crop_rect" and (step.get("w", 0) <= 0 or step.get("h", 0) <= 0):
            raise ApiError("Area crop belum dipilih. Seret pada citra untuk memilih area.")
        out.append(step)
    return out


def prepare_for_extraction(img, level, ref_w, ref_h, notes):
    h, w = img.shape[:2]
    if ref_w and ref_h and (w, h) != (ref_w, ref_h):
        img = cv2.resize(img, (ref_w, ref_h), interpolation=cv2.INTER_LINEAR)
        notes.append(f"Ukuran citra {w}×{h} disesuaikan ke {ref_w}×{ref_h} px (ukuran saat penyisipan).")
    h, w = img.shape[:2]
    m = 2 ** level
    if h % m or w % m:
        img = img[:h - h % m, :w - w % m]
        notes.append(f"Tepi citra dipangkas agar kelipatan {m}; posisi koefisien dapat bergeser.")
    return img


def run_extract(img, cfg):
    if dw.capacity(img.shape, cfg["level"], cfg["n_bits"]) < 1:
        raise ApiError("Citra terlalu kecil untuk jumlah bit watermark ini.")
    return dw.extract(img, cfg["n_bits"], cfg["delta"], cfg["key"], cfg["wavelet"], cfg["level"])


def ber_metrics(orig_bits, ext_bits):
    return {"ber": _f(mt.ber(orig_bits, ext_bits), 3), "bit_errors": mt.bit_errors(orig_bits, ext_bits),
            "n_bits": int(len(orig_bits))}


# ------------------------------------------------------------- routes ---
@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.get("/options")
def options():
    c = current_app.config
    return jsonify(wavelets=dw.available_wavelets(), has_pywt=dw.HAS_PYWT, levels=[1, 2],
                   wm_sizes=list(WM_SIZES), text_bytes=codec.TEXT_BYTES,
                   binary_bits=[codec.MIN_BINARY_BITS, codec.MAX_BINARY_BITS],
                   delta={"min": 8, "max": 80, "default": 36}, max_side=c["MAX_SIDE"])


@bp.get("/stats")
def stats():
    items = store().list(sid())
    embeds = [i for i in items if i["kind"] == "embed"]
    psnrs = [i["metrics"]["psnr"] for i in embeds]
    bers = [i["metrics"]["ber"] for i in items if i["kind"] in ("extract", "attack")
            and i.get("metrics", {}).get("ber") is not None]
    return jsonify(
        total=len(items),
        counts={k: sum(1 for i in items if i["kind"] == k) for k in ("embed", "extract", "attack")},
        avg_psnr=_f(statistics.mean(psnrs), 2) if psnrs else None,
        avg_ber=_f(statistics.mean(bers), 2) if bers else None,
        recent=[view(i) for i in items[:4]])


@bp.post("/embed")
def embed_route():
    s, form = sid(), request.form
    reuse = get_item(form.get("reuse_id"), ("embed",)) if form.get("reuse_id") else None

    cover, fname = read_upload("cover", required=False)
    if cover is None:
        if not reuse:
            raise ApiError("Unggah citra asli (cover) terlebih dahulu.")
        cover = store().read_image(s, reuse["id"], "cover.png")
        if cover is None:
            raise ApiError("Citra asli dari riwayat tidak ditemukan.", 404)
        fname = "citra riwayat"
    p = parse_params(form)
    cover, notes = fit_cover(cover)

    wm_type = form.get("wm_type", "image")
    wm_size, text = 0, None
    try:
        if wm_type == "image":
            wm_size = _int(form.get("wm_size"), "Ukuran watermark", 16, 64, 32)
            if wm_size not in WM_SIZES:
                raise ApiError(f"Ukuran watermark harus salah satu dari {WM_SIZES}.")
            up, _ = read_upload("wm_image", required=False)
            if up is not None:
                bits = codec.image_to_bits(up, wm_size)
            elif reuse and reuse["config"]["wm_type"] == "image" and reuse["config"]["wm_size"] == wm_size:
                bits = bits_from_str(reuse["bits"])
            else:
                bits = codec.default_logo_bits(wm_size)
                notes.append("Logo watermark tidak diunggah; memakai logo bawaan 'DWT'.")
        elif wm_type == "text":
            text = form.get("wm_text", "")
            bits = codec.text_to_bits(text)
        elif wm_type == "binary":
            bits = codec.binary_string_to_bits(form.get("wm_binary", ""))
        else:
            raise ApiError("Jenis watermark tidak dikenal.")
    except ValueError as e:
        raise ApiError(str(e))

    h, w = cover.shape[:2]
    if dw.capacity(cover.shape, p["level"], len(bits)) < 1:
        raise ApiError("Citra terlalu kecil untuk jumlah bit watermark ini. Kecilkan watermark atau pakai citra lebih besar.")

    wm = dw.embed(cover, bits, p["delta"], p["key"], p["wavelet"], p["level"])
    cfg = {**p, "wm_type": wm_type, "wm_size": wm_size, "n_bits": int(len(bits)), "width": w, "height": h,
           "redundancy": int(dw.capacity(cover.shape, p["level"], len(bits)))}
    ext = dw.extract(wm, cfg["n_bits"], p["delta"], p["key"], p["wavelet"], p["level"])

    diff = np.clip(np.abs(cover.astype(np.int16) - wm.astype(np.int16)).max(axis=2) * 20, 0, 255).astype(np.uint8)
    metrics = {"psnr": _f(mt.psnr(cover, wm), 2), "ssim": _f(mt.ssim(cover, wm)), **ber_metrics(bits, ext)}
    images = {"cover": cover, "watermarked": wm, "diff": diff, **wm_images(bits, cfg, ext_bits=ext)}
    title = f"{(fname or 'citra')[:40]} · {p['wavelet']} L{p['level']} Δ{p['delta']:g}"
    item = store().add(s, "embed", title, {
        "config": cfg, "bits": codec.bits_to_string(bits), "wm_text": text,
        "wm_binary": codec.bits_to_string(bits) if wm_type == "binary" else None, "metrics": metrics,
        "extracted": describe_bits(ext, wm_type), "notes": notes}, images, "watermarked")
    return jsonify(item=view(item))


@bp.post("/extract")
def extract_route():
    s, form = sid(), request.form
    notes = []
    ref = get_item(form.get("ref_id"), ("embed", "attack")) if form.get("ref_id") else None

    img, fname = read_upload("image", required=False)
    if img is None:
        if not ref:
            raise ApiError("Unggah citra uji atau pilih item dari riwayat.")
        name = "attacked.png" if ref["kind"] == "attack" else "watermarked.png"
        img = store().read_image(s, ref["id"], name)
        if img is None:
            raise ApiError("Citra dari riwayat tidak ditemukan.", 404)
        fname = ref["title"]

    if ref:
        cfg = dict(ref["config"])
        orig_bits = bits_from_str(ref["bits"])
        ref_w, ref_h = cfg["width"], cfg["height"]
    else:
        p = parse_params(form)
        t = form.get("wm_type", "image")
        size, orig_bits = 0, None
        try:
            if t == "image":
                size = _int(form.get("wm_size"), "Ukuran watermark", 16, 64, 32)
                n = size * size
                up, _ = read_upload("exp_image", required=False)
                orig_bits = codec.image_to_bits(up, size) if up is not None else None
            elif t == "text":
                n = codec.TEXT_BITS
                if form.get("exp_text"):
                    orig_bits = codec.text_to_bits(form["exp_text"])
            elif t == "binary":
                if form.get("exp_binary", "").strip():
                    orig_bits = codec.binary_string_to_bits(form["exp_binary"])
                    n = len(orig_bits)
                else:
                    n = _int(form.get("wm_bits"), "Jumlah bit", codec.MIN_BINARY_BITS, codec.MAX_BINARY_BITS, 64)
            else:
                raise ApiError("Jenis watermark tidak dikenal.")
        except ValueError as e:
            raise ApiError(str(e))
        cfg = {**p, "wm_type": t, "wm_size": size, "n_bits": int(n)}
        ref_w = _int(form.get("ref_w"), "Lebar referensi", 8, 8192, 0) if form.get("ref_w") else 0
        ref_h = _int(form.get("ref_h"), "Tinggi referensi", 8, 8192, 0) if form.get("ref_h") else 0
        cfg["width"], cfg["height"] = img.shape[1], img.shape[0]

    img = prepare_for_extraction(img, cfg["level"], ref_w, ref_h, notes)
    ext = run_extract(img, cfg)
    metrics = ber_metrics(orig_bits, ext) if orig_bits is not None else {"ber": None, "n_bits": cfg["n_bits"]}
    if orig_bits is None:
        notes.append("Watermark asli tidak diberikan, sehingga BER tidak dapat dihitung.")

    extra = {}
    if cfg["wm_type"] == "image":
        extra["wm_extracted"] = codec.bits_to_image(ext, cfg["wm_size"])
        if orig_bits is not None:
            extra["wm_original"] = codec.bits_to_image(orig_bits, cfg["wm_size"])
    item = store().add(s, "extract", f"Ekstraksi · {(fname or 'citra')[:40]}", {
        "config": cfg, "metrics": metrics, "ref_id": ref["id"] if ref else None,
        "extracted": describe_bits(ext, cfg["wm_type"]),
        "expected": describe_bits(orig_bits, cfg["wm_type"]) if orig_bits is not None else None,
        "notes": notes}, {"input": img, **extra}, "input")
    return jsonify(item=view(item))


@bp.post("/attack")
def attack_route():
    s, body = sid(), request.get_json(silent=True) or {}
    ref = get_item(body.get("ref_id"), ("embed",))
    steps = clean_steps(body.get("attacks"))
    wm = store().read_image(s, ref["id"], "watermarked.png")
    cover = store().read_image(s, ref["id"], "cover.png")
    if wm is None or cover is None:
        raise ApiError("Berkas citra dari riwayat tidak ditemukan.", 404)
    try:
        attacked = atk.apply_chain(wm, steps)
    except ValueError as e:
        raise ApiError(str(e))

    cfg, bits = dict(ref["config"]), bits_from_str(ref["bits"])
    ext = run_extract(attacked, cfg)
    metrics = {"psnr": _f(mt.psnr(cover, attacked), 2), "ssim": _f(mt.ssim(cover, attacked)),
               **ber_metrics(bits, ext)}
    title = " + ".join(atk.describe(x) for x in steps)
    item = store().add(s, "attack", title, {
        "config": cfg, "bits": ref["bits"], "wm_text": ref.get("wm_text"), "wm_binary": ref.get("wm_binary"),
        "ref_id": ref["id"],
        "attacks": steps, "metrics": metrics, "extracted": describe_bits(ext, cfg["wm_type"])},
        {"attacked": attacked, **wm_images(bits, cfg, ext_bits=ext)}, "attacked")
    return jsonify(item=view(item))


@bp.post("/benchmark")
def benchmark_route():
    s, body = sid(), request.get_json(silent=True) or {}
    ref = get_item(body.get("ref_id"), ("embed",))
    wm = store().read_image(s, ref["id"], "watermarked.png")
    cover = store().read_image(s, ref["id"], "cover.png")
    if wm is None or cover is None:
        raise ApiError("Berkas citra dari riwayat tidak ditemukan.", 404)
    cfg, bits = dict(ref["config"]), bits_from_str(ref["bits"])
    rows = []
    for step in PRESET_ATTACKS:
        att = atk.apply_step(wm, step)
        ext = run_extract(att, cfg)
        rows.append({"name": atk.describe(step), "type": step["type"], "psnr": _f(mt.psnr(cover, att), 2),
                     "ssim": _f(mt.ssim(cover, att)), "ber": _f(mt.ber(bits, ext), 3)})
    return jsonify(rows=rows)


@bp.get("/history")
def history():
    return jsonify(items=[view(i) for i in store().list(sid())])


@bp.get("/history/<item_id>")
def history_item(item_id):
    return jsonify(item=view(get_item(item_id)))


@bp.delete("/history/<item_id>")
def history_delete(item_id):
    if not store().delete(sid(), item_id):
        raise ApiError("Item tidak ditemukan.", 404)
    return jsonify(ok=True)


@bp.delete("/history")
def history_clear():
    store().clear(sid())
    return jsonify(ok=True)


@bp.get("/history/<item_id>/config")
def history_config(item_id):
    item = get_item(item_id)
    payload = {"tool": "dwt-watermark-dashboard", "kind": item["kind"], "config": item["config"],
               "catatan": "Parameter ini wajib sama saat ekstraksi. Simpan dengan aman."}
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=kunci_{item_id}.json"})


@bp.get("/files/<item_id>/<name>")
def files(item_id, name):
    path = store().path(sid(), item_id, name)
    if not path:
        raise ApiError("Berkas tidak ditemukan.", 404)
    return send_file(path, mimetype="image/png", as_attachment=bool(request.args.get("download")),
                     download_name=f"{item_id}_{name}")
