from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ImageHandler(BaseHTTPRequestHandler):
    authorization = None
    request_body = None

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        type(self).authorization = self.headers.get("Authorization")
        type(self).request_body = json.loads(self.rfile.read(length))
        buffer = BytesIO()
        Image.new("RGB", (400, 300), "white").save(buffer, format="PNG")
        payload = json.dumps({
            "data": [{"b64_json": base64.b64encode(buffer.getvalue()).decode("ascii")}]
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("x-request-id", "unit-test-request")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        return


class RasterIllustrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = load_module(
            "raster_illustration_adapter", SCRIPTS / "adapters" / "raster_illustration_adapter.py"
        )
        cls.annotation = load_module(
            "raster_annotation_backend", SCRIPTS / "backends" / "raster_annotation_backend.py"
        )
        cls.planner = load_module("raster_plan_figure", SCRIPTS / "plan_figure.py")
        cls.qa = load_module("raster_qa_figure", SCRIPTS / "qa_figure.py")
        cls.reviewer = load_module("review_generated_figure", SCRIPTS / "review_generated_figure.py")

    def plan(self, root: Path) -> dict:
        return {
            "route": "raster-illustration",
            "brief": "Create a 3D scientific illustration of an encoder flowing to a classifier.",
            "input_root": str(root),
            "review_status": "approved",
            "open_questions": [],
            "constraints": {
                "forbid_invented_quantitative_claims": True,
                "generated_content_must_be_labeled": True,
            },
            "panels": [{
                "id": "A", "type": "raster-illustration", "title": "3D method concept",
                "style": "3d-render", "evidence_role": "illustrative",
                "scientific_description": "The encoder flows to the classifier.",
                "entities": ["Encoder", "Classifier"],
                "edges": [{"from": "Encoder", "to": "Classifier", "meaning": "data-flow"}],
                "visible_labels": [
                    "3D Method Concept", "Encoder to Classifier", "Encoder", "Classifier",
                    "Data flow", "Low response", "High response", "Conceptual illustration"
                ],
                "annotation_spec": {
                    "mode": "deterministic-overlay", "allow_same_aspect_resize": True,
                    "title": {"text": "3D Method Concept", "position": [0.5, 0.08]},
                    "subtitle": {"text": "Encoder to Classifier", "position": [0.5, 0.15]},
                    "labels": [
                        {"text": "Encoder", "position": [0.25, 0.55], "anchor": [0.3, 0.5], "style": "pill"},
                        {"text": "Classifier", "position": [0.75, 0.55], "anchor": [0.7, 0.5], "style": "pill"}
                    ],
                    "arrows": [{"text": "Data flow", "from": [0.35, 0.78], "to": [0.65, 0.78]}],
                    "legend": {"position": [0.55, 0.9], "items": [
                        {"label": "Low response", "color": "#443399"},
                        {"label": "High response", "color": "#ddee33"}
                    ]},
                    "footer": {"text": "Conceptual illustration", "position": [0.5, 0.97]}
                },
                "forbidden_content": ["invented measurements"],
                "canvas": {"width": 400, "height": 300},
            }],
        }

    def test_planner_selects_raster_route_and_marks_generated_content(self):
        inventory = {
            "root": "C:/input",
            "category_counts": {"narrative": 1},
            "files": [{"path": "methods.txt", "text_preview": "The encoder flows to the classifier."}],
        }
        plan = self.planner.build_plan(inventory, "Create a 3D scientific illustration")
        self.assertEqual(plan["route"], "raster-illustration")
        self.assertEqual(plan["panels"][0]["style"], "3d-render")
        self.assertEqual(plan["panels"][0]["evidence_role"], "illustrative")
        self.assertEqual(plan["panels"][0]["canvas"], {"width": 1024, "height": 1024})
        self.assertTrue(plan["panels"][0]["visible_labels"])
        self.assertEqual(plan["panels"][0]["annotation_spec"]["mode"], "deterministic-overlay")
        self.assertFalse(plan["constraints"]["editable_source_required"])

    def test_manifest_is_redacted_and_key_is_environment_only(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(
            os.environ, {"FIGURE_IMAGE_API_KEY": ""}, clear=False
        ):
            root = Path(temp)
            plan = self.plan(root)
            request = self.adapter.prepare_request(
                plan, plan["panels"][0], root, "https://example.invalid/v1", "image-model",
                "1024x1024", "medium",
            )
            manifest = self.adapter.write_manifest(request, root)
            text = manifest.read_text(encoding="utf-8")
            self.assertNotIn("Bearer ", text)
            self.assertNotIn("Authorization", text)
            self.assertFalse(request["credential_available"])
            self.assertEqual(request["credential_environment"], "FIGURE_IMAGE_API_KEY")
            self.assertIn("no visible text", request["prompt"])
            self.assertNotIn("3D Method Concept", request["prompt"])

    def test_mock_generation_and_raster_qa_pass(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ImageHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                plan = self.plan(root)
                request = self.adapter.prepare_request(
                    plan, plan["panels"][0], root,
                    f"http://127.0.0.1:{server.server_port}/v1", "image-model",
                    "400x300", "medium", allow_insecure_http=True,
                )
                manifest = self.adapter.write_manifest(request, root)
                provenance = self.adapter.execute_request(request, "unit-test-key", allow_insecure_http=True)
                self.assertTrue(provenance["size_matches_request"])
                self.assertEqual(provenance["requested_size"], [400, 300])
                generation_path = root / "generation-provenance.json"
                generation_path.write_text(
                    json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.assertTrue((root / "panel_a.png").is_file())
                if self.annotation.browser_path() is None:
                    self.skipTest("Edge/Chrome is required for raster annotation integration")
                self.annotation.annotate(
                    plan, plan["panels"][0], root / "panel_a.png", root,
                    generation_path, root / "sources", root / "annotation-provenance.json",
                )
                self.assertTrue((root / "sources" / "panel_a_annotation.svg.txt").is_file())
                annotation = json.loads((root / "annotation-provenance.json").read_text(encoding="utf-8"))
                self.assertEqual(sorted(annotation["visible_labels"]), sorted(plan["panels"][0]["visible_labels"]))
                (root / "final").mkdir()
                shutil.copy2(root / "panel_a.png", root / "final" / "figure.png")
                self.assertEqual(ImageHandler.authorization, "Bearer unit-test-key")
                self.assertEqual(ImageHandler.request_body["model"], "image-model")
                self.assertNotIn("unit-test-key", manifest.read_text(encoding="utf-8"))
                plan_path = root / "figure-plan.json"
                plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
                pending = self.qa.run_qa(root, plan)
                self.assertEqual(pending["technical_status"], "pass", pending)
                self.assertEqual(pending["scientific_status"], "pending", pending)
                self.assertEqual(pending["human_review_status"], "pending", pending)
                self.assertEqual(pending["status"], "warn", pending)

                review = self.reviewer.prepare_review(plan_path, root / "panel_a.png")
                with self.assertRaisesRegex(ValueError, "passing scientific assessment"):
                    self.reviewer.apply_human_decision(
                        review, "approved", "unit-test-human", "Not assessed yet.", True
                    )
                results = [f"{item['id']}=pass" for item in review["scientific_assessment"]["assertions"]]
                review = self.reviewer.apply_assessment(review, results, "unit-test-agent")
                review_path = root / "scientific-review.json"
                self.reviewer.write_review(review, review_path)
                assessed = self.qa.run_qa(root, plan)
                self.assertEqual(assessed["scientific_status"], "pass", assessed)
                self.assertEqual(assessed["human_review_status"], "pending", assessed)
                self.assertEqual(assessed["status"], "warn", assessed)

                review = self.reviewer.apply_human_decision(
                    review, "approved", "unit-test-human", "Reviewed the generated image.", True
                )
                self.reviewer.write_review(review, review_path)
                approved = self.qa.run_qa(root, plan)
                self.assertEqual(approved["status"], "pass", approved)
                self.assertEqual(approved["technical_status"], "pass", approved)
                self.assertEqual(approved["scientific_status"], "pass", approved)
                self.assertEqual(approved["human_review_status"], "approved", approved)

                plan["panels"][0]["canvas"] = {"width": 401, "height": 300}
                wrong_size = self.qa.run_qa(root, plan)
                self.assertEqual(wrong_size["technical_status"], "fail", wrong_size)
                self.assertEqual(wrong_size["status"], "fail", wrong_size)
        finally:
            server.shutdown()
            server.server_close()

    def test_workflow_prepares_reviewed_request_without_personal_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "inputs"
            output = root / "output"
            inputs.mkdir()
            (inputs / "methods.txt").write_text(
                "The encoder flows to retrieval and then to the classifier.", encoding="utf-8"
            )
            environment = os.environ.copy()
            environment.pop("FIGURE_IMAGE_API_KEY", None)
            result = subprocess.run([
                sys.executable, str(SCRIPTS / "run_workflow.py"),
                "--input", str(inputs), "--brief", "Create a 3D scientific illustration",
                "--output", str(output), "--approve-plan",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, env=environment)
            self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
            manifest = json.loads(
                (output / "sources" / "raster-illustration-request.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["endpoint"], "https://right.codes/codex/v1/images/generations")
            self.assertEqual(manifest["model"], "gpt-image-2")
            self.assertFalse(manifest["credential_available"])
            self.assertFalse((output / "final" / "figure.png").exists())


if __name__ == "__main__":
    unittest.main()
