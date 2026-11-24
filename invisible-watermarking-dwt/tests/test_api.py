import io
import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from webapp import create_app

SID = "testsession0001"


def png_bytes(seed=0, size=(384, 512)):
    rng = np.random.RandomState(seed)
    base = cv2.GaussianBlur(rng.randint(0, 255, (*size, 3), np.uint8), (0, 0), 5)
    base = cv2.addWeighted(base, 1.6, np.full_like(base, 20), 1, 0)
    ok, buf = cv2.imencode(".png", base)
    return io.BytesIO(buf.tobytes())


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = create_app({"STORAGE_DIR": self.tmp, "TESTING": True})
        self.c = self.app.test_client()
        self.h = {"X-Session-Id": SID}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get_bytes(self, url):
        r = self.c.get(url)
        data = r.data
        r.close()
        return data

    def embed(self, **extra):
        data = {"cover": (png_bytes(), "a.png"), "wm_type": "image", "wm_size": "32",
                "wavelet": "haar", "level": "2", "delta": "36", "key": "7", **extra}
        return self.c.post("/api/embed", data=data, headers=self.h, content_type="multipart/form-data")

    def test_full_flow_image(self):
        r = self.embed()
        self.assertEqual(r.status_code, 200, r.get_json())
        item = r.get_json()["item"]
        self.assertGreater(item["metrics"]["psnr"], 35)
        self.assertEqual(item["metrics"]["ber"], 0)
        self.assertIn("watermarked", item["urls"])
        img = self.c.get(item["urls"]["watermarked"])
        self.assertEqual(img.status_code, 200)
        img.close()

        a = self.c.post("/api/attack", json={"ref_id": item["id"], "attacks": [{"type": "jpeg", "quality": 70}]},
                        headers=self.h)
        self.assertEqual(a.status_code, 200, a.get_json())
        self.assertLess(a.get_json()["item"]["metrics"]["ber"], 5)

        e = self.c.post("/api/extract", data={"ref_id": item["id"]}, headers=self.h,
                        content_type="multipart/form-data")
        self.assertEqual(e.get_json()["item"]["metrics"]["ber"], 0)

        st = self.c.get("/api/stats", headers=self.h).get_json()
        self.assertEqual(st["total"], 3)
        self.assertEqual(self.c.get("/api/history", headers=self.h).get_json()["items"][0]["kind"], "extract")

        b = self.c.post("/api/benchmark", json={"ref_id": item["id"]}, headers=self.h)
        self.assertEqual(len(b.get_json()["rows"]), 13)

        d = self.c.delete(f"/api/history/{item['id']}", headers=self.h)
        self.assertEqual(d.status_code, 200)

    def test_text_roundtrip_manual_extract(self):
        r = self.embed(wm_type="text", wm_text="Hak Cipta Budi 2026")
        item = r.get_json()["item"]
        att = self.c.post("/api/attack", json={"ref_id": item["id"], "attacks": [{"type": "noise", "sigma": 5}]},
                          headers=self.h).get_json()["item"]
        self.assertEqual(att["extracted"]["text"], "Hak Cipta Budi 2026")
        img = self.get_bytes(att["urls"]["attacked"])
        e = self.c.post("/api/extract", headers=self.h, content_type="multipart/form-data", data={
            "image": (io.BytesIO(img), "x.png"), "wm_type": "text", "wavelet": "haar", "level": "2",
            "delta": "36", "key": "7", "exp_text": "Hak Cipta Budi 2026"})
        self.assertEqual(e.status_code, 200, e.get_json())
        self.assertEqual(e.get_json()["item"]["extracted"]["text"], "Hak Cipta Budi 2026")

    def test_wrong_key_fails_extraction(self):
        item = self.embed().get_json()["item"]
        img = self.get_bytes(item["urls"]["watermarked"])
        e = self.c.post("/api/extract", headers=self.h, content_type="multipart/form-data", data={
            "image": (io.BytesIO(img), "x.png"), "wm_type": "image", "wm_size": "32", "wavelet": "haar",
            "level": "2", "delta": "36", "key": "999"})
        self.assertEqual(e.status_code, 200)
        self.assertEqual(e.get_json()["item"]["metrics"]["ber"], None)

    def test_level1_and_binary(self):
        r = self.embed(level="1", wm_type="binary", wm_binary="10110011" * 8, delta="20")
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["item"]["metrics"]["ber"], 0)

    def test_validation_errors(self):
        self.assertEqual(self.embed(wm_type="text", wm_text="x" * 100).status_code, 400)
        self.assertEqual(self.embed(wm_type="binary", wm_binary="1021").status_code, 400)
        self.assertEqual(self.embed(delta="9999").status_code, 400)
        r = self.c.post("/api/embed", data={"wm_type": "image"}, headers=self.h)
        self.assertEqual(r.status_code, 400)
        bad = self.c.post("/api/embed", headers=self.h, content_type="multipart/form-data",
                          data={"cover": (io.BytesIO(b"bukan gambar"), "a.png")})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.c.get("/api/history").status_code, 400)  # tanpa session id

    def test_path_traversal_and_isolation(self):
        item = self.embed().get_json()["item"]
        self.assertEqual(self.c.get(f"/api/files/{item['id']}/..%2Fitems.json?sid={SID}").status_code, 404)
        other = {"X-Session-Id": "othersession0002"}
        self.assertEqual(self.c.get("/api/history", headers=other).get_json()["items"], [])
        self.assertEqual(self.c.get(item["urls"]["cover"].replace(SID, "othersession0002")).status_code, 404)

    def test_reuse_cover(self):
        item = self.embed().get_json()["item"]
        r = self.c.post("/api/embed", headers=self.h, content_type="multipart/form-data", data={
            "reuse_id": item["id"], "wm_type": "image", "wm_size": "32", "wavelet": "haar",
            "level": "2", "delta": "30", "key": "7"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertGreater(r.get_json()["item"]["metrics"]["psnr"], 35)

    def test_crop_rect_requires_area(self):
        item = self.embed().get_json()["item"]
        r = self.c.post("/api/attack", headers=self.h, json={"ref_id": item["id"], "attacks": [
            {"type": "crop_rect", "x": 0.5, "y": 0.5, "w": 0, "h": 0}]})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
