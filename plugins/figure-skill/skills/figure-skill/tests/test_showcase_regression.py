from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO = Path(__file__).resolve().parents[5]


def load():
    path = REPO / "scripts" / "verify_showcase.py"; spec = importlib.util.spec_from_file_location("showcase_regression_test", path); module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module); return module


class ShowcaseRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.verifier = load()

    def test_identical_and_small_noise_pass_but_shift_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); baseline = root / "baseline.png"; identical = root / "identical.png"; noisy = root / "noisy.png"; shifted = root / "shifted.png"
            image = Image.new("RGB", (128, 96), "white")
            for x in range(30, 90):
                for y in range(25, 70): image.putpixel((x, y), (40, 80, 160))
            image.save(baseline); image.save(identical)
            noise = image.copy(); noise.putpixel((31, 26), (41, 81, 161)); noise.save(noisy)
            moved = Image.new("RGB", image.size, "white"); moved.paste(image.crop((30, 25, 90, 70)), (50, 25)); moved.save(shifted)
            thresholds = {"max_dhash_distance": 6, "max_thumbnail_rmse": 0.035, "max_changed_pixel_ratio": 0.08}
            self.assertTrue(self.verifier.compare_thresholds(self.verifier.visual_metrics(baseline, identical, root / "same-diff.png"), thresholds)[0])
            self.assertTrue(self.verifier.compare_thresholds(self.verifier.visual_metrics(baseline, noisy, root / "noise-diff.png"), thresholds)[0])
            self.assertFalse(self.verifier.compare_thresholds(self.verifier.visual_metrics(baseline, shifted, root / "shift-diff.png"), thresholds)[0])

    def test_offline_environment_removes_credentials_and_blocks_proxy(self):
        previous = os.environ.get("FIGURE_IMAGE_API_KEY"); os.environ["FIGURE_IMAGE_API_KEY"] = "secret"
        try:
            environment = self.verifier.safe_environment(); self.assertNotIn("FIGURE_IMAGE_API_KEY", environment); self.assertEqual(environment["FIGURE_SHOWCASE_OFFLINE"], "1"); self.assertEqual(environment["HTTP_PROXY"], "http://127.0.0.1:9")
        finally:
            if previous is None: os.environ.pop("FIGURE_IMAGE_API_KEY", None)
            else: os.environ["FIGURE_IMAGE_API_KEY"] = previous

    def test_structural_assertions_detect_missing_text_and_raster(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root / "out"; output.mkdir(); (output / "figure.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="x"/><text>Wrong</text></svg>', encoding="utf-8")
            checks = self.verifier.structural_checks(root, output, {"expected_artifacts": ["figure.svg"], "structural_assertions": {"svg": "figure.svg", "forbid_embedded_images": True, "required_text": ["Expected"]}})
            self.assertTrue(any(item["check"] == "svg-no-image" and item["status"] == "fail" for item in checks)); self.assertTrue(any(item["check"] == "svg-text:Expected" and item["status"] == "fail" for item in checks))


if __name__ == "__main__": unittest.main()
