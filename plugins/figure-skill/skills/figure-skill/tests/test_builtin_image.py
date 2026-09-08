from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from adapters.builtin_image_adapter import import_image


class BuiltinImageTests(unittest.TestCase):
    def fixture(self, root):
        image = root / "tool-output.png"
        Image.new("RGBA", (400, 300), (255, 255, 255, 0)).save(image)
        prompt = root / "prompt.txt"
        prompt.write_text("Conceptual encoder, no visible text.", encoding="utf-8")
        plan = {"route": "raster-illustration", "review_status": "approved", "open_questions": [],
                "constraints": {"forbid_invented_quantitative_claims": True},
                "panels": [{"id": "A", "type": "raster-illustration", "evidence_role": "illustrative",
                            "canvas": {"width": 400, "height": 300}, "entities": ["Encoder"],
                            "visible_labels": ["Conceptual illustration"],
                            "annotation_spec": {"mode": "deterministic-overlay", "allow_same_aspect_resize": True,
                                                "title": {"text": "Conceptual illustration", "position": [0.5, 0.1]}}}]}
        return plan, image, prompt

    def test_import_is_local_preserves_alpha_and_records_unknown_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, image, prompt = self.fixture(root)
            with patch("urllib.request.urlopen", side_effect=AssertionError("No network allowed")):
                record = import_image(plan, image, prompt, root / "panels")
            self.assertEqual(image.read_bytes(), Path(record["output"]).read_bytes())
            self.assertIsNone(record["model"])
            self.assertTrue(record["human_review_required"])
            with Image.open(record["output"]) as imported:
                self.assertEqual(imported.mode, "RGBA")
            manifest = json.loads((root / "panels/raster-illustration-request.json").read_text())
            self.assertEqual(manifest["prompt"], prompt.read_text())
            self.assertNotIn("credential_environment", manifest)

    def test_bad_aspect_or_unapproved_plan_fails_before_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, image, prompt = self.fixture(root)
            plan["open_questions"] = ["Confirm entities"]
            with self.assertRaises(ValueError):
                import_image(plan, image, prompt, root / "panels")
            plan["open_questions"] = []
            plan["panels"][0]["canvas"]["width"] = 300
            with self.assertRaises(ValueError):
                import_image(plan, image, prompt, root / "panels")
            self.assertFalse((root / "panels").exists())

    def test_same_aspect_resize_requires_plan_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, image, prompt = self.fixture(root)
            plan["panels"][0]["canvas"] = {"width": 800, "height": 600}
            plan["panels"][0]["annotation_spec"]["allow_same_aspect_resize"] = False
            with self.assertRaises(ValueError):
                import_image(plan, image, prompt, root / "panels")

    def test_workflow_imports_without_key_and_reaches_pending_review(self):
        from assemble_figure import find_browser
        if find_browser() is None:
            self.skipTest("Local browser needed for annotation")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, image, prompt = self.fixture(root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            environment = {key: value for key, value in os.environ.items() if "API_KEY" not in key}
            environment.update({"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1"})
            result = subprocess.run([sys.executable, str(SCRIPTS / "run_workflow.py"), "--plan", str(plan_path),
                                     "--output", str(root / "output"), "--approve-plan", "--builtin-image", str(image),
                                     "--builtin-prompt", str(prompt)], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            qa = json.loads((root / "output/reports/qa-report.json").read_text())
            self.assertNotEqual(qa["technical_status"], "fail", qa)
            self.assertEqual(qa["human_review_status"], "pending")
            self.assertEqual(qa["status"], "warn")
            record = json.loads((root / "output/provenance/generation-provenance.json").read_text())
            self.assertEqual(record["provider_protocol"], "codex-image-gen")
            self.assertTrue((root / "output/final/figure.png").is_file())


if __name__ == "__main__":
    unittest.main()
