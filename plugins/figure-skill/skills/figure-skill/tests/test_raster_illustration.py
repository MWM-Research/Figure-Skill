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
        cls.planner = load_module("raster_plan_figure", SCRIPTS / "plan_figure.py")
        cls.qa = load_module("raster_qa_figure", SCRIPTS / "qa_figure.py")

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
                "visible_labels": [], "forbidden_content": ["invented measurements"],
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
                    "1024x1024", "medium", allow_insecure_http=True,
                )
                manifest = self.adapter.write_manifest(request, root)
                provenance = self.adapter.execute_request(request, "unit-test-key", allow_insecure_http=True)
                (root / "generation-provenance.json").write_text(
                    json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.assertTrue((root / "panel_a.png").is_file())
                self.assertEqual(ImageHandler.authorization, "Bearer unit-test-key")
                self.assertEqual(ImageHandler.request_body["model"], "image-model")
                self.assertNotIn("unit-test-key", manifest.read_text(encoding="utf-8"))
                report = self.qa.run_qa(root, plan)
                self.assertEqual(report["status"], "pass", report)
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
