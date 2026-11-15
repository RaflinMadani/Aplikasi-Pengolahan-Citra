# Folder `data/`

Letakkan citra di sini (jpg/png). Subfolder di dalamnya boleh.

```
data/train/   -> ~10.000 citra (latih)
data/val/     -> ~1.000 citra (validasi & uji) -- TIDAK boleh sama dengan train
```

Sumber data & cara menyiapkannya: lihat bagian **"Data yang Dibutuhkan"** di `README.md` utama.
Cara cepat: `python -m utils.prepare_data --source <folder_gambar_mentah>`
