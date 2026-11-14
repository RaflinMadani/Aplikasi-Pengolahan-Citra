"""Penyimpanan riwayat per sesi (berbasis berkas, tanpa database)."""
import json
import os
import re
import shutil
import threading
import time
import uuid

import cv2

SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
ID_RE = re.compile(r"^[a-f0-9]{12}$")
FILE_RE = re.compile(r"^[a-z0-9_]{1,32}\.png$")


class SessionStore:
    def __init__(self, root, max_items=100):
        self.root = os.path.abspath(root)
        self.max_items = max_items
        self._lock = threading.RLock()
        os.makedirs(self.root, exist_ok=True)

    # ---- path helpers (semua input divalidasi -> aman dari path traversal)
    def _sdir(self, sid):
        if not SID_RE.match(sid or ""):
            raise ValueError("Session ID tidak valid.")
        return os.path.join(self.root, sid)

    def _index(self, sid):
        return os.path.join(self._sdir(sid), "items.json")

    def _load(self, sid):
        p = self._index(sid)
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, sid, items):
        os.makedirs(self._sdir(sid), exist_ok=True)
        tmp = self._index(sid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
        os.replace(tmp, self._index(sid))

    # ---- operasi
    def add(self, sid, kind, title, data, images, thumb_from):
        with self._lock:
            item_id = uuid.uuid4().hex[:12]
            d = os.path.join(self._sdir(sid), item_id)
            os.makedirs(d, exist_ok=True)
            images = dict(images)
            src = images[thumb_from]
            scale = 320.0 / max(src.shape[:2])
            images["thumb"] = cv2.resize(src, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else src
            for name, img in images.items():
                if not cv2.imwrite(os.path.join(d, f"{name}.png"), img):
                    raise IOError(f"Gagal menyimpan {name}.png")
            item = {"id": item_id, "kind": kind, "title": title, "created_at": time.time(),
                    "files": sorted(images.keys()), **data}
            items = self._load(sid)
            items.insert(0, item)
            for old in items[self.max_items:]:
                shutil.rmtree(os.path.join(self._sdir(sid), old["id"]), ignore_errors=True)
            self._save(sid, items[:self.max_items])
            return item

    def list(self, sid):
        with self._lock:
            return self._load(sid)

    def get(self, sid, item_id):
        if not ID_RE.match(item_id or ""):
            return None
        return next((i for i in self.list(sid) if i["id"] == item_id), None)

    def path(self, sid, item_id, name):
        if not (ID_RE.match(item_id or "") and FILE_RE.match(name or "")):
            return None
        p = os.path.join(self._sdir(sid), item_id, name)
        return p if os.path.isfile(p) else None

    def read_image(self, sid, item_id, name):
        p = self.path(sid, item_id, name)
        return cv2.imread(p, cv2.IMREAD_COLOR) if p else None

    def delete(self, sid, item_id):
        with self._lock:
            items = self._load(sid)
            keep = [i for i in items if i["id"] != item_id]
            if len(keep) == len(items):
                return False
            shutil.rmtree(os.path.join(self._sdir(sid), item_id), ignore_errors=True)
            self._save(sid, keep)
            return True

    def clear(self, sid):
        with self._lock:
            shutil.rmtree(self._sdir(sid), ignore_errors=True)
