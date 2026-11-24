import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    HOST = os.environ.get("WM_HOST", "127.0.0.1")
    PORT = int(os.environ.get("WM_PORT", "5000"))
    DEBUG = os.environ.get("WM_DEBUG", "0") == "1"
    STORAGE_DIR = os.environ.get("WM_STORAGE_DIR", os.path.join(BASE_DIR, "storage"))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024      # batas unggahan 16 MB
    MAX_SIDE = 1024                            # sisi terpanjang citra diproses (px)
    MIN_SIDE = 128                             # ukuran minimum citra (px)
    MAX_HISTORY = 100                          # item riwayat per sesi
