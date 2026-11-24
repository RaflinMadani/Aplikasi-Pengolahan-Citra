import unittest

import cv2
import numpy as np

from src import attacks as atk
from src import codec
from src import dwt_watermark as dw
from src import metrics as mt


def host(h=256, w=256, seed=1):
    rng = np.random.RandomState(seed)
    return cv2.GaussianBlur(rng.randint(0, 255, (h, w, 3), np.uint8), (0, 0), 4)


class CoreTest(unittest.TestCase):
    def test_haar_perfect_reconstruction(self):
        x = np.random.RandomState(0).rand(64, 64) * 255
        self.assertTrue(np.allclose(dw.idwt2(dw.dwt2(x)), x))

    def test_text_codec(self):
        b = codec.text_to_bits("Hak Cipta ©")
        self.assertEqual(len(b), codec.TEXT_BITS)
        self.assertEqual(codec.bits_to_text(b), "Hak Cipta ©")
        with self.assertRaises(ValueError):
            codec.text_to_bits("x" * 40)

    def test_embed_extract_clean(self):
        bits = codec.default_logo_bits(16)
        for level in (1, 2):
            wm = dw.embed(host(), bits, 30, 5, "haar", level)
            self.assertEqual(mt.ber(bits, dw.extract(wm, len(bits), 30, 5, "haar", level)), 0)
            self.assertGreater(mt.psnr(host(), wm), 30)

    def test_wrong_key_gives_random_ber(self):
        bits = codec.default_logo_bits(32)
        wm = dw.embed(host(512, 512), bits, 36, 1)
        self.assertGreater(mt.ber(bits, dw.extract(wm, len(bits), 36, 2)), 30)

    def test_attacks_shapes(self):
        im = host()
        self.assertEqual(atk.resize_attack(im, 0.5).shape, im.shape)
        self.assertEqual(atk.jpeg_compress(im, 50).shape, im.shape)
        c = atk.crop(im, 25)
        self.assertAlmostEqual((c == 0).all(axis=2).mean(), 0.25, delta=0.01)
        with self.assertRaises(ValueError):
            atk.apply_step(im, {"type": "jpeg", "quality": 500})

    def test_size_validation(self):
        with self.assertRaises(ValueError):
            dw.embed(host(250, 250), np.ones(64, np.uint8), 30, 1, "haar", 2)


if __name__ == "__main__":
    unittest.main()
